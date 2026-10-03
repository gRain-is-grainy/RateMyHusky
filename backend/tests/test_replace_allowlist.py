"""--replace must refuse rmp_reviews, whatever the caller asks for.

Truncating rmp_reviews regenerates every id, and evidence.source_ref for RMP is
that rowid (scraper/load_evidence_to_crdb.py:208) — a full replace orphans the
RMP half of the RAG corpus and forces a re-embed. It also empties a table the
site reads on every professor page, because the TRUNCATE commits before the
reload starts. prune_rmp_reviews.py converges the table without either cost, so
nothing needs the truncate any more and the workflow no longer asks for it.

The allowlist is the enforcement point: the workflow is one caller, and a hand-run
`python migrate_to_crdb.py rmp_reviews --replace` has to fail too.

rmp_professors stays replaceable — 3,889 rows of aggregates RMP recomputes
constantly, no request path reads the table, and nothing references its ids.
"""

from migrate_to_crdb import REPLACE_ALLOWED, TABLES


def test_rmp_reviews_cannot_be_replaced():
    assert "rmp_reviews" not in REPLACE_ALLOWED


def test_rmp_professors_can_be_replaced():
    assert "rmp_professors" in REPLACE_ALLOWED


def test_cumulative_artifacts_cannot_be_replaced():
    # The photo CSV accumulates across scrapes rather than being a complete
    # snapshot of the source, so replacing from it destroys data.
    assert "professor_photos" not in REPLACE_ALLOWED


def test_allowlist_only_names_real_tables():
    assert REPLACE_ALLOWED <= set(TABLES)


def test_a_bare_run_writes_nothing(monkeypatch):
    """No default target: a bare run would upsert every table from local CSVs,
    re-inserting reviews prune_rmp_reviews.py removed if the CSV is stale."""
    import pytest
    import migrate_to_crdb

    def no_connect(*a, **k):
        raise AssertionError("a bare run must not connect")

    monkeypatch.setattr(migrate_to_crdb, "get_connection", no_connect)
    monkeypatch.setattr(migrate_to_crdb.sys, "argv", ["migrate_to_crdb.py"])
    with pytest.raises(SystemExit) as exc:
        migrate_to_crdb.main()
    assert "usage" in str(exc.value)
