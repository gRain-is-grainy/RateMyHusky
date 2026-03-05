"""
TRACE Course Report Scraper

Scrapes individual course evaluation reports from TRACE.
Downloads XLS (scores) and HTML (comments) for each course.
Reads course list from trace_courses.csv (output of trace_scrape.py).

Outputs:
    trace_scores.csv   — one row per question per course (answer counts + stats)
    trace_comments.csv — one row per comment per course

Requires:
    pip install requests tqdm xlrd beautifulsoup4

Usage:
    python trace_reports.py --cookie "your_cookie" --months 3         # last 3 months
    python trace_reports.py --cookie "your_cookie" --months 6 --skip-months 3  # 3-6 months ago
    python trace_reports.py --cookie "your_cookie" --months 12 --skip-months 6 --append  # 6-12 months ago
    python trace_reports.py --cookie "your_cookie" --limit 50         # test with 50 courses
"""

__author__ = "Benjamin"
__version__ = "1.0.0"

import csv
import io
import os
import re
import time
import argparse
import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta

import requests
import xlrd
from bs4 import BeautifulSoup
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed, Future

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL: str = "https://www.applyweb.com"
XLS_URL: str = BASE_URL + "/eval/EvalGatekeeper/EvalGatekeeper?service=QuantitativeXls&sp={cid}&sp={iid}&sp={tid}"
COMMENTS_URL: str = BASE_URL + "/eval/new/showreport?c={cid}&i={iid}&t={tid}&r=9&d=true"
REPORT_URL: str = BASE_URL + "/eval/new/coursereport?sp={cid}&sp={iid}&sp={tid}"

COOKIE: str = ""

logging.basicConfig(level=logging.WARNING)
logger: logging.Logger = logging.getLogger(__name__)

SCORE_FIELDS: List[str] = [
    "courseId", "instructorId", "termId",
    "enrollment", "completed",
    "question", "count_5", "count_4", "count_3", "count_2", "count_1",
    "mean", "median", "std_dev",
]

COMMENT_FIELDS: List[str] = [
    "course_url",
    "question", "comment",
]


# ===========================================================================
# XLS Parser — extract scores from in-memory XLS
# ===========================================================================

