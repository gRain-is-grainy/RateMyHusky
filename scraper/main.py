"""
TRACE Master Scraper v5 (with demographics)
Scrapes all reports, outputs one CSV with all fields including demographics.

Usage:
  1. Paste fresh cookies into COOKIES
  2. Set LIST_URL for semester
  3. Run: source ~/trace-env/bin/activate && python3 master_scraper.py
"""

import requests
import json
import time
import re
import sys
import os
import csv
from collections import Counter
from bs4 import BeautifulSoup
from html.parser import HTMLParser
import html as html_module

# ═══════════════════════════════════════════
# CONFIGURATION - UPDATE BEFORE RUNNING
# ═══════════════════════════════════════════

COOKIES = {
    "_ga": "GA1.1.509540977.1774198087",
    "cookiesession1": "678B2A87D44C29A1595AAB0DF919F4B6",
    "_ga_262EDTH0JM": "GS2.1.s1774623376$o12$g0$t1774623381$j55$l0$h0",
    "BlueNextOriginalPath": "/rv.aspx?uid=5660d4f83cbd7a5460463a3454acf9bb&redi=1&SelectedIDforPrint=c0d7284255dab34acc9fd045c1e1ea53e7b9e7efa42c4841dac738545aa34abbf47a5f340cb81c1ec2b5ac2b3844c7cf&ReportType=2&isLive=0&dsid=498dbdbc97a49b840a35dfe28dbd4975&regl=en-US",
    "BlueNextRefreshToken": "2DB285A53C7F9E47E3A86FE3F927163E27CF69A95C166887B85DACA3AA8E0F1C",
    "BlueNextAccessToken": "eyJhbGciOiJSUzI1NiIsImtpZCI6IkEyOTk1ODFDQTAwRDE0QUZCRkQ0RjgzOEMwQzVDNTdERDgwMzJGOENSUzI1NiIsIng1dCI6Im9wbFlIS0FORkstXzFQZzR3TVhGZmRnREw0dyIsInR5cCI6ImF0K2p3dCJ9.eyJuYmYiOjE3NzQ2MjMzODIsImV4cCI6MTc3NDYyNjk4MiwiaXNzIjoiaHR0cHM6Ly9ub3J0aGVhc3Rlcm4tYXV0aC5ibHVlcmEuY29tIiwiY2xpZW50X2lkIjoiQUE2M0U3NjMtRTdFRS00NEU4LUI5M0UtQTYwRTA2QTM3QzkyIiwic3ViIjoiYWIyNjI1NWItYzVjOS00NDM5LTk4YzQtMDQxNDFhNzEwMGRhIiwiYXV0aF90aW1lIjoxNzc0NjIzMzc1LCJpZHAiOiIwNjc0ZDVlNi0wYWVjLTRhZGEtODc2Yy03MDkwZDIxMjllNzEiLCJnc2lkIjoiMENCNEQyQUJBRTkxMjI1QjdBMzI2RUE3NUE4QzAyREUiLCJzc29faWQiOiIxIiwiZXh0ZXJuYWxfaWRwX3VzZXJuYW1lIjoiMDAyNTcxOTkzIiwianRpIjoiNDY5MUExMEFCMEI4RDYzMEZFNENCOUE3MTQxMTdDNUMiLCJpYXQiOjE3NzQ2MjMzODIsInNjb3BlIjpbIm9wZW5pZCIsIm9mZmxpbmVfYWNjZXNzIl0sImFtciI6WyJleHRlcm5hbCJdfQ.pl8U_8Sv_hB77fcSAC6na6SPj7skAN55n7BRI_pb8KvIruUtCcoJSsdjVPQNCHzBqONrssY_0X7cZAvnrRuyC9JUNA0laNs3bKxQdPwsyZiK0OENA5i0mQ_6ELBA_Rze-ORJJnn7Sh7mDCZweSSQK0W3SwCQhBJsAr5fk4hF0Y_kqMF1A7DKxqRegsLB19qImhW1eyejYSx9HjLm1VHsVBb5NbAaTnLEN0EshAaBKNxnEt4TrA7DSLq7LyTZq-xAPPK-T8O0Y9ZdgM6bzxsLwtmVwFm_tb5PjEtiHTlOkXB09e4WsH6f-mBgEdandI7CY5TeJSg_3GQDYhizUzcH_twfT7nvJ9-NivEGn9jqhaMnt3UZERhnZTGNPyX_aFGGZIdXLXN3jQ4ZSC--g1g2ILjQjXZ1sNd-mTkIIKbVDErmbJAUgq2q8l14PfqtyBrlQjCCCDqbTWDZbKHJn5xQ3LGzOGqe2BZa1MBBFU2Utz_Ghpu5LD4tkGHtPiyES2qkKKKnsfxfKi31sxdlYYFZOAkpy1-v41S0hHjxgauGraEk0HR7dMZx6FYODbc4opYsdG1ZcJpr-Vb5sjZWhmQdNnLAFfFnzsoXWElXDqMYF6C4IAf3DHTyDshJWGIY3OECiN_Ndsb_jzA3zgG2xhY_WsDFf_TMgJ5kBiRge0obA1I",
    "BlueNextIdToken": "eyJhbGciOiJSUzI1NiIsImtpZCI6IkEyOTk1ODFDQTAwRDE0QUZCRkQ0RjgzOEMwQzVDNTdERDgwMzJGOENSUzI1NiIsIng1dCI6Im9wbFlIS0FORkstXzFQZzR3TVhGZmRnREw0dyIsInR5cCI6IkpXVCJ9.eyJuYmYiOjE3NzQ2MjMzODIsImV4cCI6MTc3NDYyMzY4MiwiaXNzIjoiaHR0cHM6Ly9ub3J0aGVhc3Rlcm4tYXV0aC5ibHVlcmEuY29tIiwiYXVkIjoiQUE2M0U3NjMtRTdFRS00NEU4LUI5M0UtQTYwRTA2QTM3QzkyIiwiaWF0IjoxNzc0NjIzMzgyLCJhdF9oYXNoIjoiOUJzRW10SlNGc0JvNXVaQWF0N1JWUSIsInNfaGFzaCI6InFRMHhhX2JrZmxqVFhGenF3MlNUaEEiLCJzdWIiOiJhYjI2MjU1Yi1jNWM5LTQ0MzktOThjNC0wNDE0MWE3MTAwZGEiLCJhdXRoX3RpbWUiOjE3NzQ2MjMzNzUsImlkcCI6IjA2NzRkNWU2LTBhZWMtNGFkYS04NzZjLTcwOTBkMjEyOWU3MSIsImFtciI6WyJleHRlcm5hbCJdLCJnc2lkIjoiMENCNEQyQUJBRTkxMjI1QjdBMzI2RUE3NUE4QzAyREUifQ.Z2VBo7LHjrWNmoDD5ZAlxEZQpgYFxMoFO_FdMq0udpVqsZt9bHb5ELLb53Q9ESZWcNptyMYZdQ2BZhmZuIzxgp0IoGdkf9r-J7TYRCZjf3jY0v1mkqVGXh-6-5Bj4olYDk3dV8FA1aodn5c0WHSOf1BOy_Mcovrank8jvR0lBOIqTSe1QK5HRAfLrvgBFcEwvmY9s81zwwF3NU2Gjez0jEaWqO87QaKb2r21P2y2HbGAKmiAHhtzTC3v_VocSL67aH6mBDb3eJnF_yw3EYYnYs8KSTE11IaK37Mn3lyIjU11xvhVgwN0uIDDVvkMLWEAxase7LkrV1XtFr_WkQVyhH0jlQJAzQ0GECKDh-kM7pz9f15lf4H51Zio9Br4A3rHRi2HV5wKiD5ImarQj09yuiqawrybJjB-XWJa89vHosygVX000z2VdlvfY7ztEAhYaYbuwv8acsLQgNMfVJHY5tWgXQCC1AB0fBbvUAl4X2ewOkSRVl3_gxfbYD5CIZpS9wu-Z6uhfXJ_43571dOL1HV83ufhSJebu1PyhfQ-zTmlnsfCyxHAJD68A7HG_YUpdyumr-5pZDLaUu_GEsivnPq0JjYHUszJUbHzRowsBarwEq05cOCnQW0EAPxgElD7gfDm9n9s9BXA95Q377m95LWYhZY_tkMlqyuh1paVwIk",
    "ASP.NET_SessionId": "4hsb5ilwqrl3ftzziaixgxvw",
    "CookieName": "FF82D7CD0B1B77F651F78FC5FB60F6013DB0687BD7FAB287C426DCBB5ED118BE3BDD0414E488862195388BE9DBE839B88310205DD762868E118D8DBBE3F2982617B0863716B76F6BBF9EE7283244248780542F0960693CF5E955A4039F433BB8840E20224D875E824C09B95497652C901663FF7AA89C8D2BD6175B86DEA77C41CDB87179103327835B083D7134B9E1631A89C6D61517AB3D2D980BBA58FDEFE22F216C8A8FF10285B05ED7CF0ADF671B3131E75F1D1C5A5F55699D7C6DF0BEB9D07784B142D906C2DD25B10143BD7F03329EDDF4B810812834D0826DCB787CE5",
    "session_token": "e5220999a44f482f8deb577034ea5da2",
}
BASE_URL = "https://northeastern-bc.bluera.com"

