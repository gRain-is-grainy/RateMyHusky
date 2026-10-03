"""Local-only labeling + grading UI for the RAG evals (ask_admin.py pattern — never deployed).

Labeling: shows one pooled evidence candidate at a time per unit; keys 0/1/2 label-and-advance,
u undoes. Labels append to qrels.json (atomic write per keypress).
Grading (Task 9): grade generation-run answers into runs/<run>/grades.json.

Run: python backend/rag/eval/eval_ui.py -> http://127.0.0.1:5052
"""
import os, sys, argparse

from eval_common import (load_json, save_json_atomic,
                         QRELS_PATH, POOL_PATH, RUNS_DIR, EVAL_DIR)

def is_safe_run_name(run):
    """Reject a run name that could escape RUNS_DIR via path traversal — the grading routes
    take `run` straight from the URL path (<path:run>) and os.path.join it into RUNS_DIR, so
    something like '../../etc' must be refused rather than resolved."""
    if not run or os.path.sep in run or (os.path.altsep and os.path.altsep in run) or ".." in run:
        return False
    base = os.path.realpath(RUNS_DIR)
    candidate = os.path.realpath(os.path.join(RUNS_DIR, run))
    return candidate == base or candidate.startswith(base + os.path.sep)

RUBRIC = {0: "doesn't help answer this question",
          1: "tangentially useful (right entity, adjacent topic)",
          2: "directly supports an answer"}


def labeled_ids(qrels, uid):
    return {l["evidence_id"] for l in qrels.get(uid, {}).get("labels", [])}


def next_candidate(pool_unit, qrels, uid):
    done = labeled_ids(qrels, uid)
    for c in pool_unit["candidates"]:
        if c["evidence_id"] not in done:
            return c
    return None


def record_label(qrels, uid, entity, cand, rel):
    if rel not in (0, 1, 2):
        raise ValueError("rel must be 0, 1, or 2")
    unit = qrels.setdefault(uid, {"entity": entity, "labels": []})
    if cand["evidence_id"] in {l["evidence_id"] for l in unit["labels"]}:
        return  # idempotent: double-post of the same candidate is a no-op
    unit["labels"].append({
        "evidence_id": cand["evidence_id"], "source": cand["source"],
        "source_ref": cand["source_ref"], "professor_slug": cand.get("professor_slug"),
        "course_code": cand.get("course_code") or "", "body_sha": cand.get("body_sha"),
        "rel": rel})


def undo_label(qrels, uid):
    labels = qrels.get(uid, {}).get("labels", [])
    return labels.pop() if labels else None


def unit_progress(pool, qrels):
    out = []
    for uid, unit in pool.get("units", {}).items():
        out.append({"unit_id": uid, "question": unit["question"],
                    "total": len(unit["candidates"]),
                    "labeled": len(labeled_ids(qrels, uid))})
    return out


def next_ungraded(answers, grades):
    # failing deterministic checks first (stable within groups), then file order
    ordered = sorted(answers, key=lambda a: a.get("checks_passed", True))
    for a in ordered:
        if a["question_id"] not in grades:
            return a
    return None


def grade_summary(grades):
    vals = list(grades.values())
    if not vals:
        return {"graded": 0, "mean_faithfulness": None, "pct_fully_grounded": None,
                "mean_relevance": None, "citation_precision": None}
    cits = [ok for g in vals for ok in g.get("citations", {}).values()]
    return {"graded": len(vals),
            "mean_faithfulness": sum(g["faithfulness"] for g in vals) / len(vals),
            "pct_fully_grounded": sum(1 for g in vals if g["faithfulness"] == 2) / len(vals),
            "mean_relevance": sum(g["relevance"] for g in vals) / len(vals),
            "citation_precision": (sum(cits) / len(cits)) if cits else None}


