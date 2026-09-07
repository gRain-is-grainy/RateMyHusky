"""Builds the labeling pool for the RAG retrieval eval.

--validate  checks eval_questions.json against the live DB (entities exist, evidence depth).
--run       (Task 5) snapshots top-20 lexical + top-20 vector candidates per unit into pool.json.
"""
import sys, argparse, collections, datetime

from eval_common import (connect, make_query_fns, unit_id, entity_args,
                         load_json, save_json_atomic, git_sha,
                         QUESTIONS_PATH, POOL_PATH)
from rag.chat_retrieve import _entity_filter, _lexical_candidates, _vector_candidates, fetch_evidence

EXPECTED_MODES = {"professor": 29, "course": 20, "compare": 6}
MIN_EVIDENCE = 20
WARN_EVIDENCE = 40
POOL_DEPTH = 20


def build_unit_pool(question_id, question, entity, query_fn, embed_fn, fetch_evidence_fn):
    slug, code = entity_args(entity)
    where, params = _entity_filter(slug, code)
    lex = [(str(i), s) for i, s in _lexical_candidates(where, params, question, query_fn, limit=POOL_DEPTH)]
    qv = embed_fn(question)
    if qv is None:
        sys.exit(f"{question_id}: query embedding failed — a lexical-only pool would bias the "
                 "labels; fix the embedder (HF cache present?) and re-run")
    vec = [(str(i), s) for i, s in _vector_candidates(where, params, qv, query_fn, limit=POOL_DEPTH)]
    top8 = [str(c["source_id"]) for c in fetch_evidence_fn(slug, code, question, embed_fn, query_fn, limit=8)]

    lex_rank = {i: n for n, (i, _) in enumerate(lex, 1)}
    vec_rank = {i: n for n, (i, _) in enumerate(vec, 1)}
    # union, ordered: lexical first, then vector-only, then top8-only stragglers (an item
    # ranked 21-40 in BOTH lists can still make the production RRF top-8)
    ordered = [i for i, _ in lex] + [i for i, _ in vec if i not in lex_rank] \
              + [i for i in top8 if i not in lex_rank and i not in vec_rank]
    if not ordered:
        return {"question_id": question_id, "question": question, "entity": entity,
                "candidates": []}
    rows = query_fn(
        "SELECT id, source, source_ref, professor_slug, course_code, body_sha, body "
        "FROM evidence WHERE id IN %s", (tuple(ordered),))
    by_id = {str(r["id"]): r for r in rows}
    candidates = []
    for i in ordered:
        r = by_id.get(i)
        if not r:
            continue
        candidates.append({
            "evidence_id": i, "source": r["source"], "source_ref": r["source_ref"],
            "professor_slug": r.get("professor_slug"), "course_code": r.get("course_code") or "",
            "body_sha": r.get("body_sha"), "body": r.get("body") or "",
            "lex_rank": lex_rank.get(i), "vec_rank": vec_rank.get(i),
            "in_top8": i in set(top8)})
    return {"question_id": question_id, "question": question, "entity": entity,
            "candidates": candidates}


