"""
Transform raw TRACE CSVs (Fall 2025.csv, Summer 2025.csv) into the 3 normalized
CSVs the existing pipeline expects: trace_courses.csv, trace_scores.csv, trace_comments.csv.

ID Ranges (to distinguish from old scraper data):
  - courseId:      500000+
  - instructorId:  50000+
  - termId:        900+

Run:  python scraper/transform_to_trace.py
Output is APPENDED to backend/Better_Scraper/output_data/*.csv (existing rows kept).
A manifest (scraper/transform_manifest.json) tracks which rows were added so re-runs
never create duplicates.
"""

import csv
import json
import os
import re
import sys

# ── Paths ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "backend", "Better_Scraper", "output_data")
MANIFEST_PATH = os.path.join(SCRIPT_DIR, "transform_manifest.json")

# ── ID offsets (well above existing max IDs) ──
COURSE_ID_OFFSET = 500000
INSTRUCTOR_ID_OFFSET = 50000
TERM_ID_OFFSET = 900

# ── Auto-incrementing ID maps ──
_course_counter = 0
_instructor_counter = 0
_term_counter = 0
course_id_map: dict[str, int] = {}      # "BIOT5621-01" -> 500001
instructor_id_map: dict[str, int] = {}   # "dennis fernandes" -> 50001
term_id_map: dict[str, int] = {}         # "Full Summer 2025" -> 901


def get_course_id(course_section: str) -> int:
    """Deterministic ID for a course+section string like 'BIOT5621-01'."""
    global _course_counter
    key = course_section.strip().upper()
    if key not in course_id_map:
        _course_counter += 1
        course_id_map[key] = COURSE_ID_OFFSET + _course_counter
    return course_id_map[key]


def get_instructor_id(name: str) -> int:
    """Deterministic ID for an instructor name."""
    global _instructor_counter
    key = name.strip().lower()
    if key not in instructor_id_map:
        _instructor_counter += 1
        instructor_id_map[key] = INSTRUCTOR_ID_OFFSET + _instructor_counter
    return instructor_id_map[key]


def get_term_id(term: str) -> int:
    """Deterministic ID for a term string like 'Fall 2025'."""
    global _term_counter
    key = term.strip()
    if key not in term_id_map:
        _term_counter += 1
        term_id_map[key] = TERM_ID_OFFSET + _term_counter
    return term_id_map[key]


def parse_course_info(raw: str):
    """
    Parse strings like:
      '- TRACE report for BIOT5621-01 Protein Principles in Biotech  (Dennis Fernandes)'
      'AACE6000-01 Arts and Culture Leadership  (Diana Arcadipone)'

    Returns (course_code, section, course_name, instructor_name) or None.
    """
    # Strip leading "- TRACE report for " if present
    s = re.sub(r'^-\s*TRACE report for\s*', '', raw.strip())

    # Match: CODE-SECTION  CourseName  (Instructor)
    m = re.match(
        r'([A-Z]{2,10}\d{4})-(\d{1,3})\s+(.+?)\s{2,}\((.+?)\)\s*$',
        s
    )
    if m:
        return m.group(1), m.group(2), m.group(3).strip(), m.group(4).strip()

    # Fallback: try single-space before parens
    m = re.match(
        r'([A-Z]{2,10}\d{4})-(\d{1,3})\s+(.+?)\s+\((.+?)\)\s*$',
        s
    )
    if m:
        return m.group(1), m.group(2), m.group(3).strip(), m.group(4).strip()

    return None


def split_instructor_name(full_name: str):
    """Split 'Dennis Fernandes' into ('Dennis', 'Fernandes')."""
    parts = full_name.strip().split()
    if len(parts) == 0:
        return ("", "")
    if len(parts) == 1:
        return ("", parts[0])
    return (parts[0], " ".join(parts[1:]))


def safe_int(val):
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def safe_float(val):
    try:
        v = str(val).replace("%", "").strip()
        return float(v)
    except (ValueError, TypeError):
        return None


def load_manifest():
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r") as f:
            return json.load(f)
    return {"processed_files": [], "source_tag": "scraper_v2"}


def save_manifest(manifest):
    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)


def load_existing_keys(csv_path, key_cols):
    """Load composite keys from an existing CSV to avoid duplicates."""
    keys = set()
    if not os.path.exists(csv_path):
        return keys
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = tuple(row.get(c, "") for c in key_cols)
            keys.add(key)
    return keys