def parse_xls(
    xls_bytes: bytes, course_url: str, cid: int, iid: int, tid: int
) -> Tuple[List[Dict[str, Any]], int, int]:
    """Parse a TRACE XLS file and extract question scores.

    Returns:
        Tuple of (score_rows, enrollment, completed)
    """
    rows: List[Dict[str, Any]] = []
    enrollment: int = 0
    completed: int = 0

    try:
        wb: xlrd.Book = xlrd.open_workbook(file_contents=xls_bytes)
        ws: xlrd.sheet.Sheet = wb.sheet_by_index(0)
    except Exception as e:
        logger.warning(f"Failed to parse XLS for course {cid}: {e}")
        return rows, enrollment, completed

    # Scan for enrollment, completed, and question data
    for row_idx in range(ws.nrows):
        # Get all cell values in this row as strings
        cell_values: List[str] = []
        for col_idx in range(ws.ncols):
            cell = ws.cell(row_idx, col_idx)
            cell_values.append(str(cell.value).strip() if cell.value else "")

        row_text: str = " ".join(cell_values).lower()

        # Extract enrollment and completed counts
        if "enrollment" in row_text:
            for val in cell_values:
                try:
                    num: int = int(float(val))
                    if num > 0:
                        enrollment = num
                        break
                except (ValueError, TypeError):
                    continue

        if "completed" in row_text and "completion" not in row_text:
            for val in cell_values:
                try:
                    num = int(float(val))
                    if num > 0:
                        completed = num
                        break
                except (ValueError, TypeError):
                    continue

        # Look for question rows — they have a question name followed by numbers
        # Skip header rows, summary rows, and label rows
        if not cell_values[0]:
            continue

        first_cell: str = cell_values[0]

        # Skip known non-question rows
        skip_labels: List[str] = [
            "evaluations summary", "all responses", "northeastern",
            "course reference", "enrollment", "completed", "answer counts",
            "strongly agree", "agree", "neutral", "disagree",
            "strongly positive", "positive", "negative",
            "almost always", "usually effective", "sometimes effective",
            "rarely effective", "never effective", "not applicable",
            "mean", "median", "std dev", "response rate",
            "general summary", "overall course summary",
            "instructor summary", "overall effectiveness summary",
            "materials summary", "all student responses",
        ]

        if any(first_cell.lower().startswith(s) for s in skip_labels):
            continue

        # Check if this row has numeric data (answer counts + stats)
        numeric_values: List[float] = []
        for val in cell_values[1:]:
            try:
                numeric_values.append(float(val))
            except (ValueError, TypeError):
                continue

        # A question row needs at least 5 values (counts) + mean
        if len(numeric_values) < 6:
            continue

        # Skip "Eval #N" rows (individual student responses)
        if first_cell.lower().startswith("eval #"):
            continue

        # Extract: count_5, count_4, count_3, count_2, count_1, mean, median, std_dev
        counts: List[int] = [int(v) for v in numeric_values[:5]]
        mean: float = numeric_values[5] if len(numeric_values) > 5 else 0.0
        median: float = numeric_values[6] if len(numeric_values) > 6 else 0.0
        std_dev: float = numeric_values[7] if len(numeric_values) > 7 else 0.0

        rows.append({
            "courseId": cid,
            "instructorId": iid,
            "termId": tid,
            "enrollment": enrollment,
            "completed": completed,
            "question": first_cell,
            "count_5": counts[0],
            "count_4": counts[1],
            "count_3": counts[2],
            "count_2": counts[3],
            "count_1": counts[4],
            "mean": round(mean, 2),
            "median": round(median, 2),
            "std_dev": round(std_dev, 2),
        })

    # Backfill enrollment/completed into all rows
    for row in rows:
        row["enrollment"] = enrollment
        row["completed"] = completed

    return rows, enrollment, completed


# ===========================================================================
# Comments Parser — extract comments from HTML
# ===========================================================================

def parse_comments(
    html: str, course_url: str,
) -> List[Dict[str, Any]]:
    """Parse TRACE comments HTML and extract question → comments."""
    rows: List[Dict[str, Any]] = []

    soup: BeautifulSoup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table", class_="table")

    for table in tables:
        # Question is in <th><strong>Q: ...</strong></th>
        question_tag = table.find("strong")
        if not question_tag:
            continue

        question: str = question_tag.get_text(strip=True)
        # Clean "Q: " prefix
        if question.startswith("Q:"):
            question = question[2:].strip()

        # Comments are in <tr><td>num</td><td><a>comment text</a></td></tr>
        body = table.find("tbody")
        if not body:
            continue

        for tr in body.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue

            # Comment text is in the second <td>, possibly inside an <a>
            comment_td = tds[1]
            link = comment_td.find("a")
            if link:
                comment_text: str = link.get_text(strip=True)
            else:
                comment_text = comment_td.get_text(strip=True)

            if not comment_text:
                continue

            # Sanitize — collapse whitespace
            comment_text = " ".join(comment_text.split())

            rows.append({
                "course_url": course_url,
                "question": question,
                "comment": comment_text,
            })

    return rows


# ===========================================================================
# Main scraper
# ===========================================================================

def load_courses(input_path: str) -> List[Dict[str, Any]]:
    """Load course triples from trace_courses.csv (includes termEndDate)."""
    courses: List[Dict[str, Any]] = []
    with open(input_path, "r", encoding="utf-8") as f:
        reader: csv.DictReader = csv.DictReader(f)
        for row in reader:
            try:
                courses.append({
                    "courseId": int(row["courseId"]),
                    "instructorId": int(row["instructorId"]),
                    "termId": int(row["termId"]),
                    "termEndDate": row.get("termEndDate", ""),
                })
            except (ValueError, KeyError):
                continue
    return courses


