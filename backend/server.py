"""
Backend API server for NEU Professor Ratings.
Place this file in: backend/server.py

Install deps:  pip install flask flask-cors pandas
Run:           python backend/server.py
"""

import os, re, unicodedata
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from flask import Flask, jsonify, request, redirect, make_response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import jwt as pyjwt
import requests as http_requests
from urllib.parse import urlencode
from datetime import datetime, timedelta, timezone

load_dotenv()


def normalize_name(name):
    """Lowercase, strip accents, collapse whitespace."""
    s = str(name).strip().lower()
    # Strip accents: María → maria
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    # Collapse whitespace
    s = re.sub(r'\s+', ' ', s).strip()
    return s

import html as _html

def sanitize(text: str) -> str:
    """Escape HTML entities in user-generated content as defense-in-depth."""
    return _html.escape(str(text), quote=False)

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
#  Google OAuth config
# ──────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required — set it in backend/.env")
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# ──────────────────────────────────────────────
#  Load CSVs once at startup
# ──────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "Better_Scraper", "output_data")

rmp_profs    = pd.read_csv(os.path.join(DATA_DIR, "rmp_professors.csv"))
rmp_reviews  = pd.read_csv(os.path.join(DATA_DIR, "rmp_reviews.csv"))
trace_courses = pd.read_csv(os.path.join(DATA_DIR, "trace_courses.csv"))
trace_scores  = pd.read_csv(os.path.join(DATA_DIR, "trace_scores.csv"))
trace_comments = pd.read_csv(os.path.join(DATA_DIR, "trace_comments.csv"))

# Load professor photos
def _upgrade_image_url(url: str) -> str:
    """Strip WordPress thumbnail size suffix to get the full-resolution original."""
    return re.sub(r'-\d+x\d+(?=\.\w+$)', '', url)

photo_lookup = {}
photos_path = os.path.join(DATA_DIR, "professor_photos.csv")
if os.path.exists(photos_path):
    _photos = pd.read_csv(photos_path)
    for _, row in _photos.iterrows():
        key = normalize_name(str(row['name']))
        photo_lookup[key] = _upgrade_image_url(str(row['image_url']))
    print(f"[startup] Loaded {len(photo_lookup)} professor photos (upgraded to full-res)")
else:
    print("[startup] No professor_photos.csv found — photos disabled")

# Clean RMP data
rmp_profs["rating"]      = pd.to_numeric(rmp_profs["rating"], errors="coerce")
rmp_profs["num_ratings"] = pd.to_numeric(rmp_profs["num_ratings"], errors="coerce")
rmp_profs.dropna(subset=["rating", "num_ratings"], inplace=True)

# Normalize display names — collapse double spaces like "Jelena  Golubovic"
rmp_profs["name"] = rmp_profs["name"].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()

# Fix TRACE scores: The stored `mean` column is WRONG in the CSV — compute it from count_1..count_5
for col in ["count_1", "count_2", "count_3", "count_4", "count_5", "completed"]:
    trace_scores[col] = pd.to_numeric(trace_scores[col], errors="coerce").fillna(0).astype(int)

trace_scores["_total_responses"] = (
    trace_scores["count_1"] + trace_scores["count_2"] +
    trace_scores["count_3"] + trace_scores["count_4"] +
    trace_scores["count_5"]
)
trace_scores["_weighted_sum"] = (
    1 * trace_scores["count_1"] + 2 * trace_scores["count_2"] +
    3 * trace_scores["count_3"] + 4 * trace_scores["count_4"] +
    5 * trace_scores["count_5"]
)
# Avoid division by zero
trace_scores["mean"] = trace_scores.apply(
    lambda r: r["_weighted_sum"] / r["_total_responses"]
              if r["_total_responses"] > 0 else np.nan,
    axis=1,
)

# ──────────────────────────────────────────────
#  Alias Mapping (Entity Resolution)
# ──────────────────────────────────────────────
ALIAS_MAP = {
    "laney strange": "elena strange",
}

def merge_rmp_aliases(df):
    df["_name_key"] = df["name"].apply(normalize_name)
    df["_name_key"] = df["_name_key"].replace(ALIAS_MAP)
    rows = []
    for nk, g in df.groupby("_name_key"):
        if len(g) == 1:
            rows.append(g.iloc[0])
            continue
        g = g.sort_values("num_ratings", ascending=False)
        primary = g.iloc[0].copy()
        tot = g["num_ratings"].sum()
        if tot > 0:
            primary["rating"] = (g["rating"] * g["num_ratings"]).sum() / tot
            if "level_of_difficulty" in g.columns:
                diffs = pd.to_numeric(g["level_of_difficulty"], errors="coerce")
                if diffs.notna().any():
                    primary["level_of_difficulty"] = (diffs.fillna(0) * g["num_ratings"]).sum() / g.loc[diffs.notna(), "num_ratings"].sum()
            if "would_take_again_pct" in g.columns:
                wtas = g["would_take_again_pct"].astype(str).str.replace("%", "").replace("N/A", "nan").astype(float)
                if wtas.notna().any():
                    val = (wtas.fillna(0) * g["num_ratings"]).sum() / g.loc[wtas.notna(), "num_ratings"].sum()
                    primary["would_take_again_pct"] = f"{round(val, 1)}%"
        primary["num_ratings"] = tot
        primary["name"] = nk.title()
        rows.append(primary)
    return pd.DataFrame(rows).reset_index(drop=True)

rmp_profs = merge_rmp_aliases(rmp_profs)