def selftest():
    fails = []
    def check(label, cond):
        if not cond: fails.append(label)
        print(("PASS" if cond else "FAIL") + ": " + label)

    cand = lambda i: {"evidence_id": i, "source": "rmp", "source_ref": f"ref-{i}",
                      "professor_slug": "guha", "course_code": "", "body_sha": f"sha-{i}",
                      "body": f"body {i}"}
    pool_unit = {"question": "q?", "candidates": [cand("a"), cand("b")]}
    qrels = {}
    ent = {"kind": "professor", "slug": "guha"}

    check("first unlabeled is a", next_candidate(pool_unit, qrels, "u1")["evidence_id"] == "a")
    record_label(qrels, "u1", ent, cand("a"), 2)
    check("label recorded with natural key + rel",
          qrels["u1"]["labels"][0]["rel"] == 2 and qrels["u1"]["labels"][0]["source_ref"] == "ref-a")
    check("label never stores the body", "body" not in qrels["u1"]["labels"][0])
    check("advances to b", next_candidate(pool_unit, qrels, "u1")["evidence_id"] == "b")
    record_label(qrels, "u1", ent, cand("a"), 0)
    check("double-label same candidate is a no-op", len(qrels["u1"]["labels"]) == 1)
    try:
        record_label(qrels, "u1", ent, cand("b"), 5); bad = False
    except ValueError:
        bad = True
    check("rel outside 0-2 rejected", bad)
    popped = undo_label(qrels, "u1")
    check("undo pops the last label", popped["evidence_id"] == "a" and qrels["u1"]["labels"] == [])
    check("undo on empty returns None", undo_label(qrels, "u1") is None)
    record_label(qrels, "u1", ent, cand("a"), 1)
    prog = unit_progress({"units": {"u1": pool_unit}}, qrels)
    check("progress counts", prog[0]["labeled"] == 1 and prog[0]["total"] == 2)

    # ── grading helpers ──
    answers = [{"question_id": "p01", "answer": "x [1]", "checks_passed": True},
               {"question_id": "p02", "answer": "y", "checks_passed": True}]
    grades = {}
    check("next ungraded is first", next_ungraded(answers, grades)["question_id"] == "p01")
    grades["p01"] = {"faithfulness": 2, "relevance": 1, "citations": {"1": True, "2": False}, "note": ""}
    check("advances past graded", next_ungraded(answers, grades)["question_id"] == "p02")
    grades["p02"] = {"faithfulness": 1, "relevance": 2, "citations": {}, "note": "meh"}
    check("all graded -> None", next_ungraded(answers, grades) is None)
    # deterministic-check failures grade FIRST (spec: failures listed first in the grading UI)
    mixed = [{"question_id": "g1", "checks_passed": True},
             {"question_id": "g2", "checks_passed": False}]
    check("failing answers surface first", next_ungraded(mixed, {})["question_id"] == "g2")
    s = grade_summary(grades)
    check("summary means", s["mean_faithfulness"] == 1.5 and s["mean_relevance"] == 1.5)
    check("summary pct fully grounded", s["pct_fully_grounded"] == 0.5)
    check("summary citation precision 1/2", s["citation_precision"] == 0.5)
    check("summary graded count", s["graded"] == 2)
    s0 = grade_summary({})
    check("empty summary has None means", s0["mean_faithfulness"] is None and s0["graded"] == 0)

    # ── path-traversal guard for the grading routes ──
    check("plain run name accepted", is_safe_run_name("2026-07-28-1200-baseline") is True)
    check("dotdot traversal rejected", is_safe_run_name("../../etc/passwd") is False)
    check("forward slash rejected", is_safe_run_name("foo/bar") is False)
    check("backslash rejected", is_safe_run_name("foo\\bar") is False)
    check("bare dotdot rejected", is_safe_run_name("..") is False)
    check("empty run name rejected", is_safe_run_name("") is False)
    check("None run name rejected", is_safe_run_name(None) is False)

    print("ALL PASS" if not fails else f"{len(fails)} FAIL(s): " + ", ".join(fails))
    return 1 if fails else 0


