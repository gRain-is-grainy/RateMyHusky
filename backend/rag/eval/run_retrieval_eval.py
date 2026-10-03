"""Scores the current fetch_evidence configuration against the hand-labeled qrels.
Run: python backend/rag/eval/run_retrieval_eval.py --run --label baseline"""
import sys, os, argparse, collections, datetime

from eval_common import (connect, make_query_fns, unit_id, entity_args, load_json,
                         save_json_atomic, git_sha, ensure_run_dir, rel_lookup,
                         hydrate_natural_keys, QUESTIONS_PATH, QRELS_PATH)
from rag_metrics import ndcg_at_k, recall_at_k, mrr, precision_at_k, aggregate

K = 8
METRICS = ("ndcg@8", "recall@8_rel1", "recall@8_rel2", "mrr_rel2", "mrr_rel1", "precision@8")


def score_unit(run_ids, run_rels, run_sources, labels):
    pool_rels = [l["rel"] for l in labels]
    out = {
        "ndcg@8": ndcg_at_k(run_rels, pool_rels, K),
        "recall@8_rel1": recall_at_k(run_rels, pool_rels, K, threshold=1),
        "recall@8_rel2": recall_at_k(run_rels, pool_rels, K, threshold=2),
        "mrr_rel2": mrr(run_rels, pool_rels, threshold=2),
        "mrr_rel1": mrr(run_rels, pool_rels, threshold=1),
        "precision@8": precision_at_k(run_rels, K, threshold=1),
        "run_ids": run_ids, "run_rels": run_rels,
    }
    # per-source recall@8 (rel>=1): of the relevant labels from source s, how many made top-8
    rel_ids_in_run = {i for i, r in zip(run_ids[:K], run_rels[:K]) if r >= 1}
    src = {}
    for s in ("reddit", "rmp"):
        rel_labels = [l for l in labels if l["source"] == s and l["rel"] >= 1]
        if rel_labels:
            src[s] = sum(1 for l in rel_labels if l["evidence_id"] in rel_ids_in_run) / len(rel_labels)
    out["source_recall_rel1"] = src
    return out


def _resolve_label_ids(labels, run_ids, query_fn):
    """Remap each label's evidence_id to the run id it actually matches, mirroring
    rel_lookup's natural-key fallback (the corpus can be reloaded between labeling and
    scoring, changing evidence uuids). Without this, score_unit's per-source recall would
    miss a label that DID match the run via natural key but whose stored evidence_id
    differs from the run's current id — disagreeing with ndcg/recall/mrr, which already
    score off rel_lookup's resolution."""
    run_id_set = set(run_ids)
    direct_ids = {l["evidence_id"] for l in labels} & run_id_set
    unresolved_run_ids = [i for i in run_ids if i not in direct_ids]
    if not unresolved_run_ids:
        return labels
    hydrated = hydrate_natural_keys(unresolved_run_ids, query_fn)
    by_key = {(row["source"], row["source_ref"], row.get("professor_slug"),
               row.get("course_code") or ""): rid for rid, row in hydrated.items()}
    resolved = []
    for l in labels:
        if l["evidence_id"] in run_id_set:
            resolved.append(l)
            continue
        key = (l["source"], l["source_ref"], l.get("professor_slug"), l.get("course_code") or "")
        rid = by_key.get(key)
        resolved.append({**l, "evidence_id": rid} if rid else l)
    return resolved