# Fall 2025:
#LIST_URL = f"{BASE_URL}/rpvlf.aspx?rid=694b0639-6919-433a-9b04-5aaba2ab962a&regl=en-US&haslang=true"
# Summer 2025:
LIST_URL = f"{BASE_URL}/rpvlf.aspx?rid=fdf8a2a3-773c-42df-9284-09b0303fb52a&regl=en-US&haslang=true"

URLS_FILE = "trace_urls.json"
RESULTS_FILE = "trace_results.json"
OUTPUT_CSV = "Summer 2025.csv"
TIMEOUT = 60

# ═══════════════════════════════════════════

AGREE_MAP = {
    "Strongly Agree": 5, "Agree": 4, "Neutral": 3,
    "Disagree": 2, "Strongly Disagree": 1,
}
EFFECTIVENESS_MAP = {
    "Almost Always Effective": 5, "Usually Effective": 4,
    "Sometimes Effective": 3, "Rarely Effective": 2,
    "Almost Never Effective": 1,
}


class BlockTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_thead = self.in_tbody = self.in_cell = False
        self.headers, self.rows, self.cur_row, self.cell_text = [], [], [], ""
    def handle_starttag(self, tag, attrs):
        if tag == "thead": self.in_thead = True
        elif tag == "tbody": self.in_tbody = True
        elif tag == "tr": self.cur_row = []
        elif tag in ("th", "td"): self.in_cell = True; self.cell_text = ""
    def handle_endtag(self, tag):
        if tag == "thead": self.in_thead = False
        elif tag == "tbody": self.in_tbody = False
        elif tag == "tr":
            if self.in_thead and self.cur_row: self.headers = self.cur_row
            elif self.in_tbody and self.cur_row: self.rows.append(self.cur_row)
        elif tag in ("th", "td") and self.in_cell:
            self.cur_row.append(self.cell_text.strip()); self.in_cell = False
    def handle_data(self, data):
        if self.in_cell: self.cell_text += data