def create_app():
    from flask import Flask, jsonify, request
    app = Flask(__name__)

    @app.route("/")
    def index():
        with open(os.path.join(EVAL_DIR, "eval_ui.html"), encoding="utf-8") as f:
            return f.read(), 200

    @app.route("/api/state")
    def api_state():
        pool = load_json(POOL_PATH, {"units": {}})
        qrels = load_json(QRELS_PATH, {})
        return jsonify({"units": unit_progress(pool, qrels), "rubric": RUBRIC})

    @app.route("/api/unit/<path:uid>")
    def api_unit(uid):
        pool = load_json(POOL_PATH, {"units": {}})
        qrels = load_json(QRELS_PATH, {})
        unit = pool["units"].get(uid)
        if not unit:
            return jsonify({"error": "unknown unit"}), 404
        return jsonify({"unit_id": uid, "question": unit["question"], "entity": unit["entity"],
                        "candidate": next_candidate(unit, qrels, uid),
                        "labeled": len(labeled_ids(qrels, uid)),
                        "total": len(unit["candidates"])})

    @app.route("/api/label", methods=["POST"])
    def api_label():
        body = request.get_json(force=True)
        uid, eid, rel = body["unit_id"], body["evidence_id"], int(body["rel"])
        pool = load_json(POOL_PATH, {"units": {}})
        qrels = load_json(QRELS_PATH, {})
        unit = pool["units"].get(uid)
        cand = next((c for c in unit["candidates"] if c["evidence_id"] == eid), None) if unit else None
        if not cand:
            return jsonify({"error": "unknown candidate"}), 404
        record_label(qrels, uid, unit["entity"], cand, rel)
        save_json_atomic(QRELS_PATH, qrels)
        return api_unit(uid)

    @app.route("/api/undo", methods=["POST"])
    def api_undo():
        uid = request.get_json(force=True)["unit_id"]
        pool = load_json(POOL_PATH, {"units": {}})
        qrels = load_json(QRELS_PATH, {})
        popped = undo_label(qrels, uid)
        if popped:
            save_json_atomic(QRELS_PATH, qrels)
        unit = pool["units"].get(uid, {"candidates": [], "question": "", "entity": {}})
        # after an undo, the popped candidate is the next unlabeled one again
        return jsonify({"unit_id": uid, "question": unit.get("question"), "entity": unit.get("entity"),
                        "candidate": next_candidate(unit, qrels, uid) if unit.get("candidates") else None,
                        "labeled": len(labeled_ids(qrels, uid)),
                        "total": len(unit.get("candidates", []))})

    register_grading_routes(app)  # Task 9 (no-op stub until then)
    return app


def register_grading_routes(app):
    from flask import jsonify, request

    def _answers_path(run):
        return os.path.join(RUNS_DIR, run, "answers.json")

    def _grades_path(run):
        return os.path.join(RUNS_DIR, run, "grades.json")

    @app.route("/api/runs")
    def api_runs():
        out = []
        if os.path.isdir(RUNS_DIR):
            for d in sorted(os.listdir(RUNS_DIR), reverse=True):
                if os.path.exists(_answers_path(d)):
                    g = load_json(_grades_path(d), {"grades": {}})
                    n = len(load_json(_answers_path(d), {"answers": []})["answers"])
                    out.append({"run": d, "answers": n, "graded": len(g["grades"])})
        return jsonify({"runs": out})

    @app.route("/api/run/<path:run>/next")
    def api_run_next(run):
        if not is_safe_run_name(run):
            return jsonify({"error": "invalid run name"}), 400
        data = load_json(_answers_path(run), None)
        if data is None:
            return jsonify({"error": "unknown run"}), 404
        grades = load_json(_grades_path(run), {"grades": {}})["grades"]
        rec = next_ungraded(data["answers"], grades)
        return jsonify({"run": run, "record": rec, "graded": len(grades),
                        "total": len(data["answers"]),
                        "summary": grade_summary(grades)})

    @app.route("/api/run/<path:run>/grade", methods=["POST"])
    def api_run_grade(run):
        if not is_safe_run_name(run):
            return jsonify({"error": "invalid run name"}), 400
        body = request.get_json(force=True)
        for f in ("faithfulness", "relevance"):
            if int(body[f]) not in (0, 1, 2):
                return jsonify({"error": f"{f} must be 0-2"}), 400
        path = _grades_path(run)
        data = load_json(path, {"grades": {}})
        data["grades"][body["question_id"]] = {
            "faithfulness": int(body["faithfulness"]), "relevance": int(body["relevance"]),
            "citations": {str(k): bool(v) for k, v in (body.get("citations") or {}).items()},
            "note": body.get("note", "")}
        data["summary"] = grade_summary(data["grades"])
        save_json_atomic(path, data)
        return api_run_next(run)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--port", type=int, default=5052)
    args = p.parse_args()
    if args.selftest:
        sys.exit(selftest())
    create_app().run(host="127.0.0.1", port=args.port, debug=False)
