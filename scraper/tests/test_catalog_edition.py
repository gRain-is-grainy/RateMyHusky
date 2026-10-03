"""Edition watcher: the one signal that says the whole catalog was replaced.

The failure this guards is silence. `catalog.northeastern.edu` swaps every
course description for a new academic year on a date that has landed anywhere
between mid-July and late August across the last three rollovers (measured
2026-08-13 against Wayback snapshots), and
nothing announces it. A watcher that returns "unchanged" when it can no longer
find the label is worse than no watcher, so every unreadable case raises rather
than reporting no change.
"""
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
import catalog_edition  # noqa: E402
from catalog_edition import (EditionUnreadable, check_edition,  # noqa: E402
                             parse_edition)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "catalog")


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


def test_parses_edition_from_the_live_sidebar_markup():
    assert parse_edition(fixture("home_sidebar.html")) == "2025-2026"


def test_reads_the_id_anchor_not_the_first_match():
    """The mobile toggle repeats the label; only the h2 is the source of record.

    A redesign that leaves stale copy in the button must not decide the answer.
    """
    html = fixture("home_sidebar.html").replace(
        "<span>2025-2026 Edition</span>", "<span>2019-2020 Edition</span>")
    assert parse_edition(html) == "2025-2026"


def test_missing_anchor_raises_rather_than_reporting_no_change():
    html = fixture("home_sidebar.html").replace('id="edition"', 'id="masthead"')
    with pytest.raises(EditionUnreadable):
        parse_edition(html)


def test_anchor_without_a_year_label_raises():
    html = fixture("home_sidebar.html").replace(
        '<h2 id="edition" class="sidebar-header"><a href="/">2025-2026 Edition</a></h2>',
        '<h2 id="edition" class="sidebar-header"><a href="/">Academic Catalog</a></h2>')
    with pytest.raises(EditionUnreadable):
        parse_edition(html)


def test_unchanged_edition_reports_no_change():
    result = check_edition(fixture("home_sidebar.html"), "2025-2026")
    assert result.changed is False
    assert result.live == "2025-2026"


def test_new_edition_reports_the_change_with_both_years():
    html = fixture("home_sidebar.html").replace("2025-2026", "2026-2027")
    result = check_edition(html, "2025-2026")
    assert result.changed is True
    assert (result.expected, result.live) == ("2025-2026", "2026-2027")


# --- CLI: the exit code is the whole interface, since CI reads nothing else ---


@pytest.fixture
def state(tmp_path):
    path = tmp_path / "catalog_edition.json"
    catalog_edition.write_state("2025-2026", str(path))
    return str(path)


@pytest.fixture
def serve(monkeypatch):
    """Replace the network boundary and count the calls it receives."""
    calls = []

    def fake_fetch(url=catalog_edition.HOME_URL, session=None):
        calls.append(url)
        return fake_fetch.html

    monkeypatch.setattr(catalog_edition, "fetch_home", fake_fetch)
    fake_fetch.calls = calls
    return fake_fetch


def test_unchanged_edition_exits_zero(state, serve, capsys):
    serve.html = fixture("home_sidebar.html")
    assert catalog_edition.main(["--state", state]) == 0
    assert "Unchanged: 2025-2026" in capsys.readouterr().out


def test_rollover_exits_with_its_own_code_so_ci_goes_red(state, serve, capsys):
    serve.html = fixture("home_sidebar.html").replace("2025-2026", "2026-2027")
    assert catalog_edition.main(["--state", state]) == catalog_edition.EXIT_NEW_EDITION
    assert "2025-2026 -> 2026-2027" in capsys.readouterr().err


def test_no_outcome_shares_exit_1_with_an_uncaught_exception():
    """CI files a different issue per code; a crash must never read as a rollover."""
    codes = {catalog_edition.EXIT_UNCHANGED, catalog_edition.EXIT_NEW_EDITION,
             catalog_edition.EXIT_UNREADABLE, catalog_edition.EXIT_FETCH_FAILED}
    assert len(codes) == 4
    assert 1 not in codes


def test_one_check_costs_one_request(state, serve):
    """The watcher's entire budget is a single weekly GET; two would double it."""
    serve.html = fixture("home_sidebar.html")
    catalog_edition.main(["--state", state])
    assert len(serve.calls) == 1


def test_unreadable_page_surfaces_rather_than_passing_silently(state, serve, capsys):
    serve.html = fixture("home_sidebar.html").replace('id="edition"', 'id="masthead"')
    assert catalog_edition.main(["--state", state]) == catalog_edition.EXIT_UNREADABLE
    assert "EDITION UNREADABLE" in capsys.readouterr().err


def test_fetch_failure_is_not_reported_as_a_rollover(state, monkeypatch, capsys):
    def down(url=catalog_edition.HOME_URL, session=None):
        raise requests.ConnectionError("connection reset")

    monkeypatch.setattr(catalog_edition, "fetch_home", down)
    assert catalog_edition.main(["--state", state]) == catalog_edition.EXIT_FETCH_FAILED
    assert "FETCH FAILED" in capsys.readouterr().err


def test_missing_baseline_crashes_instead_of_fetching(tmp_path, serve):
    serve.html = fixture("home_sidebar.html")
    with pytest.raises(FileNotFoundError):
        catalog_edition.main(["--state", str(tmp_path / "missing.json")])
    assert serve.calls == []


# --- fetch_home: retried like catalog_scrape.py, since this host drops connections ---


class FakeResponse:
    def __init__(self, status, text=""):
        self.status_code = status
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class FakeSession:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def get(self, url, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_fetch_retries_a_dropped_connection_and_a_503():
    session = FakeSession(requests.ConnectionError("reset"), FakeResponse(503),
                          FakeResponse(200, "ok"))
    assert catalog_edition.fetch_home(session=session, sleep=lambda s: None) == "ok"
    assert session.calls == 3


def test_fetch_gives_up_after_max_attempts():
    session = FakeSession(*[requests.Timeout("slow")] * catalog_edition.MAX_ATTEMPTS)
    with pytest.raises(requests.Timeout):
        catalog_edition.fetch_home(session=session, sleep=lambda s: None)
    assert session.calls == catalog_edition.MAX_ATTEMPTS


def test_fetch_does_not_retry_a_403():
    session = FakeSession(FakeResponse(403))
    with pytest.raises(requests.HTTPError):
        catalog_edition.fetch_home(session=session, sleep=lambda s: None)
    assert session.calls == 1


def test_record_writes_the_live_edition_as_the_new_baseline(state, serve):
    serve.html = fixture("home_sidebar.html").replace("2025-2026", "2026-2027")
    assert catalog_edition.main(["--record", "--state", state]) == 0
    assert catalog_edition.read_state(state) == "2026-2027"
