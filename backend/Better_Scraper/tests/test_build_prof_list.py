import os, sys, csv, json
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))
import build_prof_list as bpl


def _write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(header)
        for r in rows:
            w.writerow(r)


def test_build_records_dedup_college_and_existing(tmp_path):
    d = tmp_path
    _write_csv(d / "rmp_professors.csv",
               ["name", "department", "rating", "num_ratings",
                "would_take_again_pct", "level_of_difficulty", "professor_url"],
               [["Jane Doe", "Computer Science", "4", "10", "80%", "2", "u"],
                ["Jane  Doe", "Computer Science", "4", "10", "80%", "2", "u"],   # dup
                ["John Smith", "Economics", "3", "5", "50%", "3", "u"]])
    _write_csv(d / "professor_photos.csv",
               ["name", "image_url", "source_page"],
               [["Jane Doe", "https://x.edu/jane-400x400.jpg", "p"]])

    recs = bpl.build_records(str(d))
    by_name = {r["name"].lower(): r for r in recs}
    assert len(recs) == 2                                   # Jane deduped
    assert by_name["jane doe"]["college"] == "Khoury"
    assert by_name["jane doe"]["existing_url"] == "https://x.edu/jane-400x400.jpg"
    assert by_name["john smith"]["college"] == "CSSH"
    assert by_name["john smith"]["existing_url"] == ""


def test_collapse_duplicates_alias_and_swap():
    import photo_research as pr
    idx = pr.build_alias_index()
    recs = [
        {"name": "Christo Wilson", "department": "Computer Science", "college": "Khoury", "aliases": ["christopher wilson"], "existing_url": "https://x/cw.jpg"},
        {"name": "Christopher Wilson", "department": "Computer Science", "college": "Khoury", "aliases": ["christo wilson"], "existing_url": ""},
        {"name": "Jesse Stern", "department": "Computer Science", "college": "Khoury", "aliases": [], "existing_url": ""},
        {"name": "Stern Jesse", "department": "Computer Science", "college": "Khoury", "aliases": [], "existing_url": ""},
        {"name": "Jane Unique", "department": "Computer Science", "college": "Khoury", "aliases": [], "existing_url": ""},
    ]
    out = bpl.collapse_duplicates(recs, idx)
    names = sorted(r["name"] for r in out)
    # 5 records collapse to 3 people: Wilson(x2), Stern(x2 swap), Jane
    assert len(out) == 3
    # the Wilson record kept the existing_url
    wilson = [r for r in out if "wilson" in r["name"].lower()][0]
    assert wilson["existing_url"] == "https://x/cw.jpg"
    assert "jane unique" in [n.lower() for n in names]