def score_all(questions, qrels, query_fn, fetch_fn, embed_fn):
    units, unlabeled_total, unlabeled_by_unit, mode_of = {}, 0, {}, {}
    slot_counts = collections.Counter()
    for q in questions:
        for entity in q["entities"]:
            uid = unit_id(q["id"], entity)
            labels = qrels.get(uid, {}).get("labels", [])
            if not labels:
                print(f"  skip {uid}: no labels")
                continue
            slug, code = entity_args(entity)
            picked = fetch_fn(slug, code, q["question"], embed_fn, query_fn, limit=K)
            run_ids = [str(c["source_id"]) for c in picked]
            run_sources = {str(c["source_id"]): c.get("source") for c in picked}
            rel_by_id, unlabeled = rel_lookup(labels, run_ids, query_fn)
            run_rels = [rel_by_id.get(i, 0) for i in run_ids]
            resolved_labels = _resolve_label_ids(labels, run_ids, query_fn)
            u = score_unit(run_ids, run_rels, run_sources, resolved_labels)
            u["unlabeled_ids"] = unlabeled
            unlabeled_total += len(unlabeled)
            if unlabeled:
                unlabeled_by_unit[uid] = len(unlabeled)
            units[uid] = u
            mode_of[uid] = q["mode"]
            for c in picked:
                slot_counts[c.get("source")] += 1
    summary = {m: aggregate([u[m] for u in units.values()]) for m in METRICS}
    by_mode = {}
    for mode in ("professor", "course", "compare"):
        uids = [u for u in units if mode_of[u] == mode]
        if uids:
            by_mode[mode] = {m: aggregate([units[u][m] for u in uids]) for m in METRICS}
    src_recall = {}
    for s in ("reddit", "rmp"):
        vals = [u["source_recall_rel1"].get(s) for u in units.values() if s in u["source_recall_rel1"]]
        if vals:
            src_recall[s] = aggregate(vals)
    total_slots = sum(slot_counts.values()) or 1
    return {"summary": summary, "by_mode": by_mode,
            "by_source_recall_rel1": src_recall,
            "slot_share": {s: n / total_slots for s, n in slot_counts.items()},
            "unlabeled": {"total": unlabeled_total, "by_unit": unlabeled_by_unit},
            "units": units}


def run(questions, qrels, label, run_dir_arg):
    from rag.chat_retrieve import fetch_evidence
    from rag.query_embedder import embed_query, MODEL_VERSION
    conn = connect()
    query_fn, _ = make_query_fns(conn)
    res = score_all(questions, qrels, query_fn, fetch_evidence, embed_query)

    by_rel = collections.Counter()
    n_labels = 0
    for unit in qrels.values():
        for l in unit.get("labels", []):
            by_rel[l["rel"]] += 1
            n_labels += 1
    meta = {"kind": "retrieval", "git_sha": git_sha(),
            "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "label": label,
            "params": {"limit": K, "rrf_k": 60, "reddit_floor": 2, "rmp_floor": 2,
                       "pool_depth": 20, "query_embedder": MODEL_VERSION},
            "qrels_stats": {"units": len(qrels), "labels": n_labels,
                           "by_rel": {str(r): n for r, n in sorted(by_rel.items())}}}

    run_dir = ensure_run_dir(run_dir_arg, label)
    save_json_atomic(os.path.join(run_dir, "retrieval_metrics.json"), res)
    save_json_atomic(os.path.join(run_dir, "meta.json"), meta)

    print(f"\n== retrieval metrics ({len(res['units'])} units) ==")
    for m in METRICS:
        a = res["summary"][m]
        mean = "n/a" if a["mean"] is None else f"{a['mean']:.4f}"
        print(f"  {m:16s} {mean}  (scored {a['n_scored']}, skipped {a['n_skipped']})")
    if res["unlabeled"]["total"]:
        print(f"  WARNING: {res['unlabeled']['total']} unlabeled items hit the top-8 "
              f"(counted rel=0): {res['unlabeled']['by_unit']} — label the gaps in eval_ui")
    print(f"\nwrote {run_dir}/retrieval_metrics.json + meta.json")
    return 0