def process_csv(csv_path: str, term_override: str = None):
    """
    Process a single raw TRACE CSV.
    Returns (courses_rows, scores_rows, comments_rows).
    """
    courses = {}   # keyed by (course_section, instructor, term)
    scores = []
    comments = []

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Get course info — Fall 2025 uses 'course_info', Summer 2025 has both
            course_info = row.get("course_info", "") or row.get("display_name", "")
            if not course_info:
                continue

            parsed = parse_course_info(course_info)
            if not parsed:
                continue
            course_code, section_num, course_name, instructor_name = parsed

            term = term_override or row.get("term", "").strip()
            if not term:
                continue

            course_section = f"{course_code}-{section_num}"
            course_id = get_course_id(course_section)
            instructor_id = get_instructor_id(instructor_name)
            term_id = get_term_id(term)

            first_name, last_name = split_instructor_name(instructor_name)
            enrollment = safe_int(row.get("audience", 0))
            completed = safe_int(row.get("responses", 0))

            # Build display_name in existing format: "CS2500:01 (Course Name) - Instructor"
            display_name = f"{course_code}:{section_num} ({course_name}) - {instructor_name}"

            # Register course (dedup by composite key)
            course_key = (course_id, instructor_id, term_id)
            if course_key not in courses:
                courses[course_key] = {
                    "courseId": course_id,
                    "schoolCode": "SH",
                    "termId": term_id,
                    "termTitle": term,
                    "instructorId": instructor_id,
                    "termEndDate": row.get("created_date", ""),
                    "instructorFirstName": first_name,
                    "instructorLastName": last_name,
                    "departmentName": "",  # not in raw CSVs
                    "enrollment": enrollment,
                    "displayName": display_name,
                    "section": section_num,
                }

            section_type = row.get("section", "").strip()
            question = row.get("question", "").strip()

            # ── Comments rows ──
            if section_type == "Comments":
                comments_json = row.get("comments_json", "").strip()
                comment_prompt = row.get("comment_prompt", "").strip()
                prompt = comment_prompt or question
                if comments_json:
                    try:
                        comment_list = json.loads(comments_json)
                        # Build URL in the same format existing data uses
                        url = f"https://www.applyweb.com/eval/new/coursereport?sp={course_id}&sp={instructor_id}&sp={term_id}"
                        for c in comment_list:
                            c_text = str(c).strip()
                            if c_text:
                                comments.append({
                                    "course_url": url,
                                    "question": prompt,
                                    "comment": c_text,
                                })
                    except (json.JSONDecodeError, TypeError):
                        pass
                continue

            # ── Score rows ──
            if not question:
                continue

            count_5 = safe_int(row.get("count_5", 0))
            count_4 = safe_int(row.get("count_4", 0))
            count_3 = safe_int(row.get("count_3", 0))
            count_2 = safe_int(row.get("count_2", 0))
            count_1 = safe_int(row.get("count_1", 0))
            total = count_1 + count_2 + count_3 + count_4 + count_5

            mean_val = safe_float(row.get("Course Mean"))
            if mean_val is None and total > 0:
                mean_val = round(
                    (1*count_1 + 2*count_2 + 3*count_3 + 4*count_4 + 5*count_5) / total,
                    2
                )

            median_val = safe_float(row.get("Course Median"))

            # Map section categories to shorter question labels matching existing data
            full_question = question
            if "Instructor" in section_type:
                # Extract instructor name from section like "Instructor Related Questions: Dennis Fernandes"
                instr_match = re.search(r':\s*(.+)', section_type)
                if instr_match:
                    full_question = question
            if "Effectiveness" in section_type:
                full_question = f"What is your overall rating of this instructor teaching effectiveness?"

            scores.append({
                "courseId": course_id,
                "instructorId": instructor_id,
                "termId": term_id,
                "enrollment": enrollment,
                "completed": completed,
                "question": full_question,
                "count_5": count_5,
                "count_4": count_4,
                "count_3": count_3,
                "count_2": count_2,
                "count_1": count_1,
                "mean": mean_val if mean_val is not None else "",
                "median": median_val if median_val is not None else "",
                "std_dev": "",
            })

    return list(courses.values()), scores, comments


