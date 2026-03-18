"""
Backend API server for NEU Professor Ratings.
No pandas/numpy — queries CockroachDB directly per request.

Install deps:  pip install flask flask-cors flask-limiter psycopg2-binary pyjwt requests python-dotenv gunicorn
Run:           python server.py
"""

import os, re, unicodedata, json, hashlib
import html as _html
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
from functools import lru_cache
from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, redirect, make_response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import jwt as pyjwt
import requests as http_requests
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone
from threading import Lock
import time

load_dotenv()


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────
def normalize_name(name):
    s = str(name).strip().lower()
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def sanitize(text: str) -> str:
    return _html.escape(str(text), quote=False)


def friendly_count(n: int) -> str:
    if n < 100:
        return str(n)
    rounded = (n // 100) * 100
    return f"{rounded:,}+"


def _name_to_slug(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


# ──────────────────────────────────────────────
#  App setup
# ──────────────────────────────────────────────
app = Flask(__name__)
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
CORS(app, supports_credentials=True, origins=[FRONTEND_URL])
limiter = Limiter(get_remote_address, app=app, default_limits=["120 per minute"])


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ──────────────────────────────────────────────
#  Database connection pool
# ──────────────────────────────────────────────
CRDB_DATABASE_URL = os.getenv("CRDB_DATABASE_URL")
if not CRDB_DATABASE_URL:
    raise RuntimeError("CRDB_DATABASE_URL environment variable is required")

pool = SimpleConnectionPool(1, 5, CRDB_DATABASE_URL, sslmode="require")

# ──────────────────────────────────────────────
#  Simple in-memory cache (TTL-based)
# ──────────────────────────────────────────────
_cache = {}
_cache_lock = Lock()
CACHE_TTL = 300  # 5 minutes


def cache_get(key):
    with _cache_lock:
        entry = _cache.get(key)
        if entry and time.time() - entry["ts"] < CACHE_TTL:
            return entry["data"]
        return None


def cache_set(key, data):
    with _cache_lock:
        _cache[key] = {"data": data, "ts": time.time()}
        # Evict old entries if cache gets too large
        if len(_cache) > 2000:
            cutoff = time.time() - CACHE_TTL
            expired = [k for k, v in _cache.items() if v["ts"] < cutoff]
            for k in expired:
                del _cache[k]


def get_db():
    if 'db' not in g:
        g.db = pool.getconn()
    return g.db


@app.teardown_appcontext
def return_db(exc):
    db = g.pop('db', None)
    if db is not None:
        pool.putconn(db)


def query(sql, params=None):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(sql, params or ())
    return cur.fetchall()


def query_one(sql, params=None):
    rows = query(sql, params)
    return rows[0] if rows else None


# ──────────────────────────────────────────────
#  Google OAuth config
# ──────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required")
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


# ──────────────────────────────────────────────
#  Search helper
# ──────────────────────────────────────────────
def _professor_search(q, limit=5):
    """Search professors with tiered relevance ranking."""
    words = q.split()
    if not words:
        return []

    # Build WHERE: each word must appear somewhere in name_key
    conditions = []
    params = []
    for word in words:
        conditions.append("name_key LIKE %s")
        params.append(f"%{word}%")

    where = " AND ".join(conditions)
    rows = query(
        f"SELECT slug, name, name_key, department, avg_rating, total_reviews "
        f"FROM professors_catalog WHERE {where} "
        f"ORDER BY total_reviews DESC LIMIT 100",
        params
    )

    # Rank in Python for proper tiered relevance
    def rank_match(row):
        nk = row['name_key']
        parts = nk.split()

        # Tier 1: q matches a whole name part exactly
        if q in parts:
            return 1
        # Tier 2: q matches the start of any name part
        if any(p.startswith(q) for p in parts):
            return 2
        # Tier 3: q is a substring of the full name
        if q in nk:
            return 3
        # Tier 4: multi-word: each word prefixes a name part
        if len(words) >= 2 and all(any(p.startswith(w) for p in parts) for w in words):
            return 4
        # Tier 5: multi-word: each word is substring of any name part
        if len(words) >= 2 and all(any(w in p for p in parts) for w in words):
            return 5
        return 6

    ranked = sorted(rows, key=lambda r: (rank_match(r), -(r['total_reviews'] or 0)))
    return ranked[:limit]


# ──────────────────────────────────────────────
#  API Routes
# ──────────────────────────────────────────────
@app.route("/api/stats")
def stats():
    cached = cache_get("stats")
    if cached:
        resp = jsonify(cached)
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp
    rows = query("SELECT key, value FROM stats_cache")
    stat_map = {r['key']: r['value'] for r in rows}
    result = [
        {"label": "Professors", "value": friendly_count(stat_map.get('professors', 0))},
        {"label": "Courses", "value": friendly_count(stat_map.get('courses', 0))},
        {"label": "Comments", "value": friendly_count(stat_map.get('comments', 0))},
        {"label": "Departments", "value": friendly_count(stat_map.get('departments', 0))},
    ]
    cache_set("stats", result)
    resp = jsonify(result)
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


@app.route("/api/colleges")
def colleges():
    rows = query("""
        SELECT college, COUNT(*) as cnt FROM professors_catalog
        WHERE avg_rating IS NOT NULL
        GROUP BY college HAVING COUNT(*) >= 5
        ORDER BY college
    """)
    return jsonify([r['college'] for r in rows if r['college'] != 'Other'])


NO_MIN_COLLEGES = {"Law", "Professional Studies"}


@app.route("/api/goat-professors")
def goat_professors():
    college = request.args.get("college", "Khoury")
    limit = min(int(request.args.get("limit", "10")), 50)
    min_reviews = int(request.args.get("min_reviews", "10"))

    if college in NO_MIN_COLLEGES:
        rows = query("""
            SELECT * FROM professors_catalog
            WHERE college = %s AND total_reviews >= 5
            ORDER BY avg_rating DESC NULLS LAST, total_reviews DESC
            LIMIT %s
        """, (college, limit))
    else:
        rows = query("""
            SELECT * FROM professors_catalog
            WHERE college = %s AND num_ratings >= %s AND trace_reviews >= %s AND trace_rating IS NOT NULL
            ORDER BY avg_rating DESC NULLS LAST, total_reviews DESC
            LIMIT %s
        """, (college, min_reviews, min_reviews, limit))

    result = []
    for row in rows:
        result.append({
            "name": row["name"],
            "dept": row["department"],
            "rmpRating": round(row["rmp_rating"], 2) if row["rmp_rating"] else None,
            "traceRating": round(row["trace_rating"], 2) if row["trace_rating"] else None,
            "avgRating": round(row["avg_rating"], 2) if row["avg_rating"] else None,
            "rmpReviews": row["num_ratings"],
            "traceReviews": row["trace_reviews"],
            "totalReviews": row["total_reviews"],
            "url": row["professor_url"] or "",
        })
    return jsonify(result)


@app.route("/api/random-professor")
def random_professor():
    row = query_one("""
        SELECT * FROM professors_catalog
        WHERE num_ratings >= 3
        ORDER BY random() LIMIT 1
    """)
    if not row:
        return jsonify({"error": "No professors found"}), 404
    return jsonify({
        "name": row["name"],
        "dept": row["department"],
        "rmpRating": round(row["rmp_rating"], 2) if row["rmp_rating"] else None,
        "traceRating": round(row["trace_rating"], 2) if row["trace_rating"] else None,
        "avgRating": round(row["avg_rating"], 2) if row["avg_rating"] else None,
        "rmpReviews": row["num_ratings"],
        "traceReviews": row["trace_reviews"],
        "totalReviews": row["total_reviews"],
        "url": row["professor_url"] or "",
        "college": row["college"],
    })


# ──────────────────────────────────────────────
#  Precompute search indexes for autocomplete
# ──────────────────────────────────────────────
# Professors: merge RMP + TRACE so all instructors are searchable

# RMP professors (already have avg_rating, trace_dept, etc.)
rmp_for_search = rmp_profs[["name", "_name_key", "department", "trace_dept", "avg_rating", "total_reviews"]].copy()
rmp_for_search["_name_lower"] = rmp_for_search["_name_key"]
# Use TRACE department if available, otherwise fall back to RMP department
rmp_for_search["dept_display"] = rmp_for_search["trace_dept"].fillna(rmp_for_search["department"])

# TRACE-only professors (not in RMP)
trace_unique = trace_courses[["_full", "departmentName"]].drop_duplicates(subset=["_full"])
trace_unique = trace_unique.rename(columns={"_full": "_name_lower", "departmentName": "dept_display"})
# Exclude those already in RMP
rmp_names = set(rmp_for_search["_name_lower"])
trace_only = trace_unique[~trace_unique["_name_lower"].isin(rmp_names)].copy()

# Build proper name (title case) from the lowercase key
trace_only["name"] = trace_only["_name_lower"].str.title()
trace_only["_name_key"] = trace_only["_name_lower"]
# Pull their TRACE rating and review counts from the lookups
trace_only["avg_rating"] = trace_only["_name_lower"].map(trace_lookup).fillna(0.0)
trace_only["total_reviews"] = trace_only["_name_lower"].map(trace_reviews_lookup).fillna(0).astype(int)

# Combine
prof_search = pd.concat([
    rmp_for_search[["name", "_name_key", "_name_lower", "dept_display", "avg_rating", "total_reviews"]],
    trace_only[["name", "_name_key", "_name_lower", "dept_display", "avg_rating", "total_reviews"]],
], ignore_index=True)

# Drop any without any department info
prof_search = prof_search[prof_search["dept_display"].notna()]

# Split into individual name parts for whole-word matching (strip punctuation for better matching)
prof_search["_name_parts"] = prof_search["_name_lower"].str.replace(r'[^\w\s]', '', regex=True).str.split()
prof_search = prof_search.drop_duplicates(subset=["_name_key"])

print(f"[search] Indexed {len(prof_search)} professors ({len(rmp_for_search)} RMP + {len(trace_only)} TRACE-only)")

# Courses: unique course codes with their name
# displayName format: "ACCT6228:02 (Contmp Issues Accountng Theory) - Michael Rezuke"

def parse_course(display_name):
    m = re.match(r"^([A-Z]+\d+):\d+\s+\((.+?)\)", str(display_name))
    if m:
        return m.group(1), m.group(2)
    return None, None


def _format_course_code(raw: str) -> str:
    return re.sub(r"\s+", "", str(raw).upper())


def _safe_int(value, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default

trace_courses["_parsed"] = trace_courses["displayName"].apply(parse_course)
trace_courses["_code"] = trace_courses["_parsed"].apply(lambda x: x[0])
trace_courses["_cname"] = trace_courses["_parsed"].apply(lambda x: x[1])

course_search = (
    trace_courses[trace_courses["_code"].notna()]
    [["_code", "_cname", "departmentName"]]
    .drop_duplicates(subset=["_code"])
    .copy()
)
course_search["_search_lower"] = (
    course_search["_code"].str.lower() + " " + course_search["_cname"].astype(str).str.lower()
)

print(f"[search] Indexed {len(prof_search)} professors, {len(course_search)} courses")


# ──────────────────────────────────────────────
#  Course aggregates (catalog + detail pages)
# ──────────────────────────────────────────────
trace_courses["_code_norm"] = trace_courses["_code"].astype(str).apply(_format_course_code)
trace_courses["_instructor_name"] = (
    trace_courses["instructorFirstName"].fillna("").astype(str).str.strip()
    + " "
    + trace_courses["instructorLastName"].fillna("").astype(str).str.strip()
).str.replace(r"\s+", " ", regex=True).str.strip()

trace_courses["termId"] = pd.to_numeric(trace_courses["termId"], errors="coerce").fillna(0).astype(int)
trace_courses["enrollment"] = pd.to_numeric(trace_courses["enrollment"], errors="coerce").fillna(0).astype(int)

_course_sections = (
    trace_courses[trace_courses["_code"].notna()]
    [[
        "courseId", "instructorId", "termId", "termTitle", "departmentName", "displayName",
        "section", "enrollment", "_code", "_code_norm", "_cname", "_instructor_name",
    ]]
    .drop_duplicates(subset=["courseId", "instructorId", "termId"])
    .copy()
)

_overall_scores = trace_scores[
    trace_scores["question"].astype(str).str.lower().str.contains("overall", na=False)
][[
    "courseId", "instructorId", "termId", "_weighted_sum", "_total_responses", "completed"
]].copy()

_overall_combo = (
    _overall_scores
    .groupby(["courseId", "instructorId", "termId"], as_index=False)
    .agg({
        "_weighted_sum": "sum",
        "_total_responses": "sum",
        "completed": "sum",
    })
)
_overall_combo["overallMean"] = _overall_combo.apply(
    lambda r: (r["_weighted_sum"] / r["_total_responses"]) if r["_total_responses"] > 0 else np.nan,
    axis=1,
)

_course_sections_scored = _course_sections.merge(
    _overall_combo,
    on=["courseId", "instructorId", "termId"],
    how="left",
)

_course_latest = (
    _course_sections.sort_values("termId", ascending=False)
    .drop_duplicates(subset=["_code_norm"])
    [["_code_norm", "_code", "_cname", "departmentName", "termTitle", "termId"]]
    .rename(columns={
        "_code": "code",
        "_cname": "name",
        "departmentName": "department",
        "termTitle": "latestTermTitle",
        "termId": "latestTermId",
    })
)

_course_catalog_base = (
    _course_sections_scored
    .groupby("_code_norm", as_index=False)
    .agg({
        "courseId": "count",
        "instructorId": pd.Series.nunique,
        "enrollment": "sum",
        "_weighted_sum": "sum",
        "_total_responses": "sum",
        "completed": "sum",
    })
    .rename(columns={
        "courseId": "totalSections",
        "instructorId": "totalInstructors",
        "enrollment": "totalEnrollment",
        "completed": "totalCompleted",
    })
)
_course_catalog_base["avgRating"] = _course_catalog_base.apply(
    lambda r: (r["_weighted_sum"] / r["_total_responses"]) if r["_total_responses"] > 0 else np.nan,
    axis=1,
)

course_catalog_df = _course_catalog_base.merge(_course_latest, on="_code_norm", how="left")
course_catalog_df["_search_lower"] = (
    course_catalog_df["code"].fillna("").astype(str).str.lower() + " "
    + course_catalog_df["name"].fillna("").astype(str).str.lower() + " "
    + course_catalog_df["department"].fillna("").astype(str).str.lower()
)

print(f"[courses] Built course catalog with {len(course_catalog_df)} rows")


def _professor_search_matches(query: str) -> pd.DataFrame:
    """Return professor matches using the same tiered logic as homepage search."""
    q = normalize_name(query)
    if len(q) < 2:
        return prof_search.iloc[0:0]

    # Tier 1: query matches a whole first or last name exactly
    exact_word = prof_search[prof_search["_name_parts"].apply(
        lambda parts: q in parts if isinstance(parts, list) else False
    )]

    # Tier 2: query matches the start of any name part (but not exact)
    starts_word = prof_search[
        prof_search["_name_parts"].apply(
            lambda parts: any(p.startswith(q) for p in parts) if isinstance(parts, list) else False
        ) &
        ~prof_search.index.isin(exact_word.index)
    ]

    # Tier 3: substring match anywhere in full name
    contains = prof_search[
        prof_search["_name_lower"].str.contains(q, na=False) &
        ~prof_search.index.isin(exact_word.index) &
        ~prof_search.index.isin(starts_word.index)
    ]

    # Tier 4: spaced queries — each word must prefix a name part
    fallback_matches = pd.DataFrame()
    if ' ' in q:
        words = q.split()
        if len(words) >= 2:
            def robust_match(prof_parts):
                if not isinstance(prof_parts, list):
                    return False
                for qw in words:
                    if not any(pp.startswith(qw) for pp in prof_parts):
                        return False
                return True

            mask = prof_search["_name_parts"].apply(robust_match)
            fallback_matches = prof_search[
                mask &
                ~prof_search.index.isin(exact_word.index) &
                ~prof_search.index.isin(starts_word.index) &
                ~prof_search.index.isin(contains.index)
            ]

    # Tier 5: each query word is a substring of any name part (loosest)
    substring_matches = pd.DataFrame()
    if ' ' in q:
        words = q.split()
        if len(words) >= 2:
            def substring_match(prof_parts):
                if not isinstance(prof_parts, list):
                    return False
                for qw in words:
                    if not any(qw in pp for pp in prof_parts):
                        return False
                return True

            already = set(exact_word.index) | set(starts_word.index) | set(contains.index)
            if not fallback_matches.empty:
                already |= set(fallback_matches.index)

            mask = prof_search["_name_parts"].apply(substring_match)
            substring_matches = prof_search[
                mask & ~prof_search.index.isin(already)
            ]

    all_matches = [
        exact_word.sort_values("total_reviews", ascending=False),
        starts_word.sort_values("total_reviews", ascending=False),
        contains.sort_values("total_reviews", ascending=False),
    ]
    if not fallback_matches.empty:
        all_matches.append(fallback_matches.sort_values("total_reviews", ascending=False))
    if not substring_matches.empty:
        all_matches.append(substring_matches.sort_values("total_reviews", ascending=False))

    return pd.concat(all_matches)


@app.route("/api/search")
def search():
    q = normalize_name(request.args.get("q", ""))
    search_type = request.args.get("type", "Professor")
    limit = min(int(request.args.get("limit", "5")), 20)

    if len(q) < 2:
        return jsonify([])

    if search_type == "Professor":
        matches = _professor_search(q, limit)
        results = []
        for r in matches:
            results.append({
                "type": "professor",
                "name": r["name"],
                "dept": r["department"],
                "rating": round(r["avg_rating"], 2) if r["avg_rating"] and r["avg_rating"] > 0 else None,
                "slug": r["slug"],
            })
        return jsonify(results)

    else:
        # Course search
        rows = query("""
            SELECT code, name, department FROM course_catalog
            WHERE search_text LIKE %s
            ORDER BY
                CASE WHEN lower(code) LIKE %s THEN 0 ELSE 1 END,
                code
            LIMIT %s
        """, (f"%{q}%", f"{q}%", limit))

        results = []
        for r in rows:
            results.append({
                "type": "course",
                "code": r["code"],
                "name": r["name"],
                "dept": r["department"],
            })
        return jsonify(results)


# ──────────────────────────────────────────────
#  Professor profile page
# ──────────────────────────────────────────────
@app.route("/api/professors/<slug>")
def professor_profile(slug):
    # Check cache first
    cache_key = f"prof:{slug}"
    cached = cache_get(cache_key)
    if cached:
        resp = jsonify(cached)
        resp.headers["Cache-Control"] = "public, max-age=300"
        return resp

    # Look up professor from catalog
    prof = query_one("SELECT * FROM professors_catalog WHERE slug = %s", (slug,))

    if not prof:
        # Try resolving slug to name_key
        name_key = slug.strip().lower().replace("-", " ")
        prof = query_one("SELECT * FROM professors_catalog WHERE name_key = %s", (name_key,))

    if not prof:
        return jsonify({"error": "Professor not found"}), 404

    name_key = prof["name_key"]

    profile = {
        "name": prof["name"],
        "department": prof["department"],
        "rmpRating": round(prof["rmp_rating"], 2) if prof["rmp_rating"] else None,
        "traceRating": round(prof["trace_rating"], 2) if prof["trace_rating"] else None,
        "avgRating": round(prof["avg_rating"], 2) if prof["avg_rating"] else 0.0,
        "numRatings": prof["num_ratings"],
        "wouldTakeAgainPct": round(prof["would_take_again_pct"], 1) if prof["would_take_again_pct"] else None,
        "difficulty": round(prof["difficulty"], 2) if prof["difficulty"] else None,
        "totalRatings": prof["total_reviews"],
        "professorUrl": prof["professor_url"],
        "imageUrl": prof["image_url"],
    }

    # ── TRACE courses + scores (batched into 2 queries instead of N+1) ──
    trace_course_rows = query("""
        SELECT course_id, term_id, term_title, department_name, display_name,
               section, enrollment, instructor_id
        FROM trace_courses WHERE name_key = %s
        ORDER BY term_id DESC
    """, (name_key,))

    # Batch-fetch all scores for this professor's courses in one query
    scores_by_key = {}
    if trace_course_rows:
        keys = [(int(c["course_id"]), int(c["instructor_id"]), int(c["term_id"] or 0)) for c in trace_course_rows]
        or_clauses = []
        score_params = []
        for cid, iid, tid in keys:
            or_clauses.append("(course_id = %s AND instructor_id = %s AND term_id = %s)")
            score_params.extend([cid, iid, tid])

        all_scores = query(
            f"SELECT course_id, instructor_id, term_id, question, mean, median, std_dev, "
            f"enrollment, completed, total_responses, count_1, count_2, count_3, count_4, count_5 "
            f"FROM trace_scores WHERE {' OR '.join(or_clauses)}",
            score_params
        )
        for s in all_scores:
            k = (int(s["course_id"]), int(s["instructor_id"]), int(s["term_id"] or 0))
            scores_by_key.setdefault(k, []).append(s)

    trace_course_list = []
    for c in trace_course_rows:
        cid = int(c["course_id"])
        iid = int(c["instructor_id"])
        tid = int(c["term_id"]) if c["term_id"] else 0

        scores_list = []
        for s in scores_by_key.get((cid, iid, tid), []):
            scores_list.append({
                "question": str(s["question"] or ""),
                "mean": round(float(s["mean"]), 2) if s["mean"] else 0,
                "median": round(float(s["median"]), 2) if s["median"] else 0,
                "stdDev": round(float(s["std_dev"]), 2) if s["std_dev"] else 0,
                "enrollment": int(s["enrollment"] or 0),
                "completed": int(s["completed"] or 0),
                "totalResponses": int(s["total_responses"] or 0),
                "count1": int(s["count_1"] or 0),
                "count2": int(s["count_2"] or 0),
                "count3": int(s["count_3"] or 0),
                "count4": int(s["count_4"] or 0),
                "count5": int(s["count_5"] or 0),
            })

        trace_course_list.append({
            "courseId": cid,
            "termId": tid,
            "termTitle": str(c["term_title"] or ""),
            "departmentName": str(c["department_name"] or ""),
            "displayName": str(c["display_name"] or ""),
            "section": str(c["section"] or ""),
            "enrollment": int(c["enrollment"] or 0),
            "scores": scores_list,
        })

    profile["traceCourses"] = trace_course_list

    # ── RMP reviews ──
    review_rows = query("""
        SELECT professor_name, department, overall_rating, course,
               quality, difficulty, date, tags, attendance, grade,
               textbook, online_class, comment
        FROM rmp_reviews WHERE name_key = %s
    """, (name_key,))

    reviews = []
    for r in review_rows:
        reviews.append({
            "professorName": str(r["professor_name"] or ""),
            "department": str(r["department"] or ""),
            "overallRating": float(r["overall_rating"]) if r["overall_rating"] else 0,
            "course": str(r["course"] or ""),
            "quality": int(r["quality"]) if r["quality"] else 0,
            "difficulty": int(r["difficulty"]) if r["difficulty"] else 0,
            "date": str(r["date"] or ""),
            "tags": str(r["tags"] or ""),
            "attendance": str(r["attendance"] or ""),
            "grade": str(r["grade"] or ""),
            "textbook": str(r["textbook"] or ""),
            "online_class": str(r["online_class"] or ""),
            "comment": sanitize(r["comment"]) if r["comment"] else "",
        })
    profile["reviews"] = reviews

    # ── TRACE comments ──
    if trace_course_rows:
        url_patterns = set()
        for c in trace_course_rows:
            cid = str(int(c["course_id"]))
            iid = str(int(c["instructor_id"]))
            tid = str(int(c["term_id"])) if c["term_id"] else ""
            url_patterns.add(f"sp={cid}&sp={iid}&sp={tid}")

        # Build OR conditions for URL matching
        or_conditions = []
        or_params = []
        for pat in url_patterns:
            or_conditions.append("course_url LIKE %s")
            or_params.append(f"%{pat}%")

        if or_conditions:
            comment_rows = query(
                f"SELECT course_url, question, comment FROM trace_comments WHERE {' OR '.join(or_conditions)}",
                or_params
            )

            comments = []
            for c in comment_rows:
                comment_text = sanitize(c["comment"]) if c["comment"] else ""
                if not comment_text.strip():
                    continue

                url = str(c["course_url"] or "")
                term_id = 0
                try:
                    sp_matches = re.findall(r"sp=(\d+)", url)
                    if len(sp_matches) >= 3:
                        term_id = int(sp_matches[2])
                except (ValueError, IndexError):
                    pass

                comments.append({
                    "courseUrl": url,
                    "question": str(c["question"] or ""),
                    "comment": comment_text,
                    "termId": term_id,
                })
            profile["traceComments"] = comments
        else:
            profile["traceComments"] = []
    else:
        profile["traceComments"] = []

    cache_set(cache_key, profile)
    resp = jsonify(profile)
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


@app.route("/api/departments")
def departments():
    college = request.args.get("college", "")
    if college and college != "All":
        rows = query("""
            SELECT DISTINCT department FROM professors_catalog
            WHERE avg_rating IS NOT NULL AND college = %s
            ORDER BY department
        """, (college,))
    else:
        rows = query("""
            SELECT DISTINCT department FROM professors_catalog
            WHERE avg_rating IS NOT NULL
            ORDER BY department
        """)
    return jsonify([r['department'] for r in rows if r['department']])


@app.route("/api/professors-catalog")
def professors_catalog():
    q = normalize_name(request.args.get("q", ""))
    college = request.args.get("college", "")
    dept = request.args.get("dept", "")
    sort = request.args.get("sort", "alpha")
    page = int(request.args.get("page", "1"))
    limit = min(int(request.args.get("limit", "20")), 10000)

    try:
        min_rating = float(request.args.get("minRating", "0"))
    except (ValueError, TypeError):
        min_rating = 0.0
    try:
        max_rating = float(request.args.get("maxRating", "5"))
    except (ValueError, TypeError):
        max_rating = 5.0
    try:
        min_reviews = int(request.args.get("minReviews", "1"))
    except (ValueError, TypeError):
        min_reviews = 1
    max_reviews_raw = request.args.get("maxReviews")
    try:
        max_reviews = int(max_reviews_raw) if max_reviews_raw is not None else None
    except (ValueError, TypeError):
        max_reviews = None

    # If there's a search query, get matching name_keys first
    matched_name_keys = None
    if q and len(q) >= 2:
        matches = _professor_search(q, limit=200)
        matched_name_keys = [m["name_key"] for m in matches]
        if not matched_name_keys:
            return jsonify({"professors": [], "total": 0, "page": 1, "totalPages": 1})

    # Build dynamic query
    conditions = ["avg_rating IS NOT NULL"]
    params = []

    if college and college != "All":
        conditions.append("college = %s")
        params.append(college)
    if dept and dept != "All":
        conditions.append("department = %s")
        params.append(dept)
    if min_rating > 0:
        conditions.append("avg_rating >= %s")
        params.append(min_rating)
    if max_rating < 5:
        conditions.append("avg_rating <= %s")
        params.append(max_rating)
    if min_reviews > 1:
        conditions.append("total_reviews >= %s")
        params.append(min_reviews)
    if max_reviews is not None:
        conditions.append("total_reviews <= %s")
        params.append(max_reviews)

    where = " AND ".join(conditions)

    if matched_name_keys is not None:
        # Filter to search matches, preserve search order
        placeholders = ",".join(["%s"] * len(matched_name_keys))
        # Get total count
        count_row = query_one(
            f"SELECT COUNT(*) as cnt FROM professors_catalog WHERE {where} AND name_key IN ({placeholders})",
            params + matched_name_keys
        )
        total = count_row["cnt"]

        # Get page data - preserve search ranking order
        total_pages = max(1, (total + limit - 1) // limit)
        page = max(1, min(page, total_pages))
        offset = (page - 1) * limit

        all_rows = query(
            f"SELECT * FROM professors_catalog WHERE {where} AND name_key IN ({placeholders})",
            params + matched_name_keys
        )

        # Reorder by search ranking
        name_key_order = {nk: i for i, nk in enumerate(matched_name_keys)}
        all_rows.sort(key=lambda r: name_key_order.get(r["name_key"], 999999))
        page_rows = all_rows[offset:offset + limit]
    else:
        # No search - use SQL sorting
        if sort == "rating":
            order = "avg_rating DESC NULLS LAST"
        elif sort == "reviews":
            order = "total_reviews DESC"
        else:
            order = "lower(name) ASC"

        count_row = query_one(f"SELECT COUNT(*) as cnt FROM professors_catalog WHERE {where}", params)
        total = count_row["cnt"]

        total_pages = max(1, (total + limit - 1) // limit)
        page = max(1, min(page, total_pages))
        offset = (page - 1) * limit

        page_rows = query(
            f"SELECT * FROM professors_catalog WHERE {where} ORDER BY {order} LIMIT %s OFFSET %s",
            params + [limit, offset]
        )

    professors = []
    for row in page_rows:
        professors.append({
            "name": row["name"],
            "slug": row["slug"],
            "department": row["department"],
            "college": row["college"],
            "avgRating": round(row["avg_rating"], 2) if row["avg_rating"] else None,
            "rmpRating": round(row["rmp_rating"], 2) if row["rmp_rating"] else None,
            "traceRating": round(row["trace_rating"], 2) if row["trace_rating"] else None,
            "totalReviews": row["total_reviews"],
            "wouldTakeAgainPct": round(row["would_take_again_pct"], 1) if row["would_take_again_pct"] else None,
            "imageUrl": row["image_url"],
        })

    return jsonify({
        "professors": professors,
        "total": total,
        "page": page,
        "totalPages": total_pages,
    })


@app.route("/api/course-departments")
def course_departments():
    depts = sorted(
        course_catalog_df["department"]
        .dropna()
        .astype(str)
        .replace("", np.nan)
        .dropna()
        .unique()
        .tolist()
    )
    return jsonify(depts)


@app.route("/api/courses-catalog")
def courses_catalog():
    q = normalize_name(request.args.get("q", ""))
    dept = request.args.get("dept", "")
    sort = request.args.get("sort", "alpha")
    page = int(request.args.get("page", "1"))
    limit = min(int(request.args.get("limit", "20")), 10000)

    try:
        min_rating = float(request.args.get("minRating", "0"))
    except (ValueError, TypeError):
        min_rating = 0.0

    try:
        max_rating = float(request.args.get("maxRating", "5"))
    except (ValueError, TypeError):
        max_rating = 5.0

    subset = course_catalog_df[course_catalog_df["avgRating"].notna()].copy()

    if dept and dept != "All":
        subset = subset[subset["department"] == dept]
    if q:
        subset = subset[subset["_search_lower"].str.contains(q, na=False)]
    if min_rating > 0:
        subset = subset[subset["avgRating"] >= min_rating]
    if max_rating < 5:
        subset = subset[subset["avgRating"] <= max_rating]

    if sort == "rating":
        subset = subset.sort_values("avgRating", ascending=False, na_position="last")
    elif sort == "sections":
        subset = subset.sort_values("totalSections", ascending=False)
    elif sort == "recent":
        subset = subset.sort_values("latestTermId", ascending=False)
    else:
        subset = subset.sort_values("code", ascending=True, key=lambda s: s.str.lower())

    total = len(subset)
    total_pages = max(1, (total + limit - 1) // limit)
    page = max(1, min(page, total_pages))
    start = (page - 1) * limit
    page_data = subset.iloc[start:start + limit]

    courses = []
    for _, row in page_data.iterrows():
        courses.append({
            "code": row["code"],
            "name": row["name"],
            "department": row["department"],
            "avgRating": round(float(row["avgRating"]), 2) if pd.notna(row["avgRating"]) else None,
            "totalSections": int(row["totalSections"]),
            "totalInstructors": int(row["totalInstructors"]),
            "totalEnrollment": int(row["totalEnrollment"]),
            "totalResponses": int(row["_total_responses"]),
            "latestTermTitle": row["latestTermTitle"] if pd.notna(row["latestTermTitle"]) else "",
            "latestTermId": int(row["latestTermId"]) if pd.notna(row["latestTermId"]) else 0,
        })

    return jsonify({
        "courses": courses,
        "total": total,
        "page": page,
        "totalPages": total_pages,
    })


@app.route("/api/courses/<code>")
def course_profile(code):
    code_norm = _format_course_code(code)
    if not code_norm:
        return jsonify({"error": "Course not found"}), 404

    course_rows = _course_sections_scored[_course_sections_scored["_code_norm"] == code_norm].copy()
    if course_rows.empty:
        return jsonify({"error": "Course not found"}), 404

    latest_row = course_rows.sort_values("termId", ascending=False).iloc[0]

    total_weighted = _safe_float(course_rows["_weighted_sum"].fillna(0).sum())
    total_responses = _safe_int(course_rows["_total_responses"].fillna(0).sum())
    avg_rating = (total_weighted / total_responses) if total_responses > 0 else None

    summary = {
        "code": str(latest_row["_code"]),
        "name": str(latest_row["_cname"]),
        "department": str(latest_row["departmentName"]) if pd.notna(latest_row["departmentName"]) else "",
        "avgRating": round(avg_rating, 2) if avg_rating is not None else None,
        "totalSections": int(len(course_rows)),
        "totalInstructors": int(course_rows["instructorId"].nunique()),
        "totalEnrollment": _safe_int(course_rows["enrollment"].fillna(0).sum()),
        "totalResponses": total_responses,
        "latestTermTitle": str(latest_row["termTitle"]) if pd.notna(latest_row["termTitle"]) else "",
        "latestTermId": _safe_int(latest_row["termId"]),
    }

    difficulty_lookup = {}
    if "level_of_difficulty" in rmp_profs.columns:
        _difficulty_series = pd.to_numeric(rmp_profs["level_of_difficulty"], errors="coerce")
        for nk, diff in zip(rmp_profs["_name_key"], _difficulty_series):
            key = normalize_name(nk)
            if key and pd.notna(diff):
                difficulty_lookup[key] = round(float(diff), 2)

    instructor_meta_lookup = {}
    _catalog_cols = ["name", "slug", "imageUrl", "_name_lower", "totalReviews", "wouldTakeAgainPct"]
    for _, prof in catalog_df[_catalog_cols].iterrows():
        slug = str(prof["slug"]) if pd.notna(prof["slug"]) else ""
        image_url = str(prof["imageUrl"]) if pd.notna(prof.get("imageUrl")) else None
        total_reviews = int(prof["totalReviews"]) if pd.notna(prof.get("totalReviews")) else 0
        wta = float(prof["wouldTakeAgainPct"]) if pd.notna(prof.get("wouldTakeAgainPct")) else None
        difficulty = difficulty_lookup.get(normalize_name(prof["_name_lower"]))
        meta_payload = {
            "slug": slug,
            "imageUrl": image_url,
            "totalReviews": total_reviews,
            "wouldTakeAgainPct": round(wta, 1) if wta is not None else None,
            "difficulty": difficulty,
        }

        key_display = normalize_name(prof["name"])
        if key_display and key_display not in instructor_meta_lookup:
            instructor_meta_lookup[key_display] = meta_payload

        key_lower = normalize_name(prof["_name_lower"])
        if key_lower and key_lower not in instructor_meta_lookup:
            instructor_meta_lookup[key_lower] = meta_payload

    instructor_rows = []
    for name, g in course_rows.groupby("_instructor_name"):
        weighted = _safe_float(g["_weighted_sum"].fillna(0).sum())
        responses = _safe_int(g["_total_responses"].fillna(0).sum())
        meta = instructor_meta_lookup.get(
            normalize_name(name),
            {
                "slug": "",
                "imageUrl": None,
                "totalReviews": 0,
                "wouldTakeAgainPct": None,
                "difficulty": None,
            },
        )
        instructor_rows.append({
            "name": name,
            "slug": meta["slug"],
            "imageUrl": meta["imageUrl"],
            "difficulty": meta["difficulty"],
            "wouldTakeAgainPct": meta["wouldTakeAgainPct"],
            "totalReviews": meta["totalReviews"],
            "sections": int(len(g)),
            "totalEnrollment": _safe_int(g["enrollment"].fillna(0).sum()),
            "totalResponses": responses,
            "avgRating": round(weighted / responses, 2) if responses > 0 else None,
        })
    instructor_rows.sort(key=lambda r: (r["avgRating"] is None, -(r["avgRating"] or 0), -r["sections"]))

    section_rows = []
    section_cols = [
        "courseId", "instructorId", "termId", "termTitle", "section", "enrollment",
        "_instructor_name", "overallMean", "_total_responses", "completed",
    ]
    for _, row in course_rows.sort_values("termId", ascending=False)[section_cols].iterrows():
        section_rows.append({
            "courseId": _safe_int(row["courseId"]),
            "instructorId": _safe_int(row["instructorId"]),
            "termId": _safe_int(row["termId"]),
            "termTitle": str(row["termTitle"]) if pd.notna(row["termTitle"]) else "",
            "section": str(row["section"]) if pd.notna(row["section"]) else "",
            "instructor": str(row["_instructor_name"]),
            "enrollment": _safe_int(row["enrollment"]),
            "overallRating": round(float(row["overallMean"]), 2) if pd.notna(row["overallMean"]) else None,
            "totalResponses": _safe_int(row["_total_responses"]),
            "completed": _safe_int(row["completed"]),
        })

    course_keys = course_rows[["courseId", "instructorId", "termId"]].drop_duplicates()
    score_subset = trace_scores.merge(course_keys, on=["courseId", "instructorId", "termId"], how="inner")

    question_rows = []
    if not score_subset.empty:
        grouped = score_subset.groupby("question", as_index=False).agg({
            "_weighted_sum": "sum",
            "_total_responses": "sum",
        })
        for _, row in grouped.iterrows():
            responses = _safe_int(row["_total_responses"])
            question_rows.append({
                "question": str(row["question"]),
                "avgRating": round(_safe_float(row["_weighted_sum"]) / responses, 2) if responses > 0 else None,
                "totalResponses": responses,
            })
    question_rows.sort(key=lambda r: (-r["totalResponses"], r["question"].lower()))

    return jsonify({
        "summary": summary,
        "instructors": instructor_rows,
        "sections": section_rows,
        "questionScores": question_rows,
    })


# ──────────────────────────────────────────────
#  Google OAuth routes
# ──────────────────────────────────────────────
def _get_redirect_uri():
    # Railway/proxies send X-Forwarded-Proto; use https in production
    scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
    host = request.host
    return f"{scheme}://{host}/api/auth/google/callback"


@app.route("/api/auth/google")
@limiter.limit("10 per minute")
def auth_google():
    return_to = request.args.get("returnTo", "/")
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": _get_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "hd": "husky.neu.edu",
    }
    is_popup = request.args.get("popup") == "1"
    resp = make_response(redirect(f"{GOOGLE_AUTH_URL}?{urlencode(params)}"))
    resp.set_cookie("auth_return_to", return_to, max_age=600, httponly=True, samesite="None", secure=True)
    if is_popup:
        resp.set_cookie("auth_popup", "1", max_age=600, httponly=True, samesite="None", secure=True)
    return resp


@app.route("/api/auth/google/callback")
@limiter.limit("10 per minute")
def auth_google_callback():
    code = request.args.get("code")
    if not code:
        return redirect(f"{FRONTEND_URL}?auth_error=no_code")

    token_resp = http_requests.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": _get_redirect_uri(),
        "grant_type": "authorization_code",
    })
    if token_resp.status_code != 200:
        return redirect(f"{FRONTEND_URL}?auth_error=token_exchange_failed")

    access_token = token_resp.json().get("access_token")

    user_resp = http_requests.get(GOOGLE_USERINFO_URL, headers={
        "Authorization": f"Bearer {access_token}",
    })
    if user_resp.status_code != 200:
        return redirect(f"{FRONTEND_URL}?auth_error=userinfo_failed")

    user_info = user_resp.json()

    if user_info.get("hd") != "husky.neu.edu":
        return redirect(f"{FRONTEND_URL}?auth_error=invalid_domain")

    payload = {
        "sub": user_info["id"],
        "email": user_info["email"],
        "name": user_info.get("name", ""),
        "picture": user_info.get("picture", ""),
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    token = pyjwt.encode(payload, JWT_SECRET, algorithm="HS256")

    is_popup = request.cookies.get("auth_popup") == "1"

    if is_popup:
        # Desktop popup: post message to opener and close
        resp = make_response(f"""
        <html><body><script>
          window.opener && window.opener.postMessage({{ type: "auth_complete", token: "{token}" }}, "{FRONTEND_URL}");
          window.close();
        </script></body></html>
        """)
        resp.delete_cookie("auth_popup")
    else:
        # Mobile redirect: pass token via URL fragment (not querystring, so it's not logged)
        return_to = request.cookies.get("auth_return_to", "/")
        from urllib.parse import urlparse
        parsed = urlparse(return_to)
        if parsed.scheme or parsed.netloc or not return_to.startswith("/"):
            return_to = "/"
        resp = make_response(redirect(f"{FRONTEND_URL}{return_to}#auth_token={token}"))
        resp.delete_cookie("auth_return_to")
    return resp


def _get_auth_token():
    """Get JWT token from Authorization header or cookie."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return request.cookies.get("auth_token")


@app.route("/api/auth/me")
@limiter.limit("30 per minute")
def auth_me():
    token = _get_auth_token()
    if not token:
        return jsonify(None), 401

    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return jsonify({
            "email": payload["email"],
            "name": payload["name"],
            "picture": payload.get("picture", ""),
        })
    except pyjwt.ExpiredSignatureError:
        return jsonify(None), 401
    except pyjwt.InvalidTokenError:
        return jsonify(None), 401


@app.route("/api/auth/logout", methods=["POST"])
@limiter.limit("10 per minute")
def auth_logout():
    resp = make_response(jsonify({"ok": True}))
    resp.delete_cookie("auth_token")
    return resp


if __name__ == "__main__":
    print("Starting server on port 5001...")
    app.run(debug=True, port=5001, use_reloader=True)
