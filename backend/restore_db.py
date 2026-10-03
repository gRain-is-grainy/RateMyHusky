"""
Emergency restore from a backend/backup_db.py gzipped SQL dump into CockroachDB.

Usage:
    python backend/restore_db.py <dump.sql.gz> --tables rmp_professors,rmp_reviews [--yes]
    python backend/restore_db.py <dump.sql.gz> --all [--yes]
    python backend/restore_db.py <dump.sql.gz> --list
    python backend/restore_db.py --selftest

WARNING: restore DROPs the target tables on the live cluster (CASCADE) and
recreates them from the dump. The live site will error on those tables until
the restore completes. Double-check --tables / --all before confirming.

Reads NEW_CRDB_DATABASE_URL from backend/.env (same as backup_db.py).
"""

import os, sys, re, argparse, glob
from urllib.parse import urlparse

_FIXTURE_SQL = """-- ratemyhusky NEW cluster backup
-- Table: rmp_reviews  (3 rows)
SET sql_safe_updates = false;

DROP TABLE IF EXISTS rmp_reviews CASCADE;
CREATE TABLE public.rmp_reviews (
    id INT8 NOT NULL,
    comment STRING NULL
);

INSERT INTO rmp_reviews (id, comment) VALUES
(1,'simple'),
(2,'tricky; has ''quoted'' text;
and a newline -- not a comment'),
(3,E'escaped \\' quote');

-- Table: stats_cache  (1 rows)
DROP TABLE IF EXISTS stats_cache CASCADE;
INSERT INTO stats_cache (key, value) VALUES ('professors',9385);
"""


def iter_statements(lines):
    """Split a backup_db.py dump into statements, streaming. State machine handles:
    '...' literals with '' doubling (psycopg2 mogrify), E'...' with backslash escapes
    (defensive), "..." identifiers, and -- line comments outside strings. RMP
    review text contains ; and newlines INSIDE literals — naive split(';') corrupts it."""
    buf = []
    in_sq = in_dq = False
    estring = False
    for line in lines:
        i = 0
        stripped_lead = line.lstrip()
        if not (in_sq or in_dq) and not buf and stripped_lead.startswith("--"):
            continue  # comment-only line between statements
        while i < len(line):
            ch = line[i]
            if in_sq:
                if estring and ch == "\\":
                    i += 2; buf.append(line[i-2:i]); continue
                if ch == "'":
                    if i + 1 < len(line) and line[i+1] == "'":
                        buf.append("''"); i += 2; continue
                    in_sq = False
                buf.append(ch); i += 1; continue
            if in_dq:
                if ch == '"':
                    in_dq = False
                buf.append(ch); i += 1; continue
            if ch == "'":
                in_sq = True
                estring = bool(buf) and buf[-1].rstrip().upper().endswith("E") and \
                          (len(buf[-1].rstrip()) == 1 or not buf[-1].rstrip()[-2].isalnum())
                buf.append(ch); i += 1; continue
            if ch == '"':
                in_dq = True; buf.append(ch); i += 1; continue
            if ch == "-" and line[i:i+2] == "--":
                break  # rest of line is a comment
            if ch == ";":
                stmt = "".join(buf).strip()
                if stmt:
                    yield stmt
                buf = []; i += 1; continue
            buf.append(ch); i += 1
        else:
            continue
    tail = "".join(buf).strip()
    if tail:
        yield tail

_TABLE_RE = re.compile(r"^(?:DROP TABLE IF EXISTS|CREATE TABLE|INSERT INTO)\s+(?:\"?[A-Za-z0-9_]+\"?\.)?\"?([A-Za-z0-9_]+)\"?", re.I)

def statement_table(stmt):
    m = _TABLE_RE.match(stmt.strip())
    return m.group(1) if m else None

def list_dump(path):
    import gzip
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.startswith("-- Table:"):
                print(line.rstrip())

def confirm(host, tables, dump_name, input_fn=input, assume_yes=False):
    label = host.split(".")[0]
    print(f"\n*** DESTRUCTIVE RESTORE ***\n  Target host: {host}\n  Dump: {dump_name}"
          f"\n  Tables to DROP + recreate: {', '.join(sorted(tables)) if tables else 'ALL'}"
          "\n  The live site will error on these tables until the restore completes.")
    if assume_yes:
        return True
    return input_fn(f"Type the cluster name ('{label}') to proceed: ").strip() == label

def _fmt_secs(secs):
    secs = int(secs)
    if secs >= 3600:
        return f"{secs // 3600}h{(secs % 3600) // 60:02d}m"
    if secs >= 60:
        return f"{secs // 60}m{secs % 60:02d}s"
    return f"{secs}s"


def restore(conn, path, tables):
    import gzip, psycopg2, time as _t
    executed = skipped = 0
    total_bytes = os.path.getsize(path)
    start = last_print = _t.time()
    # Progress = compressed bytes consumed from the dump; ETA extrapolates from
    # elapsed time, so it overshoots early while skipping filtered tables and
    # corrects as real execution dominates.
    with open(path, "rb") as raw, gzip.open(raw, "rt", encoding="utf-8") as f:
        for stmt in iter_statements(f):
            t = statement_table(stmt)
            if tables is not None and t is not None and t not in tables:
                skipped += 1
            else:
                for attempt in range(6):
                    try:
                        with conn.cursor() as cur:
                            cur.execute(stmt)
                        conn.commit()
                        break
                    except psycopg2.errors.SerializationFailure:
                        conn.rollback()
                        if attempt == 5:
                            raise
                        _t.sleep(0.5 * (2 ** attempt))
                executed += 1
            now = _t.time()
            if now - last_print >= 2:
                last_print = now
                frac = raw.tell() / total_bytes
                eta = _fmt_secs((now - start) * (1 - frac) / frac) if frac > 0 else "?"
                print(f"  {executed:,} statements executed | {frac:.1%} of dump | ~{eta} left   ", end="\r")
    print(f"\nDone: {executed:,} statements executed, {skipped:,} skipped (filtered tables) "
          f"in {_fmt_secs(_t.time() - start)}.")