def append_rows(csv_path, fieldnames, rows):
    """Append rows to a CSV, creating it with headers if it doesn't exist."""
    file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def main():
    manifest = load_manifest()

    # Find raw CSVs to process
    raw_files = []
    for fname in sorted(os.listdir(DATA_DIR)):
        if fname.endswith(".csv"):
            full_path = os.path.join(DATA_DIR, fname)
            if full_path not in manifest["processed_files"]:
                raw_files.append(full_path)

    if not raw_files:
        print("No new CSV files to process. All files already in manifest.")
        return

    print(f"Found {len(raw_files)} new file(s) to process:")
    for f in raw_files:
        print(f"  {os.path.basename(f)}")

    # Load existing keys for dedup
    existing_course_keys = load_existing_keys(
        os.path.join(OUTPUT_DIR, "trace_courses.csv"),
        ["courseId", "instructorId", "termId"]
    )
    existing_comment_keys = load_existing_keys(
        os.path.join(OUTPUT_DIR, "trace_comments.csv"),
        ["course_url", "question", "comment"]
    )

    all_courses = []
    all_scores = []
    all_comments = []

    for csv_path in raw_files:
        print(f"\nProcessing: {os.path.basename(csv_path)}")
        courses, scores, comments = process_csv(csv_path)
        print(f"  Parsed: {len(courses)} sections, {len(scores)} scores, {len(comments)} comments")
        all_courses.extend(courses)
        all_scores.extend(scores)
        all_comments.extend(comments)

    # ── Dedup courses against existing data ──
    new_courses = []
    for c in all_courses:
        key = (str(c["courseId"]), str(c["instructorId"]), str(c["termId"]))
        if key not in existing_course_keys:
            new_courses.append(c)
            existing_course_keys.add(key)

    # ── Dedup scores (same composite key as courses — keep all questions) ──
    # Scores are fine as long as their parent course exists
    new_scores = all_scores

    # ── Dedup comments against existing data ──
    new_comments = []
    for c in all_comments:
        key = (c["course_url"], c["question"], c["comment"])
        if key not in existing_comment_keys:
            new_comments.append(c)
            existing_comment_keys.add(key)

    print(f"\n{'='*50}")
    print(f"New rows to append:")
    print(f"  trace_courses:  {len(new_courses)}")
    print(f"  trace_scores:   {len(new_scores)}")
    print(f"  trace_comments: {len(new_comments)}")
    print(f"{'='*50}")

    if not new_courses and not new_scores and not new_comments:
        print("Nothing new to add.")
        return

    # ── Append to output CSVs ──
    course_fields = [
        "courseId", "schoolCode", "termId", "termTitle", "instructorId",
        "termEndDate", "instructorFirstName", "instructorLastName",
        "departmentName", "enrollment", "displayName", "section"
    ]
    score_fields = [
        "courseId", "instructorId", "termId", "enrollment", "completed",
        "question", "count_5", "count_4", "count_3", "count_2", "count_1",
        "mean", "median", "std_dev"
    ]
    comment_fields = ["course_url", "question", "comment"]

    if new_courses:
        append_rows(os.path.join(OUTPUT_DIR, "trace_courses.csv"), course_fields, new_courses)
        print(f"  Appended {len(new_courses)} rows to trace_courses.csv")

    if new_scores:
        append_rows(os.path.join(OUTPUT_DIR, "trace_scores.csv"), score_fields, new_scores)
        print(f"  Appended {len(new_scores)} rows to trace_scores.csv")

    if new_comments:
        append_rows(os.path.join(OUTPUT_DIR, "trace_comments.csv"), comment_fields, new_comments)
        print(f"  Appended {len(new_comments)} rows to trace_comments.csv")

    # ── Update manifest ──
    for csv_path in raw_files:
        manifest["processed_files"].append(csv_path)
    manifest["id_ranges"] = {
        "courseId": f"{COURSE_ID_OFFSET + 1} - {COURSE_ID_OFFSET + _course_counter}",
        "instructorId": f"{INSTRUCTOR_ID_OFFSET + 1} - {INSTRUCTOR_ID_OFFSET + _instructor_counter}",
        "termId": f"{TERM_ID_OFFSET + 1} - {TERM_ID_OFFSET + _term_counter}",
        "note": "All rows with IDs in these ranges came from scraper/transform_to_trace.py"
    }
    manifest["id_maps"] = {
        "terms": {v: k for k, v in term_id_map.items()},
        "total_courses": _course_counter,
        "total_instructors": _instructor_counter,
    }
    save_manifest(manifest)
    print(f"\nManifest saved to {MANIFEST_PATH}")
    print("Done! Now run: python backend/migrate_to_crdb.py all && python backend/precompute.py")


if __name__ == "__main__":
    main()