# ──────────────────────────────────────────────
#  Friendly stat formatting:  round down then "+"
#    3863 → "3,800+",  42677 → "42,600+",  1234 → "1,200+"
# ──────────────────────────────────────────────
def friendly_count(n: int) -> str:
    if n < 100:
        return str(n)
    # Round down to nearest 100
    rounded = (n // 100) * 100
    return f"{rounded:,}+"


# ──────────────────────────────────────────────
#  Department → College mapping (NEU)
#  Exact match only — no substring matching
# ──────────────────────────────────────────────
COLLEGE_MAP = {
    # Khoury College of Computer Sciences
    "Computer Science":                   "Khoury",
    "Information Science":                "Khoury",
    "Information Systems":                "Khoury",
    "Computer & Informational Tech.":     "Khoury",
    "Computer amp Informational Tech.":   "Khoury",
    "Computer  Informational Tech.":      "Khoury",
    "Computer Engineering":               "Khoury",
    "Cybersecurity":                      "Khoury",
    "Data Science":                       "Khoury",
    "Computer Information Systm":         "Khoury",
    # College of Engineering
    "Engineering":                        "Engineering",
    "Electrical Engineering":             "Engineering",
    "Mechanical Engineering":             "Engineering",
    "Civil Engineering":                  "Engineering",
    "Chemical Engineering":               "Engineering",
    "Industrial Engineering":             "Engineering",
    "Materials Engineering":              "Engineering",
    "Engineering Technology":             "Engineering",
    "Electronics":                        "Engineering",
    "Electrical & Computer Engr":         "Engineering",
    "Mechanical & Industrial Eng":        "Engineering",
    "Civil & Environmental Eng":          "Engineering",
    "Bioengineering":                     "Engineering",
    "Industrial Technology":              "Engineering",
    # D'Amore-McKim School of Business
    "Business":                           "Business",
    "Business Administration":            "Business",
    "Finance":                            "Business",
    "Finance & Insurance":                "Business",
    "Accounting":                         "Business",
    "Accounting & Finance":               "Business",
    "Marketing":                          "Business",
    "Management":                         "Business",
    "Entrepreneurship":                   "Business",
    "International Business":             "Business",
    "Supply Chain Management":            "Business",
    "Operations Management":              "Business",
    "Managerial Science":                 "Business",
    "Organizational Behavior":            "Business",
    "Organizational Leadership":          "Business",
    "Human Resources Management":         "Business",
    "Leadership":                         "Business",
    # College of Science
    "Mathematics":                        "Science",
    "Physics":                            "Science",
    "Chemistry":                          "Science",
    "Biology":                            "Science",
    "Biochemistry":                       "Science",
    "Environmental Science":              "Science",
    "Environmental Studies":              "Science",
    "Marine Sciences":                    "Science",
    "Marine Biology":                     "Science",
    "Microbiology":                       "Science",
    "Biotechnology":                      "Science",
    "Geology":                            "Science",
    "Earth Science":                      "Science",
    "Biomedical":                         "Science",
    "Science":                            "Science",
    "Math":                               "Science",
    "Behavioral Neuroscience":            "Science",
    # College of Arts, Media and Design (CAMD)
    "Art":                                "CAMD",
    "Art History":                        "CAMD",
    "Architecture":                       "CAMD",
    "Communication Studies":              "CAMD",
    "Communication":                      "CAMD",
    "Communications":                     "CAMD",
    "Journalism":                         "CAMD",
    "Media":                              "CAMD",
    "Media Studies":                      "CAMD",
    "Graphic Design":                     "CAMD",
    "Design":                             "CAMD",
    "Music":                              "CAMD",
    "Music Technology":                   "CAMD",
    "Music Business":                     "CAMD",
    "Theater":                            "CAMD",
    "Game Design":                        "CAMD",
    "Fine Arts":                          "CAMD",
    "Visual Arts":                        "CAMD",
    "Cinema":                             "CAMD",
    "Photography":                        "CAMD",
    "Multimedia":                         "CAMD",
    "Creative Studies":                   "CAMD",
    # Bouvé College of Health Sciences
    "Health Science":                     "Health Sciences",
    "Health Sciences":                    "Health Sciences",
    "Nursing":                            "Health Sciences",
    "Pharmacy":                           "Health Sciences",
    "Physical Therapy":                   "Health Sciences",
    "Speech & Hearing Sciences":          "Health Sciences",
    "Speech Language Pathology":          "Health Sciences",
    "Health Management":                  "Health Sciences",
    "Health  Physical Education":         "Health Sciences",
    "Medicine":                           "Health Sciences",
    "Regulatory Affairs":                 "Health Sciences",
    "Counseling Psychology":              "Health Sciences",
    "Applied Psychology":                 "Health Sciences",
    # College of Social Sciences and Humanities (CSSH)
    "Political Science":                  "CSSH",
    "Economics":                          "CSSH",
    "History":                            "CSSH",
    "Psychology":                         "CSSH",
    "Sociology":                          "CSSH",
    "Philosophy":                         "CSSH",
    "English":                            "CSSH",
    "Writing":                            "CSSH",
    "Literature":                         "CSSH",
    "Linguistics":                        "CSSH",
    "Languages":                          "CSSH",
    "Modern Languages":                   "CSSH",
    "Spanish":                            "CSSH",
    "French":                             "CSSH",
    "Arabic":                             "CSSH",
    "Sign Language":                      "CSSH",
    "World Languages Center":             "CSSH",
    "Criminal Justice":                   "CSSH",
    "Anthropology":                       "CSSH",
    "Human Services":                     "CSSH",
    "Religious Studies":                  "CSSH",
    "Judaic Studies":                     "CSSH",
    "International Studies":              "CSSH",
    "International Affairs":              "CSSH",
    "International Politics":             "CSSH",
    "East Asian Studies":                 "CSSH",
    "Latin American Studies":             "CSSH",
    "African-American Studies":           "CSSH",
    "Women's Studies":                    "CSSH",
    "Women":                              "CSSH",
    "Social Science":                     "CSSH",
    "Public Policy":                      "CSSH",
    "Public Administration":              "CSSH",
    "Urban Studies":                      "CSSH",
    "Humanities":                         "CSSH",
    # College of Professional Studies
    "Education":                          "Professional Studies",
    "Professional Studies":               "Professional Studies",
    "Counseling & Educational Psych":     "Professional Studies",
    "Counseling amp Educational Psych":   "Professional Studies",
    "Counseling  Educational Psych":      "Professional Studies",
    # Law
    "Law":                                "Law",
}


def get_college(dept: str) -> str:
    if not isinstance(dept, str):
        return "Other"
    return COLLEGE_MAP.get(dept, "Other")


rmp_profs["college"] = rmp_profs["department"].apply(get_college)

# ──────────────────────────────────────────────
#  Build TRACE "overall" rating per instructor
# ──────────────────────────────────────────────
#  1. Build a lowercase full-name key in trace_courses
#  2. Get all courseIds + instructorIds per name
#  3. Filter trace_scores to "overall" questions
#  4. Compute weighted avg of mean scores (weighted by completed responses)
# ──────────────────────────────────────────────

# Normalise names for matching
trace_courses["_first"] = trace_courses["instructorFirstName"].apply(normalize_name)
trace_courses["_last"]  = trace_courses["instructorLastName"].apply(normalize_name)
trace_courses["_full"]  = (trace_courses["_first"] + " " + trace_courses["_last"]).apply(normalize_name)

# Build TRACE department lookup: use the most recent department per instructor
# (highest termId = most recent term)
trace_courses["termId"] = pd.to_numeric(trace_courses["termId"], errors="coerce")
_dept_sorted = trace_courses.sort_values("termId", ascending=False).drop_duplicates(subset=["_full"])
trace_dept_lookup = dict(zip(_dept_sorted["_full"], _dept_sorted["departmentName"]))

# Filter trace_scores to only rows whose question mentions "overall"
trace_scores["question"] = trace_scores["question"].astype(str)
overall_scores = trace_scores[
    trace_scores["question"].str.lower().str.contains("overall", na=False)
].copy()
overall_scores.dropna(subset=["mean"], inplace=True)

# Map courseId+instructorId → overall mean scores
# First get the set of (courseId, instructorId) per full name from trace_courses
instructor_courses = (
    trace_courses[["courseId", "instructorId", "_full"]]
    .drop_duplicates()
)

# Merge overall_scores with instructor_courses on courseId + instructorId
merged = overall_scores.merge(
    instructor_courses,
    on=["courseId", "instructorId"],
    how="inner",
)

# Weighted average per instructor name:
#   weight = _total_responses (actual number who answered the question)
#   value  = mean (computed from count_1..count_5)
def weighted_avg(group):
    w = group["_total_responses"]
    v = group["mean"]
    total_w = w.sum()
    if total_w == 0:
        return np.nan
    return (v * w).sum() / total_w

trace_avg_by_name = (
    merged
    .groupby("_full")
    .apply(weighted_avg, include_groups=False)
    .reset_index()
    .rename(columns={0: "trace_overall"})
)

# Build a lookup dict: lowercase full name → trace overall (1-5 scale)
trace_lookup = dict(zip(trace_avg_by_name["_full"], trace_avg_by_name["trace_overall"]))
print(f"[startup] Matched {len(trace_lookup)} instructors to TRACE overall scores")

# ──────────────────────────────────────────────
#  Build TRACE review count per instructor
# ──────────────────────────────────────────────
#  1. Get unique (courseId, instructorId, termId) combos from trace_courses per name
#  2. Match into trace_scores on (courseId, instructorId, termId)
#  3. Deduplicate: each (courseId, instructorId, termId) has many rows (one per question)
#     but `completed` is the same across all questions — take one row per combo
#  4. Sum `completed` across all combos for that instructor
# ──────────────────────────────────────────────

# Get unique course sections per instructor name
instructor_sections = (
    trace_courses[["courseId", "instructorId", "termId", "_full"]]
    .drop_duplicates(subset=["courseId", "instructorId", "termId"])
)

# Ensure trace_scores has numeric completed
trace_scores["completed"] = pd.to_numeric(trace_scores["completed"], errors="coerce")

# Deduplicate trace_scores to one row per (courseId, instructorId, termId)
# — all questions for the same section share the same `completed` count
scores_deduped = (
    trace_scores
    .drop_duplicates(subset=["courseId", "instructorId", "termId"])
    [["courseId", "instructorId", "termId", "completed"]]
)

# Merge with instructor names
trace_reviews_merged = scores_deduped.merge(
    instructor_sections,
    on=["courseId", "instructorId", "termId"],
    how="inner",
)

# Sum completed per instructor name
trace_review_counts = (
    trace_reviews_merged
    .groupby("_full")["completed"]
    .sum()
    .reset_index()
    .rename(columns={"completed": "trace_reviews"})
)

trace_reviews_lookup = dict(zip(trace_review_counts["_full"], trace_review_counts["trace_reviews"]))
print(f"[startup] Computed TRACE review counts for {len(trace_reviews_lookup)} instructors")

# ──────────────────────────────────────────────
#  Attach TRACE overall + avg rating + combined reviews to rmp_profs
# ──────────────────────────────────────────────
#  RMP rating is on a 1-5 scale.  TRACE mean is also 1-5.
#  Avg = average of both when TRACE is available,
#  otherwise fall back to just RMP.
#  Total reviews = RMP num_ratings + TRACE completed responses
# ──────────────────────────────────────────────
rmp_profs["_name_key"] = rmp_profs["name"].apply(normalize_name)

# Exact match first
rmp_profs["trace_overall"] = rmp_profs["_name_key"].map(trace_lookup)
rmp_profs["trace_reviews"] = rmp_profs["_name_key"].map(trace_reviews_lookup).fillna(0).astype(int)
rmp_profs["trace_dept"] = rmp_profs["_name_key"].map(trace_dept_lookup)

# Fallback match for unmatched: last name exact + first name prefix
# e.g. RMP "maria villar" → TRACE "maria elena villar"
trace_all_names = set(trace_lookup.keys())
trace_by_last = {}
for tn in trace_all_names:
    parts = tn.split()
    if len(parts) >= 2:
        last = parts[-1]
        trace_by_last.setdefault(last, []).append(tn)

unmatched = rmp_profs["trace_overall"].isna()
for idx in rmp_profs[unmatched].index:
    rmp_key = rmp_profs.at[idx, "_name_key"]
    rmp_parts = rmp_key.split()
    if len(rmp_parts) < 2:
        continue
    rmp_first = rmp_parts[0]
    rmp_last = rmp_parts[-1]

    candidates = trace_by_last.get(rmp_last, [])
    for tc_name in candidates:
        tc_first = tc_name.split()[0]
        # Match if either first name is a prefix of the other
        if tc_first.startswith(rmp_first) or rmp_first.startswith(tc_first):
            rmp_profs.at[idx, "trace_overall"] = trace_lookup.get(tc_name)
            rmp_profs.at[idx, "trace_reviews"] = trace_reviews_lookup.get(tc_name, 0)
            rmp_profs.at[idx, "trace_dept"] = trace_dept_lookup.get(tc_name)
            break

fallback_matched = unmatched.sum() - rmp_profs["trace_overall"].isna().sum()
print(f"[startup] Fallback matched {fallback_matched} additional professors")

rmp_profs["trace_reviews"] = rmp_profs["trace_reviews"].fillna(0).astype(int)
rmp_profs["total_reviews"] = rmp_profs["num_ratings"].astype(int) + rmp_profs["trace_reviews"]

def compute_avg_rating(r):
    has_rmp = r["num_ratings"] > 0 and r["rating"] > 0
    has_trace = pd.notna(r["trace_overall"]) and r["trace_reviews"] > 0

    if has_rmp and has_trace:
        return round((r["rating"] + r["trace_overall"]) / 2, 2)
    elif has_trace:
        return round(float(r["trace_overall"]), 2)
    elif has_rmp:
        return round(float(r["rating"]), 2)
    else:
        return 0.0

rmp_profs["avg_rating"] = rmp_profs.apply(compute_avg_rating, axis=1)

has_trace = rmp_profs["trace_overall"].notna().sum()
print(f"[startup] {has_trace}/{len(rmp_profs)} RMP professors matched to TRACE data")

# ──────────────────────────────────────────────
#  Precompute stats
# ──────────────────────────────────────────────

# Professors = unique names from BOTH RMP and TRACE (case-insensitive, already lowercase)
_all_prof_names = set(rmp_profs["_name_key"].unique())
_all_prof_names.update(trace_courses["_full"].unique())
# Strip any extra whitespace that might cause false duplicates
_all_prof_names = set(n.strip() for n in _all_prof_names if isinstance(n, str) and n.strip())
stat_professor_count = len(_all_prof_names)

# Courses = unique course codes (e.g. "ACCT6228"), case-insensitive
trace_courses["_course_code"] = trace_courses["displayName"].astype(str).str.split(":").str[0]
stat_course_count = trace_courses["_course_code"].str.upper().nunique()

# Comments = RMP reviews + TRACE comments
rmp_review_count = len(rmp_reviews)
trace_comment_count = len(trace_comments)
stat_total_comments = rmp_review_count + trace_comment_count

# Departments = unique department names, case-insensitive
stat_department_count = trace_courses["departmentName"].str.lower().str.strip().nunique()

print(f"[stats] {stat_professor_count} professors, {stat_course_count} courses, "
      f"{stat_total_comments} comments ({rmp_review_count} RMP + {trace_comment_count} TRACE), "
      f"{stat_department_count} departments")


# ──────────────────────────────────────────────
#  API Routes
# ──────────────────────────────────────────────
@app.route("/api/stats")
def stats():
    return jsonify([
        {"label": "Professors",  "value": friendly_count(stat_professor_count)},
        {"label": "Courses",     "value": friendly_count(stat_course_count)},
        {"label": "Comments", "value": friendly_count(stat_total_comments)},
        {"label": "Departments", "value": friendly_count(stat_department_count)},
    ])


@app.route("/api/colleges")
def colleges():
    counts = rmp_profs["college"].value_counts()
    college_list = sorted([c for c, n in counts.items() if n >= 5 and c != "Other"])
    return jsonify(college_list)


@app.route("/api/goat-professors")
def goat_professors():
    college     = request.args.get("college", "Khoury")
    limit       = min(int(request.args.get("limit", "10")), 50)
    min_reviews = int(request.args.get("min_reviews", "10"))

    # Small colleges get no minimum review requirement
    NO_MIN_COLLEGES = {"Law", "Professional Studies"}
    if college in NO_MIN_COLLEGES:
        min_reviews = 0

    subset = rmp_profs[rmp_profs["college"] == college].copy()
    if college in NO_MIN_COLLEGES:
        # Require at least 5 total reviews across both sources
        subset = subset[subset["total_reviews"] >= 5]
    else:
        subset = subset[
            (subset["num_ratings"] >= min_reviews) &
            (subset["trace_reviews"] >= min_reviews) &
            (subset["trace_overall"].notna())
        ]

    # Sort by avg_rating desc, then total_reviews desc as tiebreak
    subset = subset.sort_values(
        ["avg_rating", "total_reviews"], ascending=[False, False]
    )
    top = subset.head(limit)

    result = []
    for _, row in top.iterrows():
        has_rmp   = int(row["num_ratings"]) > 0 and row["rating"] > 0
        has_trace = pd.notna(row["trace_overall"]) and int(row["trace_reviews"]) > 0
        result.append({
            "name":           row["name"],
            "dept":           row["trace_dept"] if pd.notna(row["trace_dept"]) else row["department"],
            "rmpRating":      round(float(row["rating"]), 2) if has_rmp else None,
            "traceRating":    round(float(row["trace_overall"]), 2) if has_trace else None,
            "avgRating":  round(float(row["avg_rating"]), 2),
            "rmpReviews":     int(row["num_ratings"]),
            "traceReviews":   int(row["trace_reviews"]),
            "totalReviews":   int(row["total_reviews"]),
            "url":            row.get("professor_url", ""),
        })

    return jsonify(result)


@app.route("/api/random-professor")
def random_professor():
    pool = rmp_profs[rmp_profs["num_ratings"] >= 3]
    row = pool.sample(1).iloc[0]
    has_rmp   = int(row["num_ratings"]) > 0 and row["rating"] > 0
    has_trace = pd.notna(row["trace_overall"]) and int(row["trace_reviews"]) > 0
    return jsonify({
        "name":          row["name"],
        "dept":          row["trace_dept"] if pd.notna(row["trace_dept"]) else row["department"],
        "rmpRating":     round(float(row["rating"]), 2) if has_rmp else None,
        "traceRating":   round(float(row["trace_overall"]), 2) if has_trace else None,
        "avgRating": round(float(row["avg_rating"]), 2),
        "rmpReviews":    int(row["num_ratings"]),
        "traceReviews":  int(row["trace_reviews"]),
        "totalReviews":  int(row["total_reviews"]),
        "url":           row.get("professor_url", ""),
        "college":       row["college"],
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
        matches = _professor_search_matches(q).head(limit)

        results = []
        for _, r in matches.iterrows():
            results.append({
                "type":   "professor",
                "name":   r["name"],
                "dept":   r["dept_display"],
                "rating": round(float(r["avg_rating"]), 2) if r["avg_rating"] > 0 else None,
                "slug":   _name_to_slug(r["_name_key"]),
            })
        return jsonify(results)

    else:
        # Match courses: prioritize code prefix, then code contains, then name contains
        code_starts = course_search[course_search["_code"].str.lower().str.startswith(q, na=False)]
        code_contains = course_search[
            course_search["_code"].str.lower().str.contains(q, na=False) &
            ~course_search["_code"].str.lower().str.startswith(q, na=False)
        ]
        name_contains = course_search[
            course_search["_cname"].astype(str).str.lower().str.contains(q, na=False) &
            ~course_search["_code"].str.lower().str.contains(q, na=False)
        ]
        matches = pd.concat([code_starts, code_contains, name_contains]).head(limit)

        results = []
        for _, r in matches.iterrows():
            results.append({
                "type": "course",
                "code": r["_code"],
                "name": r["_cname"],
                "dept": r["departmentName"],
            })
        return jsonify(results)


# ──────────────────────────────────────────────
#  Professor page
# ──────────────────────────────────────────────

# Slug index: frontend generates slugs like "john-smith" from names
# This maps every slug back to the actual lowercase name key
def _name_to_slug(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

_slug_to_name = {}
for _, row in rmp_profs.iterrows():
    _slug_to_name[_name_to_slug(row["_name_key"])] = row["_name_key"]
for nk in trace_courses["_full"].unique():
    s = _name_to_slug(nk)
    if s not in _slug_to_name:
        _slug_to_name[s] = nk
for nk in prof_search["_name_lower"].values:
    s = _name_to_slug(nk)
    if s not in _slug_to_name:
        _slug_to_name[s] = nk

print(f"[prof-page] Slug index: {len(_slug_to_name)} unique slugs")

# Precompute review name keys
rmp_reviews["_rev_name_key"] = rmp_reviews["professor_name"].astype(str).str.strip().str.lower().str.replace(r'\s+', ' ', regex=True).replace(ALIAS_MAP)


# ──────────────────────────────────────────────
#  Build catalog DataFrame (all professors, for the browse page)
# ──────────────────────────────────────────────
def _build_catalog():
    rows = []
    rmp_name_keys = set(rmp_profs["_name_key"].values)

    # RMP professors (may also have TRACE data)
    for _, row in rmp_profs.iterrows():
        has_rmp   = int(row["num_ratings"]) > 0 and float(row["rating"]) > 0
        has_trace = pd.notna(row["trace_overall"]) and int(row["trace_reviews"]) > 0
        dept = str(row["trace_dept"]) if pd.notna(row["trace_dept"]) else str(row["department"])

        wta = None
        wta_raw = str(row.get("would_take_again_pct", "")).strip().replace("%", "")
        try:
            if wta_raw and wta_raw.lower() not in ("nan", "n/a", ""):
                wta = round(float(wta_raw), 1)
                if wta < 0:
                    wta = None
        except (ValueError, TypeError):
            pass

        avg = round(float(row["avg_rating"]), 2) if float(row["avg_rating"]) > 0 else None
        rows.append({
            "name":              row["name"],
            "slug":              _name_to_slug(row["_name_key"]),
            "department":        dept,
            "college":           row["college"],
            "avgRating":         avg,
            "rmpRating":         round(float(row["rating"]), 2) if has_rmp else None,
            "traceRating":       round(float(row["trace_overall"]), 2) if has_trace else None,
            "totalReviews":      int(row["total_reviews"]),
            "wouldTakeAgainPct": wta,
            "imageUrl":          photo_lookup.get(row["_name_key"], None),
            "_name_lower":       row["_name_key"],
        })

    # TRACE-only professors (not in RMP)
    for _, row in trace_only.iterrows():
        nk = row["_name_lower"]
        if nk in rmp_name_keys:
            continue
        dept = str(row["dept_display"]) if pd.notna(row["dept_display"]) else ""
        trace_rat = trace_lookup.get(nk)
        has_trace = trace_rat is not None and pd.notna(trace_rat)
        avg = round(float(trace_rat), 2) if has_trace else None
        rows.append({
            "name":              row["name"],
            "slug":              _name_to_slug(nk),
            "department":        dept,
            "college":           get_college(dept),
            "avgRating":         avg,
            "rmpRating":         None,
            "traceRating":       avg,
            "totalReviews":      int(row["total_reviews"]),
            "wouldTakeAgainPct": None,
            "imageUrl":          photo_lookup.get(nk, None),
            "_name_lower":       nk,
        })

    return pd.DataFrame(rows)


catalog_df = _build_catalog()
print(f"[catalog] Built catalog with {len(catalog_df)} professors")


def _resolve_slug(slug):
    nk = _slug_to_name.get(slug)
    return nk if nk else slug.strip().lower().replace("-", " ")


@app.route("/api/professors/<slug>")
def professor_profile(slug):
    name_key = _resolve_slug(slug)
    profile = None

    # Try RMP
    rmp_match = rmp_profs[rmp_profs["_name_key"] == name_key]
    if not rmp_match.empty:
        row = rmp_match.iloc[0]
        has_rmp = int(row["num_ratings"]) > 0 and row["rating"] > 0
        has_trace = pd.notna(row["trace_overall"]) and int(row["trace_reviews"]) > 0

        wta = None
        if "would_take_again_pct" in row.index:
            raw_val = str(row["would_take_again_pct"]).strip().replace("%", "")
            try:
                val = float(raw_val)
                if pd.notna(val) and val >= 0:
                    wta = val
            except (ValueError, TypeError):
                pass

        difficulty = None
        if "level_of_difficulty" in row.index:
            try:
                val = float(row["level_of_difficulty"])
                if pd.notna(val) and val > 0:
                    difficulty = val
            except (ValueError, TypeError):
                pass

        profile = {
            "name": row["name"],
            "department": row["trace_dept"] if pd.notna(row["trace_dept"]) else row["department"],
            "rmpRating": round(float(row["rating"]), 2) if has_rmp else None,
            "traceRating": round(float(row["trace_overall"]), 2) if has_trace else None,
            "avgRating": round(float(row["avg_rating"]), 2),
            "numRatings": int(row["num_ratings"]),
            "wouldTakeAgainPct": round(wta, 1) if wta is not None else None,
            "difficulty": round(difficulty, 2) if difficulty is not None else None,
            "totalRatings": int(row["total_reviews"]),
            "professorUrl": row.get("professor_url", None) or None,
        }

    # Try TRACE-only
    elif not trace_courses[trace_courses["_full"] == name_key].empty:
        trace_rating = trace_lookup.get(name_key)
        trace_rev = trace_reviews_lookup.get(name_key, 0)
        dept = trace_dept_lookup.get(name_key, "")
        profile = {
            "name": name_key.title(),
            "department": dept,
            "rmpRating": None,
            "traceRating": round(float(trace_rating), 2) if trace_rating and pd.notna(trace_rating) else None,
            "avgRating": round(float(trace_rating), 2) if trace_rating and pd.notna(trace_rating) else 0.0,
            "numRatings": 0,
            "wouldTakeAgainPct": None,
            "difficulty": None,
            "totalRatings": int(trace_rev),
            "professorUrl": None,
        }

    if profile is None:
        return jsonify({"error": "Professor not found"}), 404

    # --- Professor photo ---
    profile["imageUrl"] = photo_lookup.get(name_key, None)

    # --- TRACE courses + scores ---
    tc = trace_courses[trace_courses["_full"] == name_key]
    trace_course_list = []
    for _, c in tc.iterrows():
        cid = int(c["courseId"])
        iid = int(c["instructorId"])
        tid = int(c["termId"]) if pd.notna(c["termId"]) else 0
        section_scores = trace_scores[
            (trace_scores["courseId"] == cid) &
            (trace_scores["instructorId"] == iid) &
            (trace_scores["termId"] == tid)
        ]
        scores_list = []
        for _, s in section_scores.iterrows():
            scores_list.append({
                "question": str(s["question"]),
                "mean": round(float(s["mean"]), 2) if pd.notna(s["mean"]) else 0,
                "median": round(float(s["median"]), 2) if pd.notna(s["median"]) else 0,
                "stdDev": round(float(s["std_dev"]), 2) if pd.notna(s["std_dev"]) else 0,
                "enrollment": int(s["enrollment"]) if pd.notna(s["enrollment"]) else 0,
                "completed": int(s["completed"]) if pd.notna(s["completed"]) else 0,
                "totalResponses": int(s["_total_responses"]) if pd.notna(s["_total_responses"]) else 0,
                "count1": int(s["count_1"]) if pd.notna(s["count_1"]) else 0,
                "count2": int(s["count_2"]) if pd.notna(s["count_2"]) else 0,
                "count3": int(s["count_3"]) if pd.notna(s["count_3"]) else 0,
                "count4": int(s["count_4"]) if pd.notna(s["count_4"]) else 0,
                "count5": int(s["count_5"]) if pd.notna(s["count_5"]) else 0,
            })
        trace_course_list.append({
            "courseId": cid, "termId": tid,
            "termTitle": str(c["termTitle"]) if pd.notna(c["termTitle"]) else "",
            "departmentName": str(c["departmentName"]) if pd.notna(c["departmentName"]) else "",
            "displayName": str(c["displayName"]) if pd.notna(c["displayName"]) else "",
            "section": str(c["section"]) if pd.notna(c["section"]) else "",
            "enrollment": int(c["enrollment"]) if pd.notna(c["enrollment"]) else 0,
            "scores": scores_list,
        })
    trace_course_list.sort(key=lambda x: x["termId"], reverse=True)
    profile["traceCourses"] = trace_course_list

    # --- RMP reviews ---
    rev_matches = rmp_reviews[rmp_reviews["_rev_name_key"] == name_key]
    reviews = []
    for _, r in rev_matches.iterrows():
        reviews.append({
            "professorName": str(r["professor_name"]),
            "department": str(r["department"]) if pd.notna(r["department"]) else "",
            "overallRating": float(r["overall_rating"]) if pd.notna(r["overall_rating"]) else 0,
            "course": str(r["course"]) if pd.notna(r["course"]) else "",
            "quality": int(r["quality"]) if pd.notna(r["quality"]) else 0,
            "difficulty": int(r["difficulty"]) if pd.notna(r["difficulty"]) else 0,
            "date": str(r["date"]) if pd.notna(r["date"]) else "",
            "tags": str(r["tags"]) if pd.notna(r["tags"]) else "",
            "attendance": str(r["attendance"]) if pd.notna(r["attendance"]) else "",
            "grade": str(r["grade"]) if pd.notna(r["grade"]) else "",
            "textbook": str(r["textbook"]) if pd.notna(r["textbook"]) else "",
            "online_class": str(r["online_class"]) if pd.notna(r["online_class"]) else "",
            "comment": sanitize(r["comment"]) if pd.notna(r["comment"]) else "",
        })
    profile["reviews"] = reviews

    # --- TRACE comments ---
    url_patterns = set()
    for _, c in tc.iterrows():
        cid = str(int(c["courseId"]))
        iid = str(int(c["instructorId"]))
        tid = str(int(c["termId"])) if pd.notna(c["termId"]) else ""
        url_patterns.add(f"sp={cid}&sp={iid}&sp={tid}")

    if url_patterns:
        mask = trace_comments["course_url"].apply(
            lambda url: isinstance(url, str) and any(pat in url for pat in url_patterns)
        )
        matching = trace_comments[mask]
        comments = []
        for _, c in matching.iterrows():
            comment_text = sanitize(c["comment"]) if pd.notna(c["comment"]) else ""
            if not comment_text.strip():
                continue
            
            # Extract termId from URL for sorting: sp=105528&sp=1158&sp=198 -> last sp is tid
            url = str(c["course_url"]) if pd.notna(c["course_url"]) else ""
            term_id = 0
            try:
                # Find all sp= values
                sp_matches = re.findall(r"sp=(\d+)", url)
                if len(sp_matches) >= 3:
                    term_id = int(sp_matches[2])
            except (ValueError, IndexError):
                pass

            comments.append({
                "courseUrl": url,
                "question": str(c["question"]) if pd.notna(c["question"]) else "",
                "comment": comment_text,
                "termId": term_id
            })
        profile["traceComments"] = comments
    else:
        profile["traceComments"] = []

    return jsonify(profile)


@app.route("/api/departments")
def departments():
    college = request.args.get("college", "")
    # Keep department options aligned with the catalog: only rated professors are visible.
    rated_subset = catalog_df[catalog_df["avgRating"].notna()]
    if college and college != "All":
        subset = rated_subset[rated_subset["college"] == college]
    else:
        subset = rated_subset
    depts = sorted(subset["department"].dropna().unique().tolist())
    return jsonify(depts)


@app.route("/api/professors-catalog")
def professors_catalog():
    q          = normalize_name(request.args.get("q", ""))
    college    = request.args.get("college", "")
    dept       = request.args.get("dept", "")
    sort       = request.args.get("sort", "alpha")
    page       = int(request.args.get("page", "1"))
    limit      = min(int(request.args.get("limit", "20")), 10000)

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

    # Always exclude professors with no rating data
    subset = catalog_df[catalog_df["avgRating"].notna()].copy()

    if college and college != "All":
        subset = subset[subset["college"] == college]
    if dept and dept != "All":
        subset = subset[subset["department"] == dept]
    if q:
        if len(q) >= 2:
            matched_name_keys = set(_professor_search_matches(q)["_name_lower"].tolist())
            subset = subset[subset["_name_lower"].isin(matched_name_keys)]
        else:
            subset = subset[subset["_name_lower"].str.contains(q, na=False)]
    if min_rating > 0:
        subset = subset[subset["avgRating"] >= min_rating]
    if max_rating < 5:
        subset = subset[subset["avgRating"] <= max_rating]
    if min_reviews > 1:
        subset = subset[subset["totalReviews"] >= min_reviews]
    if max_reviews is not None:
        subset = subset[subset["totalReviews"] <= max_reviews]

    if sort == "rating":
        subset = subset.sort_values("avgRating", ascending=False, na_position="last")
    elif sort == "reviews":
        subset = subset.sort_values("totalReviews", ascending=False)
    else:  # alpha
        subset = subset.sort_values(
            "name", ascending=True, key=lambda s: s.str.lower()
        )

    total = len(subset)
    total_pages = max(1, (total + limit - 1) // limit)
    page = max(1, min(page, total_pages))
    start = (page - 1) * limit
    page_data = subset.iloc[start : start + limit]

    professors = []
    for _, row in page_data.iterrows():
        professors.append({
            "name":              row["name"],
            "slug":              row["slug"],
            "department":        row["department"],
            "college":           row["college"],
            "avgRating":         float(row["avgRating"]) if pd.notna(row["avgRating"]) else None,
            "rmpRating":         float(row["rmpRating"]) if pd.notna(row["rmpRating"]) else None,
            "traceRating":       float(row["traceRating"]) if pd.notna(row["traceRating"]) else None,
            "totalReviews":      int(row["totalReviews"]),
            "wouldTakeAgainPct": float(row["wouldTakeAgainPct"]) if pd.notna(row["wouldTakeAgainPct"]) else None,
            "imageUrl":          row["imageUrl"] if pd.notna(row.get("imageUrl")) else None,
        })

    return jsonify({
        "professors": professors,
        "total":      total,
        "page":       page,
        "totalPages": total_pages,
    })


# ──────────────────────────────────────────────
#  Google OAuth routes
# ──────────────────────────────────────────────

def _get_redirect_uri():
    return request.host_url.rstrip("/") + "/api/auth/google/callback"


@app.route("/api/auth/google")
@limiter.limit("10 per minute")
def auth_google():
    """Redirect user to Google's consent screen (restricted to husky.neu.edu)."""
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
    resp.set_cookie("auth_return_to", return_to, max_age=600, httponly=True, samesite="Lax")
    if is_popup:
        resp.set_cookie("auth_popup", "1", max_age=600, httponly=True, samesite="Lax")
    return resp


@app.route("/api/auth/google/callback")
@limiter.limit("10 per minute")
def auth_google_callback():
    """Exchange auth code for tokens, verify domain, set JWT cookie."""
    code = request.args.get("code")
    if not code:
        return redirect(f"{FRONTEND_URL}?auth_error=no_code")

    # Exchange code for tokens
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

    # Fetch user info
    user_resp = http_requests.get(GOOGLE_USERINFO_URL, headers={
        "Authorization": f"Bearer {access_token}",
    })
    if user_resp.status_code != 200:
        return redirect(f"{FRONTEND_URL}?auth_error=userinfo_failed")

    user_info = user_resp.json()

    # Restrict to husky.neu.edu
    if user_info.get("hd") != "husky.neu.edu":
        return redirect(f"{FRONTEND_URL}?auth_error=invalid_domain")

    # Create JWT
    payload = {
        "sub": user_info["id"],
        "email": user_info["email"],
        "name": user_info.get("name", ""),
        "picture": user_info.get("picture", ""),
        "exp": datetime.now(timezone.utc) + timedelta(days=7),
    }
    token = pyjwt.encode(payload, JWT_SECRET, algorithm="HS256")

    # Set auth cookie
    is_popup = request.cookies.get("auth_popup") == "1"

    if is_popup:
        # Close popup and notify opener
        resp = make_response("""
        <html><body><script>
          window.opener && window.opener.postMessage("auth_complete", "*");
          window.close();
        </script></body></html>
        """)
        resp.delete_cookie("auth_popup")
    else:
        # Fallback: redirect to the page the user was on
        return_to = request.cookies.get("auth_return_to", "/")
        from urllib.parse import urlparse
        parsed = urlparse(return_to)
        if parsed.scheme or parsed.netloc or not return_to.startswith("/"):
            return_to = "/"
        resp = make_response(redirect(f"{FRONTEND_URL}{return_to}"))
        resp.delete_cookie("auth_return_to")

    resp.set_cookie(
        "auth_token",
        token,
        httponly=True,
        samesite="Lax",
        max_age=7 * 24 * 3600,
        secure=request.scheme == "https",
    )
    return resp


@app.route("/api/auth/me")
@limiter.limit("30 per minute")
def auth_me():
    """Return current user from JWT cookie, or 401."""
    token = request.cookies.get("auth_token")
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
    """Clear the auth cookie."""
    origin = request.headers.get("Origin", "")
    if origin and origin != FRONTEND_URL:
        return jsonify({"error": "forbidden"}), 403
    resp = make_response(jsonify({"ok": True}))
    resp.delete_cookie("auth_token")
    return resp


if __name__ == "__main__":
    print(f"Loaded {len(rmp_profs)} RMP professors, {len(rmp_reviews)} RMP reviews")
    print(f"Stats → {stat_professor_count} professors, {stat_course_count} courses, "
          f"{stat_total_comments} comments, {stat_department_count} departments")
    app.run(debug=True, port=5001, use_reloader=True)