def connect_database(label, url, attempts=8):
    import time
    import psycopg2
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return psycopg2.connect(url, sslmode="require")
        except psycopg2.OperationalError as exc:
            message = str(exc)
            if "could not translate host name" not in message:
                raise
            last_error = message
            if attempt < attempts:
                print(f"  DNS lookup failed for {label}; retrying ({attempt}/{attempts})...")
                time.sleep(3)
    sys.exit(f"Could not resolve the hostname in {label} after {attempts} attempts.\n"
             f"Original error:\n{last_error}")


def selftest():
    fails = []
    def check(label, cond):
        if not cond: fails.append(label)
        print(("PASS" if cond else "FAIL") + ": " + label)

    stmts = list(iter_statements(_FIXTURE_SQL.splitlines(keepends=True)))
    check("6 statements found (comments skipped)", len(stmts) == 6)
    check("semicolon+newline inside quotes did not split",
          any("tricky; has ''quoted'' text" in s and "newline -- not a comment" in s for s in stmts))
    check("E-string backslash escape did not split", any("escaped" in s and s.count("VALUES") == 1 for s in stmts))
    check("SET statement captured", stmts[0].startswith("SET sql_safe_updates"))

    check("table of DROP", statement_table("DROP TABLE IF EXISTS rmp_reviews CASCADE") == "rmp_reviews")
    check("table of CREATE", statement_table('CREATE TABLE rmp_reviews (\n id INT8)') == "rmp_reviews")
    check("table of schema-qualified CREATE",
          statement_table('CREATE TABLE public.rmp_reviews (\n id INT8)') == "rmp_reviews")
    check("table of INSERT", statement_table("INSERT INTO stats_cache (key) VALUES ('x')") == "stats_cache")
    check("SET has no table", statement_table("SET sql_safe_updates = false") is None)

    kept = [s for s in stmts if statement_table(s) in (None, "stats_cache")]
    check("--tables filter keeps SET + target table only", len(kept) == 3)

    check("confirm accepts typed host label",
          confirm("free-tier-cluster.gcp.cockroachlabs.cloud", ["rmp_reviews"], "d.sql.gz",
                  input_fn=lambda _: "free-tier-cluster") is True)
    check("confirm rejects wrong input",
          confirm("free-tier-cluster.gcp.cockroachlabs.cloud", ["rmp_reviews"], "d.sql.gz",
                  input_fn=lambda _: "yes") is False)
    check("confirm honors --yes",
          confirm("h.x.y", ["t"], "d", input_fn=lambda _: (_ for _ in ()).throw(AssertionError("prompted")),
                  assume_yes=True) is True)

    check("fmt seconds", _fmt_secs(45) == "45s")
    check("fmt minutes", _fmt_secs(130) == "2m10s")
    check("fmt hours", _fmt_secs(7500) == "2h05m")

    print("ALL PASS" if not fails else f"{len(fails)} FAIL(s): " + ", ".join(fails))
    return 1 if fails else 0


def _newest_dump():
    backup_dir = os.path.join(os.path.dirname(__file__), "backups")
    candidates = glob.glob(os.path.join(backup_dir, "ratemyhusky_new_*.sql.gz"))
    if not candidates:
        return None
    return max(candidates)


def main():
    parser = argparse.ArgumentParser(description="Emergency restore from a backup_db.py dump into CockroachDB.")
    parser.add_argument("dump", nargs="?", help="Path to a .sql.gz dump (default: newest in backend/backups/)")
    parser.add_argument("--list", action="store_true", help="List tables in the dump and exit (no DB connection)")
    parser.add_argument("--tables", help="Comma-separated table names to restore")
    parser.add_argument("--all", action="store_true", help="Restore every table in the dump")
    parser.add_argument("--yes", action="store_true", help="Skip the interactive confirmation prompt")
    parser.add_argument("--selftest", action="store_true", help="Run the offline selftest and exit")
    args = parser.parse_args()

    if args.selftest:
        sys.exit(selftest())

    dump = args.dump or _newest_dump()
    if not dump:
        sys.exit("No dump given and no backend/backups/ratemyhusky_new_*.sql.gz found.")
    if not os.path.isfile(dump):
        sys.exit(f"Dump file not found: {dump}")

    if args.list:
        list_dump(dump)
        return

    if bool(args.tables) == bool(args.all):
        sys.exit("Specify exactly one of --tables a,b,c or --all.")

    tables = None if args.all else {t.strip() for t in args.tables.split(",") if t.strip()}

    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    db_url = os.getenv("NEW_CRDB_DATABASE_URL")
    if not db_url:
        sys.exit("Missing NEW_CRDB_DATABASE_URL in backend/.env")

    host = urlparse(db_url).hostname
    if not confirm(host, tables, os.path.basename(dump), assume_yes=args.yes):
        sys.exit("Aborted: confirmation not given.")

    conn = connect_database("NEW_CRDB_DATABASE_URL", db_url)
    try:
        restore(conn, dump, tables)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
