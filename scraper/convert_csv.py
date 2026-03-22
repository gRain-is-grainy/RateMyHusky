import json, csv, sys

files = [
    ("Fall 2025.json", "Fall 2025.csv"),
    ("trace_summer.json", "Summer 2025.csv"),
]

for jfile, cfile in files:
    try:
        with open(jfile) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Skipping {jfile} (not found)")
        continue

    rows = []
    for r in data:
        if "error" in r:
            continue
        for s in r["sections"]:
            for q in s["questions"]:
                row = {
                    "course_info": r["course_info"],
                    "audience": r["audience"],
                    "responses": r["responses"],
                    "response_rate": r["response_rate"],
                    "section": s["section"],
                }

                qtext = q.get("question", "")

                # Fix shifted overall rating row
                if qtext.isdigit() and "Effectiveness" in s["section"]:
                    row["question"] = "What is your overall rating of this instructor teaching effectiveness?"
                    row["Number of Responses"] = int(qtext)
                    keys = [k for k in q if k != "question"]
                    vals = [q[k] for k in keys]
                    correct_keys = ["Response Rate", "Course Mean", "Dept. Mean", "Univ. Mean", "Course Median", "Dept. Median", "Univ. Median"]
                    for i2, k2 in enumerate(correct_keys):
                        row[k2] = vals[i2] if i2 < len(vals) else ""
                else:
                    row.update(q)

                rows.append(row)

    if not rows:
        print(f"No data in {jfile}")
        continue

    fieldnames = [
        "course_info", "audience", "responses", "response_rate", "section",
        "question", "Number of Responses", "Response Rate", "Course Mean",
        "Dept. Mean", "Univ. Mean", "Course Median", "Dept. Median", "Univ. Median"
    ]

    with open(cfile, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(f"Saved {len(rows)} rows to {cfile}")
