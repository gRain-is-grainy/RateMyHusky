import json, csv

JSON_FILE = "trace_results.json"
OUTPUT_CSV = "Fall 2025.csv"  # Change to "Summer 2025.csv" for summer

with open(JSON_FILE) as f:
    results = json.load(f)

fieldnames = [
    "term", "created_date", "course_info", "audience",
    "section", "question",
    "Number of Responses",
    "Course Mean", "Dept. Mean", "Univ. Mean",
    "Course Median", "Dept. Median", "Univ. Median",
    "count_5", "count_4", "count_3", "count_2", "count_1",
    "comment_prompt", "comments_json",
    "demographics_json",
]

rows = []
for r in results:
    if "error" in r: continue
    base = {
        "term": r.get("term", ""),
        "created_date": r.get("created_date", ""),
        "course_info": r.get("course_info", ""),
        "audience": r.get("audience", ""),
    }
    score_dists = r.get("score_distributions", {})
    comments_by_prompt = {}
    for c in r.get("comments", []):
        comments_by_prompt.setdefault(c["prompt"], []).append(c["comment"])

    # Summary rows
    for s in r.get("sections", []):
        for q in s.get("questions", []):
            row = {**base, "section": s["section"]}
            qtext = q.get("question", "")
            if qtext.isdigit() and "Effectiveness" in s["section"]:
                row["question"] = "What is your overall rating of this instructor's teaching effectiveness?"
                row["Number of Responses"] = int(qtext)
                keys = [k for k in q if k != "question"]
                vals = [q[k] for k in keys]
                correct = ["_skip", "Course Mean", "Dept. Mean", "Univ. Mean",
                           "Course Median", "Dept. Median", "Univ. Median"]
                for i, k in enumerate(correct):
                    if k != "_skip":
                        row[k] = vals[i] if i < len(vals) else ""
                qtext = row["question"]
            else:
                row["question"] = qtext
                row["Number of Responses"] = q.get("Number of Responses", "")
                for k in ["Course Mean", "Dept. Mean", "Univ. Mean",
                          "Course Median", "Dept. Median", "Univ. Median"]:
                    row[k] = q.get(k, "")
            dist = score_dists.get(qtext, {})
            row["count_5"] = dist.get(5, dist.get("5", 0))
            row["count_4"] = dist.get(4, dist.get("4", 0))
            row["count_3"] = dist.get(3, dist.get("3", 0))
            row["count_2"] = dist.get(2, dist.get("2", 0))
            row["count_1"] = dist.get(1, dist.get("1", 0))
            rows.append(row)

    # Comment rows
    for prompt, comment_list in comments_by_prompt.items():
        row = {**base, "section": "Comments",
               "comment_prompt": prompt,
               "comments_json": json.dumps(comment_list, ensure_ascii=False)}
        rows.append(row)

    # Demographics rows
    for demo in r.get("demographics", []):
        row = {**base, "section": "Demographics",
               "question": demo["question"],
               "demographics_json": json.dumps(demo["distribution"], ensure_ascii=False)}
        rows.append(row)

with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)

print(f"Saved {len(rows)} rows to {OUTPUT_CSV}")