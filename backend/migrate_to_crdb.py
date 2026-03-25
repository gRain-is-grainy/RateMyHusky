"""
Migrate CSV data into CockroachDB.
Run:  python backend/migrate_to_crdb.py all
"""

import os, csv, sys, time
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

DATABASE_URL = os.getenv("CRDB_DATABASE_URL")

if not DATABASE_URL:
    sys.exit("Missing CRDB_DATABASE_URL in backend/.env")

import psycopg2
from psycopg2.extras import execute_values

DATA_DIR = os.path.join(os.path.dirname(__file__), "Better_Scraper", "output_data")
BATCH_SIZE = 10000


def get_connection():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def create_table(conn, sql: str):
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def upload_csv(conn, table: str, columns: list[str], csv_path: str, transform=None):
    if not os.path.exists(csv_path):
        print(f"  File not found: {csv_path}")
        return

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        batch = []
        total = 0

        col_names = ", ".join(columns)
        insert_sql = f"INSERT INTO {table} ({col_names}) VALUES %s"

        for row in reader:
            if transform:
                row = transform(row)
            if row is None:
                continue
            batch.append(tuple(row[col] for col in columns))

            if len(batch) >= BATCH_SIZE:
                with conn.cursor() as cur:
                    execute_values(cur, insert_sql, batch, page_size=BATCH_SIZE)
                conn.commit()
                total += len(batch)
                print(f"  Uploaded {total:,} rows...", end="\r")
                batch = []

        if batch:
            with conn.cursor() as cur:
                execute_values(cur, insert_sql, batch, page_size=BATCH_SIZE)
            conn.commit()
            total += len(batch)

    print(f"  Done: {total:,} rows inserted.")


# ──────────────────────────────────────────────
#  Table definitions & transforms
# ──────────────────────────────────────────────