def selftest():
    fails = []
    def check(label, cond):
        if not cond: fails.append(label)
        print(("PASS" if cond else "FAIL") + ": " + label)
    def approx(a, b, tol=1e-6):
        return a is not None and abs(a - b) <= tol

    labels_u1 = [
        {"evidence_id": "a", "source": "rmp", "source_ref": "ra", "professor_slug": "g", "course_code": "", "body_sha": "s", "rel": 2},
        {"evidence_id": "b", "source": "reddit", "source_ref": "rb", "professor_slug": "g", "course_code": "", "body_sha": "s", "rel": 1},
        {"evidence_id": "c", "source": "rmp", "source_ref": "rc", "professor_slug": "g", "course_code": "", "body_sha": "s", "rel": 0},
        {"evidence_id": "d", "source": "rmp", "source_ref": "rd", "professor_slug": "g", "course_code": "", "body_sha": "s", "rel": 2},
    ]
    # run returns a,b,c,d in that order -> run_rels [2,1,0,2] vs pool [2,1,0,2]
    u = score_unit(["a", "b", "c", "d"], [2, 1, 0, 2],
                   {"a": "rmp", "b": "reddit", "c": "rmp", "d": "rmp"}, labels_u1)
    # ideal pool [2,2,1,0] -> same worked example as rag_metrics selftest
    check("unit ndcg matches worked example", approx(u["ndcg@8"], 0.91287807, 1e-4))
    check("unit recall rel2 = 1.0", u["recall@8_rel2"] == 1.0)
    check("unit mrr rel2 = 1.0 (first item is rel2)", u["mrr_rel2"] == 1.0)
    check("unit precision = 0.75", u["precision@8"] == 0.75)
    check("per-source recall: rmp 2/2", u["source_recall_rel1"]["rmp"] == 1.0)
    check("per-source recall: reddit 1/1", u["source_recall_rel1"]["reddit"] == 1.0)

    # ── score_all: a natural-key-resolved label (stale evidence_id, corpus reloaded since
    # labeling) must still count toward source_recall_rel1, agreeing with the ndcg/recall/mrr
    # metrics (which already score off rel_lookup's resolution) ──
    questions_nk = [{"id": "p01", "mode": "professor", "question": "is g hard?",
                     "entities": [{"kind": "professor", "slug": "g"}]}]
    qrels_nk = {"p01::g": {"entity": {"kind": "professor", "slug": "g"}, "labels": [
        {"evidence_id": "old-id", "source": "rmp", "source_ref": "ref1",
         "professor_slug": "g", "course_code": "", "body_sha": "s", "rel": 2}]}}
    def fake_query_nk(sql, params):
        if "FROM evidence WHERE id IN" in sql:
            return [{"id": "new-id", "source": "rmp", "source_ref": "ref1",
                     "professor_slug": "g", "course_code": "", "body_sha": "s"}]
        return []
    def fake_fetch_nk(slug, code, q, embed_fn, query_fn, limit=8):
        return [{"source_id": "new-id", "source": "rmp"}]
    res_nk = score_all(questions_nk, qrels_nk, fake_query_nk, fake_fetch_nk, lambda q: None)
    unit_nk = res_nk["units"]["p01::g"]
    check("natural-key-resolved label counts in source_recall_rel1",
          unit_nk["source_recall_rel1"].get("rmp") == 1.0)

    print("ALL PASS" if not fails else f"{len(fails)} FAIL(s): " + ", ".join(fails))
    return 1 if fails else 0


def main():
    p = argparse.ArgumentParser(description="Score fetch_evidence against hand-labeled qrels.")
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--run", action="store_true")
    p.add_argument("--label", default="run")
    p.add_argument("--run-dir")
    args = p.parse_args()
    if args.selftest:
        sys.exit(selftest())
    if args.run:
        questions = load_json(QUESTIONS_PATH, None)
        if questions is None:
            sys.exit(f"missing {QUESTIONS_PATH}")
        qrels = load_json(QRELS_PATH, None)
        if not qrels:
            sys.exit(f"missing/empty {QRELS_PATH} — run eval_ui.py and label some units first")
        sys.exit(run(questions, qrels, args.label, args.run_dir))
    print("use --run --label <name>, or --selftest")


if __name__ == "__main__":
    main()