def filter_by_months(
    courses: List[Dict[str, Any]],
    months: Optional[int] = None,
    skip_months: int = 0,
) -> List[Dict[str, Any]]:
    """Filter courses by termEndDate date range.

    Args:
        courses: Full course list with termEndDate strings ("2026-01-15").
        months: Only include courses from the last N months (None = all).
        skip_months: Skip the most recent N months.

    Examples:
        --months 3                → last 3 months
        --months 6 --skip-months 3 → 3 to 6 months ago
        --months 12 --skip-months 6 → 6 to 12 months ago
    """
    if months is None and skip_months == 0:
        return courses

    now: datetime = datetime.now(timezone.utc)
    oldest: Optional[datetime] = now - timedelta(days=months * 30) if months else None
    newest: datetime = now - timedelta(days=skip_months * 30)

    filtered: List[Dict[str, Any]] = []
    for course in courses:
        date_str: str = course.get("termEndDate", "")

        # No date — include if no months filter, skip otherwise
        if not date_str:
            if months is None:
                filtered.append(course)
            continue

        try:
            end_date: datetime = datetime.strptime(date_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue

        # Must be before newest cutoff (skip recent months)
        if end_date > newest:
            continue

        # Must be after oldest cutoff (within months range)
        if oldest and end_date < oldest:
            continue

        filtered.append(course)

    return filtered


def scrape_reports(
    cookie: str,
    courses: List[Dict[str, Any]],
    limit: Optional[int] = None,
    workers: int = 10,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Scrape scores and comments for each course in parallel.

    Args:
        cookie: TRACE session cookie.
        courses: List of {courseId, instructorId, termId} dicts.
        limit: Max courses to scrape (None = all).
        workers: Number of parallel threads.

    Returns:
        Tuple of (all_scores, all_comments).
    """
    session: requests.Session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "Cookie": cookie,
        "Referer": "https://www.applyweb.com/eval/new/reportbrowser",
    })

    if limit:
        courses = courses[:limit]

    all_scores: List[Dict[str, Any]] = []
    all_comments: List[Dict[str, Any]] = []
    failed: int = 0
    expired: bool = False

    def scrape_one(course: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Scrape a single course — thread-safe."""
        cid: int = course["courseId"]
        iid: int = course["instructorId"]
        tid: int = course["termId"]
        course_url: str = REPORT_URL.format(cid=cid, iid=iid, tid=tid)
        scores: List[Dict[str, Any]] = []
        comments: List[Dict[str, Any]] = []

        # XLS (scores)
        try:
            xls_resp: requests.Response = session.get(
                XLS_URL.format(cid=cid, iid=iid, tid=tid),
                timeout=60,
            )
            if xls_resp.status_code == 200 and len(xls_resp.content) > 100:
                scores, _, _ = parse_xls(xls_resp.content, course_url, cid, iid, tid)
            elif xls_resp.status_code == 401:
                raise ConnectionError("Session expired")
        except ConnectionError:
            raise
        except Exception as e:
            logger.warning(f"XLS failed for {cid}: {e}")

        # Comments HTML
        try:
            comments_resp: requests.Response = session.get(
                COMMENTS_URL.format(cid=cid, iid=iid, tid=tid),
                timeout=60,
            )
            if comments_resp.status_code == 200:
                comments = parse_comments(comments_resp.text, course_url)
            elif comments_resp.status_code == 401:
                raise ConnectionError("Session expired")
        except ConnectionError:
            raise
        except Exception as e:
            logger.warning(f"Comments failed for {cid}: {e}")

        return scores, comments

    pbar: tqdm = tqdm(total=len(courses), desc="Scraping reports", unit=" course")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures: Dict[Future, Dict[str, Any]] = {
            executor.submit(scrape_one, course): course
            for course in courses
        }

        for future in as_completed(futures):
            if expired:
                pbar.update(1)
                continue

            try:
                scores, comments = future.result()
                all_scores.extend(scores)
                all_comments.extend(comments)
            except ConnectionError:
                expired = True
                print(f"\n  ✗ Session expired — saving what we have...")
            except Exception:
                failed += 1

            pbar.update(1)

    pbar.close()

    if failed:
        print(f"  ⚠ {failed} courses failed")

    return all_scores, all_comments


def save_csv(
    rows: List[Dict[str, Any]], fieldnames: List[str], file_path: str,
    append: bool = False,
) -> None:
    """Save rows to CSV. Append mode adds to existing file."""
    os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
    file_exists: bool = os.path.exists(file_path)
    mode: str = "a" if append and file_exists else "w"

    with open(file_path, mode, newline="", encoding="utf-8") as f:
        writer: csv.DictWriter = csv.DictWriter(f, fieldnames=fieldnames)
        if mode == "w" or not file_exists:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)

    label: str = "Appended" if append and file_exists else "Saved"
    print(f"  ✓ {label} {len(rows):,} rows to: {file_path}")


# ===========================================================================
# CLI
# ===========================================================================

def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Scrape TRACE course evaluation reports (scores + comments)"
    )
    parser.add_argument(
        "--cookie", type=str, default=COOKIE,
        help="TRACE session cookie",
    )
    parser.add_argument(
        "--input", type=str, default=None,
        help="Path to trace_courses.csv (default: output_data/trace_courses.csv)",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max courses to scrape (for testing)",
    )
    parser.add_argument(
        "--months", type=int, default=None,
        help="Only scrape courses from the last N months",
    )
    parser.add_argument(
        "--skip-months", type=int, default=0,
        help="Skip the most recent N months (for chunking by time)",
    )
    parser.add_argument(
        "--workers", type=int, default=10,
        help="Parallel threads (default 10, lower if timeouts)",
    )
    parser.add_argument(
        "--append", action="store_true",
        help="Append to existing CSVs instead of overwriting",
    )
    parser.add_argument(
        "-o", "--output-dir", type=str, default=None,
        help="Output directory for CSVs",
    )

    args: argparse.Namespace = parser.parse_args()

    cookie: str = args.cookie.strip()
    if not cookie:
        print("\n  Paste your TRACE session cookie:")
        cookie = input("  Cookie: ").strip()
    if not cookie:
        print("  ✗ Cannot proceed without cookies.")
        return

    # Load courses
    script_dir: str = os.path.dirname(os.path.abspath(__file__))
    input_path: str = args.input or os.path.join(
        script_dir, "output_data", "trace_courses.csv"
    )

    if not os.path.exists(input_path):
        print(f"  ✗ Course list not found: {input_path}")
        print("    Run trace_scrape.py first to generate it.")
        return

    courses: List[Dict[str, Any]] = load_courses(input_path)
    print(f"  Loaded {len(courses):,} courses from {input_path}")

    # Filter by date range
    if args.months is not None or args.skip_months > 0:
        courses = filter_by_months(courses, months=args.months, skip_months=args.skip_months)
        if args.skip_months > 0 and args.months:
            print(f"  Filtered to {len(courses):,} courses ({args.skip_months}-{args.months} months ago)")
        elif args.months:
            print(f"  Filtered to {len(courses):,} courses (last {args.months} months)")
        elif args.skip_months > 0:
            print(f"  Filtered to {len(courses):,} courses (skipping last {args.skip_months} months)")

    if args.limit:
        print(f"  Limiting to {args.limit} courses")

    # Scrape
    all_scores, all_comments = scrape_reports(cookie, courses, limit=args.limit, workers=args.workers)

    # Save
    output_dir: str = args.output_dir or os.path.join(script_dir, "output_data")

    if all_scores:
        save_csv(all_scores, SCORE_FIELDS, os.path.join(output_dir, "trace_scores.csv"), append=args.append)

    if all_comments:
        save_csv(all_comments, COMMENT_FIELDS, os.path.join(output_dir, "trace_comments.csv"), append=args.append)

    total: int = len(all_scores) + len(all_comments)
    if total == 0:
        print("  ✗ No data scraped — check your cookie or date range.")
    else:
        print(f"\n  Done! ({len(all_scores):,} score rows, {len(all_comments):,} comments)")
        print()


if __name__ == "__main__":
    main()