TABLES = {
    "trace_comments": {
        "create_sql": """
            CREATE TABLE IF NOT EXISTS trace_comments (
                id INT8 DEFAULT unique_rowid() PRIMARY KEY,
                course_url TEXT NOT NULL,
                question TEXT,
                comment TEXT
            );
        """,
        "columns": ["course_url", "question", "comment"],
        "csv": "trace_comments.csv",
        "transform": lambda row: {
            "course_url": row.get("course_url", ""),
            "question": row.get("question", ""),
            "comment": row.get("comment", ""),
        },
    },
    "rmp_professors": {
        "create_sql": """
            CREATE TABLE IF NOT EXISTS rmp_professors (
                id INT8 DEFAULT unique_rowid() PRIMARY KEY,
                name TEXT NOT NULL,
                department TEXT,
                rating REAL,
                num_ratings INT,
                would_take_again_pct TEXT,
                level_of_difficulty REAL,
                professor_url TEXT
            );
        """,
        "columns": ["name", "department", "rating", "num_ratings", "would_take_again_pct", "level_of_difficulty", "professor_url"],
        "csv": "rmp_professors.csv",
        "transform": lambda row: {
            "name": row.get("name", ""),
            "department": row.get("department", ""),
            "rating": float(row["rating"]) if row.get("rating") else None,
            "num_ratings": int(row["num_ratings"]) if row.get("num_ratings") else None,
            "would_take_again_pct": row.get("would_take_again_pct", ""),
            "level_of_difficulty": float(row["level_of_difficulty"]) if row.get("level_of_difficulty") else None,
            "professor_url": row.get("professor_url", ""),
        },
    },
    "rmp_reviews": {
        "create_sql": """
            CREATE TABLE IF NOT EXISTS rmp_reviews (
                id INT8 DEFAULT unique_rowid() PRIMARY KEY,
                professor_name TEXT NOT NULL,
                department TEXT,
                overall_rating REAL,
                course TEXT,
                quality REAL,
                difficulty REAL,
                date TEXT,
                tags TEXT,
                attendance TEXT,
                grade TEXT,
                textbook TEXT,
                online_class TEXT,
                comment TEXT
            );
        """,
        "columns": ["professor_name", "department", "overall_rating", "course", "quality", "difficulty", "date", "tags", "attendance", "grade", "textbook", "online_class", "comment"],
        "csv": "rmp_reviews.csv",
        "transform": lambda row: {
            "professor_name": row.get("professor_name", ""),
            "department": row.get("department", ""),
            "overall_rating": float(row["overall_rating"]) if row.get("overall_rating") else None,
            "course": row.get("course", ""),
            "quality": float(row["quality"]) if row.get("quality") else None,
            "difficulty": float(row["difficulty"]) if row.get("difficulty") else None,
            "date": row.get("date", ""),
            "tags": row.get("tags", ""),
            "attendance": row.get("attendance", ""),
            "grade": row.get("grade", ""),
            "textbook": row.get("textbook", ""),
            "online_class": row.get("online_class", ""),
            "comment": row.get("comment", ""),
        },
    },
    "trace_courses": {
        "create_sql": """
            CREATE TABLE IF NOT EXISTS trace_courses (
                id INT8 DEFAULT unique_rowid() PRIMARY KEY,
                course_id INT,
                school_code TEXT,
                term_id INT,
                term_title TEXT,
                instructor_id INT,
                term_end_date TEXT,
                instructor_first_name TEXT,
                instructor_last_name TEXT,
                department_name TEXT,
                enrollment INT,
                display_name TEXT,
                section TEXT
            );
        """,
        "columns": ["course_id", "school_code", "term_id", "term_title", "instructor_id", "term_end_date", "instructor_first_name", "instructor_last_name", "department_name", "enrollment", "display_name", "section"],
        "csv": "trace_courses.csv",
        "transform": lambda row: {
            "course_id": int(row["courseId"]) if row.get("courseId") else None,
            "school_code": row.get("schoolCode", ""),
            "term_id": int(row["termId"]) if row.get("termId") else None,
            "term_title": row.get("termTitle", ""),
            "instructor_id": int(row["instructorId"]) if row.get("instructorId") else None,
            "term_end_date": row.get("termEndDate", ""),
            "instructor_first_name": row.get("instructorFirstName", ""),
            "instructor_last_name": row.get("instructorLastName", ""),
            "department_name": row.get("departmentName", ""),
            "enrollment": int(row["enrollment"]) if row.get("enrollment") else None,
            "display_name": row.get("displayName", ""),
            "section": row.get("section", ""),
        },
    },
    "trace_scores": {
        "create_sql": """
            CREATE TABLE IF NOT EXISTS trace_scores (
                id INT8 DEFAULT unique_rowid() PRIMARY KEY,
                course_id INT,
                instructor_id INT,
                term_id INT,
                enrollment INT,
                completed INT,
                question TEXT,
                count_5 INT,
                count_4 INT,
                count_3 INT,
                count_2 INT,
                count_1 INT,
                mean REAL,
                median REAL,
                std_dev REAL
            );
        """,
        "columns": ["course_id", "instructor_id", "term_id", "enrollment", "completed", "question", "count_5", "count_4", "count_3", "count_2", "count_1", "mean", "median", "std_dev"],
        "csv": "trace_scores.csv",
        "transform": lambda row: {
            "course_id": int(row["courseId"]) if row.get("courseId") else None,
            "instructor_id": int(row["instructorId"]) if row.get("instructorId") else None,
            "term_id": int(row["termId"]) if row.get("termId") else None,
            "enrollment": int(row["enrollment"]) if row.get("enrollment") else None,
            "completed": int(row["completed"]) if row.get("completed") else None,
            "question": row.get("question", ""),
            "count_5": int(row["count_5"]) if row.get("count_5") else None,
            "count_4": int(row["count_4"]) if row.get("count_4") else None,
            "count_3": int(row["count_3"]) if row.get("count_3") else None,
            "count_2": int(row["count_2"]) if row.get("count_2") else None,
            "count_1": int(row["count_1"]) if row.get("count_1") else None,
            "mean": float(row["mean"]) if row.get("mean") else None,
            "median": float(row["median"]) if row.get("median") else None,
            "std_dev": float(row["std_dev"]) if row.get("std_dev") else None,
        },
    },
    "professor_photos": {
        "create_sql": """
            CREATE TABLE IF NOT EXISTS professor_photos (
                id INT8 DEFAULT unique_rowid() PRIMARY KEY,
                name TEXT NOT NULL,
                image_url TEXT,
                source_page TEXT
            );
        """,
        "columns": ["name", "image_url", "source_page"],
        "csv": "professor_photos.csv",
        "transform": lambda row: {
            "name": row.get("name", ""),
            "image_url": row.get("image_url", ""),
            "source_page": row.get("source_page", ""),
        },
    },
}


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["trace_comments"]

    if targets == ["all"]:
        targets = list(TABLES.keys())

    conn = get_connection()
    print("Connected to CockroachDB!")

    for table_name in targets:
        if table_name not in TABLES:
            print(f"Unknown table: {table_name}")
            continue

        conf = TABLES[table_name]
        csv_path = os.path.join(DATA_DIR, conf["csv"])

        print(f"\n{'='*50}")
        print(f"Uploading: {table_name}")
        print(f"{'='*50}")

        print(f"  Creating table if not exists...")
        create_table(conn, conf["create_sql"])

        print(f"  Reading {conf['csv']}...")
        start = time.time()
        upload_csv(conn, table_name, conf["columns"], csv_path, conf.get("transform"))
        elapsed = time.time() - start
        print(f"  Time: {elapsed:.1f}s")

    conn.close()
    print("\nDone! All tables migrated.")


if __name__ == "__main__":
    main()