def build_pool(questions, query_fn):
    from rag.query_embedder import embed_query
    units = {}
    for q in questions:
        for entity in q["entities"]:
            uid = unit_id(q["id"], entity)
            units[uid] = build_unit_pool(q["id"], q["question"], entity,
                                         query_fn, embed_query, fetch_evidence)
            print(f"  {uid}: {len(units[uid]['candidates'])} candidates")
    pool = {"built_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "git_sha": git_sha(), "pool_depth": POOL_DEPTH, "units": units}
    save_json_atomic(POOL_PATH, pool)
    total = sum(len(u["candidates"]) for u in units.values())
    print(f"wrote {POOL_PATH}: {len(units)} units, {total} candidates")
    return 0


def _evidence_count(entity, query_fn):
    slug, code = entity_args(entity)
    if slug:
        row = query_fn("SELECT count(*) AS c FROM evidence WHERE professor_slug = %s AND flagged = false", (slug,))
    else:
        row = query_fn("SELECT count(*) AS c FROM evidence WHERE course_code = %s AND flagged = false", (code,))
    return row[0]["c"] if row else 0


def validate_questions(questions, query_fn):
    problems = []
    ids = [q.get("id") for q in questions]
    if len(ids) != len(set(ids)):
        problems.append("duplicate question ids")
    modes = collections.Counter(q.get("mode") for q in questions)
    if dict(modes) != EXPECTED_MODES:
        problems.append(f"mode mix {dict(modes)} != expected {EXPECTED_MODES}")
    for q in questions:
        qid = q.get("id", "?")
        ents = q.get("entities") or []
        want = 2 if q.get("mode") == "compare" else 1
        if len(ents) != want:
            problems.append(f"{qid}: expected {want} entities, got {len(ents)}")
        if not (q.get("question") or "").strip().endswith("?"):
            problems.append(f"{qid}: question must be a question")
        for e in ents:
            slug, code = entity_args(e)
            if bool(slug) == bool(code):
                problems.append(f"{qid}: entity needs exactly one of slug/code")
                continue
            if slug and not query_fn("SELECT 1 FROM professors_catalog WHERE slug = %s", (slug,)):
                problems.append(f"{qid}: unknown professor slug {slug}")
            elif code and not query_fn("SELECT 1 FROM course_catalog WHERE code = %s", (code,)):
                problems.append(f"{qid}: unknown course code {code}")
            else:
                n = _evidence_count(e, query_fn)
                if n < MIN_EVIDENCE:
                    problems.append(f"{qid}: {slug or code} has only {n} evidence rows (<{MIN_EVIDENCE})")
                elif n < WARN_EVIDENCE:
                    print(f"  warn: {qid}: {slug or code} has {n} evidence rows (<{WARN_EVIDENCE})")
    return problems


def main():
    p = argparse.ArgumentParser(description="RAG eval pool builder.")
    p.add_argument("--validate", action="store_true")
    p.add_argument("--run", action="store_true")
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args()
    if args.selftest:
        sys.exit(selftest())
    questions = load_json(QUESTIONS_PATH, None)
    if questions is None:
        sys.exit(f"missing {QUESTIONS_PATH}")
    conn = connect()
    query_fn, _ = make_query_fns(conn)
    if args.validate:
        problems = validate_questions(questions, query_fn)
        for pr in problems:
            print("PROBLEM: " + pr)
        print("VALID" if not problems else f"{len(problems)} problem(s)")
        sys.exit(1 if problems else 0)
    if args.run:
        sys.exit(build_pool(questions, query_fn))
    print("use --validate or --run")


def selftest():
    fails = []
    def check(label, cond):
        if not cond: fails.append(label)
        print(("PASS" if cond else "FAIL") + ": " + label)

    def fake_query(sql, params):
        if "professors_catalog" in sql:
            return [{"1": 1}] if params[0] == "real-prof" else []
        if "course_catalog" in sql:
            return [{"1": 1}] if params[0] == "CS3500" else []
        if "count(*)" in sql:
            return [{"c": 55}]
        return []

    good = ([{"id": f"p{i:02d}", "mode": "professor", "question": "Is X hard?",
              "entities": [{"kind": "professor", "slug": "real-prof"}]} for i in range(EXPECTED_MODES["professor"])]
            + [{"id": f"c{i:02d}", "mode": "course", "question": "Is Y hard?",
                "entities": [{"kind": "course", "code": "CS3500"}]} for i in range(EXPECTED_MODES["course"])]
            + [{"id": f"x{i:02d}", "mode": "compare", "question": "X or Y?",
                "entities": [{"kind": "professor", "slug": "real-prof"},
                             {"kind": "course", "code": "CS3500"}]} for i in range(EXPECTED_MODES["compare"])])
    check("valid set passes", validate_questions(good, fake_query) == [])

    bad = [dict(good[0], id=good[1]["id"])] + good[1:]
    check("duplicate ids caught", any("duplicate" in p for p in validate_questions(bad, fake_query)))
    bad2 = [dict(good[0], entities=[{"kind": "professor", "slug": "ghost"}])] + good[1:]
    check("unknown slug caught", any("unknown professor" in p for p in validate_questions(bad2, fake_query)))
    bad3 = [dict(good[0], mode="compare")] + good[1:]
    probs3 = validate_questions(bad3, fake_query)
    check("mode-mix and entity-count caught", any("mode mix" in p for p in probs3)
          and any("expected 2 entities" in p for p in probs3))

    # ── build_unit_pool: 20+20 union + production top-8 flags ──
    def fake_embed(text):
        return [0.1, 0.2]
    def pool_query(sql, params):
        if "plainto_tsquery" in sql:
            return [{"id": "L1", "r": 0.9}, {"id": "B1", "r": 0.5}]
        if "evidence_embeddings" in sql:
            return [{"id": "V1", "sim": 0.8}, {"id": "B1", "sim": 0.6}]
        if "WHERE id IN" in sql and "body" in sql:
            ids = set(params[0])
            rows = {"L1": "lex only", "B1": "both", "V1": "vec only", "S1": "top8 straggler"}
            return [{"id": i, "source": "trace", "source_ref": f"ref-{i}",
                     "professor_slug": "guha", "course_code": "", "body_sha": f"sha-{i}",
                     "body": rows[i]} for i in rows if i in ids]
        return []
    def fake_fetch_evidence(slug, code, q, embed_fn, query_fn, limit=8):
        return [{"source_id": "L1"}, {"source_id": "S1"}]  # S1 not in either top-20 list
    unit = build_unit_pool("p01", "is guha hard", {"kind": "professor", "slug": "guha"},
                           pool_query, fake_embed, fake_fetch_evidence)
    by_id = {c["evidence_id"]: c for c in unit["candidates"]}
    check("pool unions lexical+vector+top8", set(by_id) == {"L1", "B1", "V1", "S1"})
    check("lex_rank recorded", by_id["L1"]["lex_rank"] == 1 and by_id["L1"]["vec_rank"] is None)
    check("both-lists candidate has both ranks", by_id["B1"]["lex_rank"] == 2 and by_id["B1"]["vec_rank"] == 2)
    check("top8-only straggler pooled with null ranks",
          by_id["S1"]["lex_rank"] is None and by_id["S1"]["vec_rank"] is None and by_id["S1"]["in_top8"])
    check("in_top8 flags exactly the production picks",
          {i for i, c in by_id.items() if c["in_top8"]} == {"L1", "S1"})
    check("candidates carry natural key + body", by_id["V1"]["source_ref"] == "ref-V1"
          and by_id["V1"]["body"] == "vec only" and by_id["V1"]["body_sha"] == "sha-V1")

    # ── Finding 1: an all-empty union must not render "WHERE id IN ()" (syntax error) ──
    calls = []
    def empty_query(sql, params):
        calls.append((sql, params))
        return []
    def empty_fetch_evidence(slug, code, q, embed_fn, query_fn, limit=8):
        return []
    empty_unit = build_unit_pool("p02", "is nobody hard", {"kind": "professor", "slug": "nobody"},
                                 empty_query, fake_embed, empty_fetch_evidence)
    check("all-empty union returns unit with empty candidates", empty_unit["candidates"] == [])
    check("all-empty union issues no WHERE-id-IN-empty-tuple hydrate query",
          not any("WHERE id IN" in sql and params == (tuple(),) for sql, params in calls))

    print("ALL PASS" if not fails else f"{len(fails)} FAIL(s): " + ", ".join(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    main()
