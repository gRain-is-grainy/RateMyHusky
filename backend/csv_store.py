"""Reading data-store CSVs that may ship zipped.

GitHub rejects any file over 100MB, so a big data-store export (rmp_reviews is
the largest) may be tracked compressed. The fallback belongs here before a push
is rejected, not after.

Two readers, because they consume the file differently:

  resolve()    for pandas, which opens a .zip directly given the path.
  open_text()  for csv.DictReader, which does not.

Better_Scraper/scrape_guard.py answers the same question for the workflow's row
counts, but it is deliberately stdlib-only and import-free so ci.yml can run it
without pandas — hence the second, smaller copy of the rule there rather than an
import across that boundary.
"""

import contextlib
import io
import os
import zipfile


def resolve(data_dir, filename):
    """Path to `filename` in `data_dir`, or its .zip sibling when only that is there.

    Prefers the plain .csv when both exist: a local re-scrape writes the
    uncompressed file beside the store's zip, and the fresh one should win.

    Returns the .csv path when neither exists, so a caller's "file not found"
    names the file someone should go looking for.
    """
    path = os.path.join(str(data_dir), filename)
    if os.path.exists(path) or not filename.endswith(".csv"):
        return path
    zipped = path[: -len(".csv")] + ".zip"
    return zipped if os.path.exists(zipped) else path


@contextlib.contextmanager
def open_text(path):
    """A text handle for a .csv, or for the single .csv inside a .zip.

    errors="replace" because review text is not reliably UTF-8, and
    newline="" because the csv module requires it to keep newlines embedded in
    quoted fields intact.
    """
    path = str(path)
    if not path.endswith(".zip"):
        with open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
            yield fh
        return

    with zipfile.ZipFile(path) as z:
        members = [n for n in z.namelist() if n.endswith(".csv")]
        if not members:
            raise ValueError(f"{path} contains no .csv member")
        with z.open(members[0]) as raw:
            yield io.TextIOWrapper(
                raw, encoding="utf-8", errors="replace", newline=""
            )