def text_to_score(text):
    text = text.strip()
    if text in AGREE_MAP: return AGREE_MAP[text]
    if text in EFFECTIVENESS_MAP: return EFFECTIVENESS_MAP[text]
    return None


def parse_demographics(soup):
    """Parse frequency/demographics blocks (attendance, hours per week)."""
    demographics = []
    for block in soup.find_all("div", class_="FrequencyBlock_FullMain"):
        title_el = block.find("h4", class_="FrequencyQuestionTitle")
        if not title_el:
            continue
        question = title_el.get_text(strip=True)

        distribution = {}
        for li in block.find_all("li"):
            label_div = li.find("div", class_="frequency-data-item-choice-text")
            count_div = li.find("div", class_="frequency-data-item-choice-nb")
            if label_div and count_div:
                label = label_div.get_text(strip=True)
                try:
                    count = int(count_div.get_text(strip=True))
                except ValueError:
                    count = 0
                distribution[label] = count

        if distribution:
            demographics.append({
                "question": question,
                "distribution": distribution,
            })
    return demographics


def parse_report_html(html_text):
    soup = BeautifulSoup(html_text, "html.parser")

    # Metadata
    title_tag = soup.find("title")
    title_text = title_tag.text.strip() if title_tag else ""
    m = re.search(r"Student TRACE report for (.+)", title_text)
    course_info = m.group(1).strip() if m else title_text

    # Term
    term = ""
    for sp in soup.find_all("span", id=re.compile(r"ProjectTitle")):
        t = sp.get_text(strip=True)
        if t and t != "Project Title":
            term = t; break

    # Created date
    created_date = ""
    created_span = soup.find("span", id=re.compile(r"lbPublishDateInfo"))
    if created_span:
        strong = created_span.find("strong")
        if strong: created_date = strong.get_text(strip=True)

    # Audience & responses
    aud_el = soup.find("span", id=re.compile(r"lblInvited"))
    resp_el = soup.find("span", id=re.compile(r"lblResponded"))
    audience = int(aud_el.text.strip()) if aud_el else None
    responses = int(resp_el.text.strip()) if resp_el else None

    # Section headings
    headings = [h3.find("strong").get_text(strip=True)
                for h3 in soup.find_all("h3") if h3.find("strong")]

    # Summary tables
    tables = re.findall(r"<table class='block-table[^']*'>.*?</table>", html_text, re.DOTALL)
    sections = []
    for i, block in enumerate(tables):
        p = BlockTableParser(); p.feed(block)
        name = headings[i] if i < len(headings) else f"Section {i+1}"
        questions = []
        for row in p.rows:
            if len(row) < 2: continue
            q = {"question": row[0]}
            for j, h in enumerate(p.headers[1:], 1):
                if j < len(row):
                    v = row[j].strip()
                    try: v = float(v) if "." in v and "%" not in v else v
                    except: pass
                    try: v = int(v) if isinstance(v, str) and v.isdigit() else v
                    except: pass
                    q[h.strip()] = v
            questions.append(q)
        sections.append({"section": name, "questions": questions})

    # Comments
    comments = []
    for block in soup.find_all("div", class_="CommentBlockRow"):
        prev = block.find_previous("h4", class_="ReportBlockTitle")
        prompt = ""
        if prev:
            span = prev.find("span", id=re.compile(r"lblBlockTitle"))
            if span:
                prompt = span.get_text(strip=True)
                if prompt == "-": prompt = ""
        for td in block.find_all("td"):
            div = td.find("div")
            if div:
                text = div.get_text(strip=True)
                if text and text != "[No Response]":
                    comments.append({"prompt": prompt, "comment": html_module.unescape(text)})

    # Score distributions from individual responses
    score_dist = {}
    for sheet in soup.find_all("div", class_="RespS_Sheet"):
        for li in sheet.find_all("li", class_="RespS_QuestionTitle_ListItem"):
            q_rows = li.find_all("span", class_="RespS_QuestionRow_font")
            if q_rows:
                resp_spans = li.find_all("span", class_="RespS_Resp_font")
                for idx, qrow in enumerate(q_rows):
                    question = qrow.get_text(strip=True)
                    resp_text = resp_spans[idx].get_text(strip=True) if idx < len(resp_spans) else ""
                    score = text_to_score(resp_text)
                    if score is not None:
                        score_dist.setdefault(question, []).append(score)
            else:
                title_div = li.find("div", class_="RespS_QuestionTitle_font")
                question = ""
                if title_div:
                    for sp in title_div.find_all("span", recursive=False):
                        if "RespS_QuestionTitle_index" not in (sp.get("class") or []):
                            t = sp.get_text(strip=True)
                            if t and t != "-": question = t
                resp_span = li.find("span", class_="RespS_Resp_font")
                if resp_span:
                    resp_text = resp_span.get_text(strip=True)
                    score = text_to_score(resp_text)
                    if score is not None and question:
                        score_dist.setdefault(question, []).append(score)

    # Demographics
    demographics = parse_demographics(soup)

    return {
        "course_info": course_info,
        "term": term,
        "created_date": created_date,
        "audience": audience,
        "responses": responses,
        "sections": sections,
        "comments": comments,
        "score_distributions": {q: dict(Counter(scores)) for q, scores in score_dist.items()},
        "demographics": demographics,
    }


def fetch(session, method, url, **kwargs):
    kwargs.setdefault("timeout", TIMEOUT)
    for attempt in range(3):
        try:
            r = session.get(url, **kwargs) if method == "GET" else session.post(url, **kwargs)
            r.raise_for_status()
            return r
        except Exception as e:
            w = 5 * (attempt + 1)
            print(f"    ⚠ {type(e).__name__}, retry in {w}s ({attempt+1}/3)")
            time.sleep(w)
    return None


def results_to_csv(results, output_file):
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

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"Saved {len(rows)} rows to {output_file}")


if __name__ == "__main__":
    if not COOKIES:
        print("ERROR: Paste fresh cookies into the COOKIES dict.")
        sys.exit(1)

    s = requests.Session()
    s.cookies.update(COOKIES)
    s.headers.update({"User-Agent": "Mozilla/5.0"})

    print("Testing session...")
    test = fetch(s, "GET", LIST_URL)
    if not test or "Sign in" in test.text:
        print("ERROR: Cookies expired.")
        sys.exit(1)
    print("Session valid!\n")

    # Step 1: Collect URLs
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE) as f:
            all_reports = json.load(f)
        print(f"Loaded {len(all_reports)} URLs from {URLS_FILE}\n")
    else:
        all_reports = []
        resp = test
        page = 1
        while True:
            soup = BeautifulSoup(resp.text, "html.parser")
            for link in soup.find_all("a", href=re.compile(r"rpvf-eng\.aspx")):
                href = link["href"]
                if not href.startswith("http"): href = BASE_URL + "/" + href
                all_reports.append({"name": link.get_text(strip=True), "url": href.replace("&amp;", "&")})
            print(f"  Page {page}: total {len(all_reports)} URLs")
            if page % 10 == 0:
                with open(URLS_FILE, "w") as f: json.dump(all_reports, f)
            next_btn = None
            for inp in soup.find_all("input", id=re.compile(r"btnNext")):
                if not inp.has_attr("disabled") and "Disabled" not in str(inp.get("class", "")):
                    next_btn = inp; break
            if not next_btn:
                print(f"\nAll pages collected! {len(all_reports)} URLs total.\n")
                break
            vs = soup.find("input", {"id": "__VIEWSTATE"})["value"]
            ev = soup.find("input", {"id": "__EVENTVALIDATION"})["value"]
            vg = soup.find("input", {"id": "__VIEWSTATEGENERATOR"})["value"]
            resp = fetch(s, "POST", LIST_URL, data={
                "__EVENTTARGET": "", "__EVENTARGUMENT": "", "__VIEWSTATE": vs,
                "__VIEWSTATEGENERATOR": vg, "__VIEWSTATEENCRYPTED": "",
                "__EVENTVALIDATION": ev, next_btn["name"]: "",
            })
            if not resp:
                print(f"\nConnection lost at page {page}. Re-run to resume.")
                break
            page += 1
            time.sleep(0.5)
        with open(URLS_FILE, "w") as f: json.dump(all_reports, f)

    # Step 2: Download & parse
    done_names = set()
    results = []
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            results = json.load(f)
        done_names = {r.get("report_name", "") for r in results}
        remaining = len(all_reports) - len(done_names)
        if remaining > 0:
            print(f"Resuming: {len(done_names)} done, {remaining} remaining.\n")
        else:
            print(f"All {len(done_names)} reports downloaded.\n")

    total = len(all_reports)
    new_dl = 0
    for i, report in enumerate(all_reports):
        if report["name"] in done_names: continue
        r = fetch(s, "GET", report["url"])
        if r:
            try:
                parsed = parse_report_html(r.text)
                parsed["report_name"] = report["name"]
                nc = len(parsed.get("comments", []))
                nd = len(parsed.get("demographics", []))
                ns = len(parsed.get("score_distributions", {}))
                results.append(parsed)
                new_dl += 1
                print(f"  [{i+1}/{total}] ✓ {report['name']} ({nc} comments, {ns} scored, {nd} demo)")
            except Exception as e:
                results.append({"report_name": report["name"], "error": str(e)})
                print(f"  [{i+1}/{total}] ✗ {e}")
        else:
            results.append({"report_name": report["name"], "error": "download failed"})
            print(f"  [{i+1}/{total}] ✗ download failed")
        if new_dl % 50 == 0 and new_dl > 0:
            with open(RESULTS_FILE, "w") as f:
                json.dump(results, f, ensure_ascii=False)
            print(f"  ... saved ({len(results)} reports)")
        time.sleep(0.4)

    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Step 3: CSV
    print("\nConverting to CSV...")
    results_to_csv(results, OUTPUT_CSV)

    ok = sum(1 for r in results if "error" not in r)
    print(f"\n{'='*60}")
    print(f"DONE! {ok}/{total} reports")
    print(f"JSON: {RESULTS_FILE}")
    print(f"CSV:  {OUTPUT_CSV}")
    print(f"{'='*60}")