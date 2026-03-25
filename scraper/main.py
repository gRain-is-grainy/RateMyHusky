"""
TRACE Master Scraper v4
Scrapes all reports, outputs one CSV with all fields.

Usage:
  1. Update COOKIES if expired
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
# CONFIGURATION
# ═══════════════════════════════════════════

COOKIES = {
    "_ga": "GA1.1.509540977.1774198087",
    "cookiesession1": "678B2A87D44C29A1595AAB0DF919F4B6",
    "BlueNextOriginalPath": "/rv.aspx?uid=5660d4f83cbd7a5460463a3454acf9bb&redi=1&SelectedIDforPrint=c0d7284255dab34acc9fd045c1e1ea53e7b9e7efa42c4841dac738545aa34abbf47a5f340cb81c1ec2b5ac2b3844c7cf&ReportType=2&isLive=0&dsid=498dbdbc97a49b840a35dfe28dbd4975&regl=en-US",
    "BlueNextRefreshToken": "0438172A0B6259A21009895240F28CA452D2CF977BACAD09FA04C8FD097A1F10",
    "BlueNextAccessToken": "eyJhbGciOiJSUzI1NiIsImtpZCI6IkEyOTk1ODFDQTAwRDE0QUZCRkQ0RjgzOEMwQzVDNTdERDgwMzJGOENSUzI1NiIsIng1dCI6Im9wbFlIS0FORkstXzFQZzR3TVhGZmRnREw0dyIsInR5cCI6ImF0K2p3dCJ9.eyJuYmYiOjE3NzQ0MDM0ODQsImV4cCI6MTc3NDQwNzA4NCwiaXNzIjoiaHR0cHM6Ly9ub3J0aGVhc3Rlcm4tYXV0aC5ibHVlcmEuY29tIiwiY2xpZW50X2lkIjoiQUE2M0U3NjMtRTdFRS00NEU4LUI5M0UtQTYwRTA2QTM3QzkyIiwic3ViIjoiYWIyNjI1NWItYzVjOS00NDM5LTk4YzQtMDQxNDFhNzEwMGRhIiwiYXV0aF90aW1lIjoxNzc0NDAzNDgxLCJpZHAiOiIwNjc0ZDVlNi0wYWVjLTRhZGEtODc2Yy03MDkwZDIxMjllNzEiLCJnc2lkIjoiODIwMzJFMjEwQjE2M0E1NEQwOTlGRkUxRkYyNkMwNjciLCJzc29faWQiOiIxIiwiZXh0ZXJuYWxfaWRwX3VzZXJuYW1lIjoiMDAyNTcxOTkzIiwianRpIjoiRTMyQTczNUZCRUI3NTUxMDEzQzQ2RTU0N0ZBOTQwREIiLCJpYXQiOjE3NzQ0MDM0ODQsInNjb3BlIjpbIm9wZW5pZCIsIm9mZmxpbmVfYWNjZXNzIl0sImFtciI6WyJleHRlcm5hbCJdfQ.bTNJQ5rfOtRHwrONW9dD_A9vR0ka3gRjWaH-usxyIXn1jIXDvDWvvJKLa0jPUAogzI35wAgsYfdtDFxLUbzySAoU4mUh4-VVMCWtNPoznuOEmzTeg39q7LYwEKrGVjCJwY1oXqGT4yefsP1WFQsQofsx3-qXgStrji29Zg4rLCCBwRyEUonfrpOox9woCQ9DZFZYdslf-ykuXVSWrzHHAWx5NS18PksIO5VekRHD-rLa-CyhG5RmYWPeQx4nXDleCOO-3bPltVpdZmnDEmHj1iwgGURYzFOWMnTLpxM0UC48iUwtpgC0c2UtCWvh_y077oxQtmHZTBvXRQiFE0UEAr4S9QztGYU5mkZrQrWtPdywzgQV7XqTdynAiG21koa2V9j_xmHHC9k4pJWxp7DO05VDPloD_jfdvtVx9sktiRGtnGDic69qx-lSMPxkaidvKWykvkv4in6n3oqY-37YxeOD4Si-tGeOeuWZRHOF9Z_XN8PvZzaZd3uQyrKaJC1gQ0qK7UBqWq-McwwpbSVy7XhtRdmJYAtNeERpKjVv31cT7eJGRG7LrkdVrcdtoPuu1aOg-waQZP-Zwm8Wax2ewZq38aR-Te6W8xyG9PucSM6OjXnKBvvtQ2Sj-2jpVjrC0Biu5zOUrkbuPmJv-YJrp6jkToWaDckq9NmyT3w2lHU",
    "BlueNextIdToken": "eyJhbGciOiJSUzI1NiIsImtpZCI6IkEyOTk1ODFDQTAwRDE0QUZCRkQ0RjgzOEMwQzVDNTdERDgwMzJGOENSUzI1NiIsIng1dCI6Im9wbFlIS0FORkstXzFQZzR3TVhGZmRnREw0dyIsInR5cCI6IkpXVCJ9.eyJuYmYiOjE3NzQ0MDM0ODQsImV4cCI6MTc3NDQwMzc4NCwiaXNzIjoiaHR0cHM6Ly9ub3J0aGVhc3Rlcm4tYXV0aC5ibHVlcmEuY29tIiwiYXVkIjoiQUE2M0U3NjMtRTdFRS00NEU4LUI5M0UtQTYwRTA2QTM3QzkyIiwiaWF0IjoxNzc0NDAzNDg0LCJhdF9oYXNoIjoiVzhqY0U5VF9BRWkxdEFVWEw4OUZrdyIsInNfaGFzaCI6Ik8xZUVzYXlRQ0VmNXhTSlZwWkZTdUEiLCJzdWIiOiJhYjI2MjU1Yi1jNWM5LTQ0MzktOThjNC0wNDE0MWE3MTAwZGEiLCJhdXRoX3RpbWUiOjE3NzQ0MDM0ODEsImlkcCI6IjA2NzRkNWU2LTBhZWMtNGFkYS04NzZjLTcwOTBkMjEyOWU3MSIsImFtciI6WyJleHRlcm5hbCJdLCJnc2lkIjoiODIwMzJFMjEwQjE2M0E1NEQwOTlGRkUxRkYyNkMwNjcifQ.CgiIDnm2YAQi8XpfnIsEARJboy3WB5CK18rWLyLtvYUtFgYMIpI1gukBQEjXY58GFFEeF3cMpgDYsIknl7iHFdYR7XLXQfqQvfBLcSfXJFKdO-hJRz0_q-Dew8kzZR1NUGFh7i6gBrzljHghZNmsKOcFK6iGqcRiT2N8h1CiDWvCvDZI_FqPN03rbV7KUI8i6Wp95Wy1h-x9NdzfAygo6zwnlaqjGBqFbvmi6UmqYN0Pn0gQZFjG2eYZbKEK1gUmX_zqTerHRkJbSupPW2Y2fKtPE3BrqOOQNcxF7nl6836jCbmt1sUvI4XGEpMNr5uo-WhQec9xbe7Mkbumoq-15LAeNRUf8zyrMKYq7rvY11gPuAEitNwxAtuXQpVt1A5gT09w6WoMobq7UmYNL0nUizImEyhBzMLBMy-AXbB4JSOxuTUQ0kzmS6Rw0rI3TV_eu2QWaN3eE7BRohFD-CMIUEATV78j1wCSfL1kkoDgEmItnP1uZ8WYUH5LiH7PUu-sjquP8ai8uvVOPJCsNs9FdZzAj9hI_sZ6Bpe9QcI1M-J67d3kkPclbSP0MwJ7NS7yw8-JAqE2TzW2TNZNtRH52xDhya8_C6v_hb4cqzaL4AfhHvX2qBNArBG_jO0CwDflOMTeRFe-NVHriDGr2sOdXamhTFzeZ0KNLvqrypEq7ko",
    "ASP.NET_SessionId": "awabay4rqgs4qyiujtkuez5r",
    "CookieName": "ADB3F981191C74784F6F923C29F3EFC7C7D073110D3DC7979F64E854C50D753AF8870B2F5C9CFC09E04AFDA913F02491D04967295C63757120DBD229A9894CED664B3DA0DAD4ADE7E2D7D5645844EBF9D003D4198CBBF1C056BE5996C60C0A3D400FF091C267DEC558AC7DCE54ADA60185B2FC5445834BDC900FA78FB7818D120E00F2CCEF2994890D4B248E611AE98CAC55DC475D97AF88B3D8425794C88313F26A1681BEF6D4B83A2C287E082980EDD4812873329508ECF36E5E9F86A8E884B79A54A8AAC182571AF1E1A225186370CF54999A2F6CE6F7816A5A724331F344",
    "session_token": "54f4183a3e3a49f7ab699544c397cf13",
    "_ga_262EDTH0JM": "GS2.1.s1774403482$o8$g0$t1774403527$j15$l0$h0",
}

BASE_URL = "https://northeastern-bc.bluera.com"

# ── SET SEMESTER HERE ──
LIST_URL = f"{BASE_URL}/rpvlf.aspx?rid=fdf8a2a3-773c-42df-9284-09b0303fb52a&regl=en-US&haslang=true"
# Summer 2025:
# LIST_URL = f"{BASE_URL}/rpvlf.aspx?rid=fdf8a2a3-773c-42df-9284-09b0303fb52a&regl=en-US&haslang=true"

URLS_FILE = "trace_urls.json"
RESULTS_FILE = "summer.json"
OUTPUT_CSV = "summer.csv"
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


def parse_report_html(html_text):
    soup = BeautifulSoup(html_text, "html.parser")

    # Metadata
    title_tag = soup.find("title")
    title_text = title_tag.text.strip() if title_tag else ""
    m = re.search(r"Student TRACE report for (.+)", title_text)
    course_info = m.group(1).strip() if m else title_text
    display_name = title_text.replace(" - ", "").strip()

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
    rate_el = soup.find("span", id=re.compile(r"lblRespRateValue"))
    audience = int(aud_el.text.strip()) if aud_el else None
    responses = int(resp_el.text.strip()) if resp_el else None
    response_rate = rate_el.text.strip() if rate_el else None

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

    return {
        "display_name": display_name,
        "course_info": course_info,
        "term": term,
        "created_date": created_date,
        "audience": audience,
        "responses": responses,
        "response_rate": response_rate,
        "sections": sections,
        "comments": comments,
        "score_distributions": {q: dict(Counter(scores)) for q, scores in score_dist.items()},
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
        "display_name", "term", "created_date", "course_info",
        "audience", "responses", "response_rate",
        "section", "question",
        "Number of Responses", "Response Rate",
        "Course Mean", "Dept. Mean", "Univ. Mean",
        "Course Median", "Dept. Median", "Univ. Median",
        "count_5", "count_4", "count_3", "count_2", "count_1",
        "comment_prompt", "comments_json",
    ]
    rows = []
    for r in results:
        if "error" in r: continue
        base = {
            "display_name": r.get("display_name", ""),
            "term": r.get("term", ""),
            "created_date": r.get("created_date", ""),
            "course_info": r.get("course_info", ""),
            "audience": r.get("audience", ""),
            "responses": r.get("responses", ""),
            "response_rate": r.get("response_rate", ""),
        }
        score_dists = r.get("score_distributions", {})
        comments_by_prompt = {}
        for c in r.get("comments", []):
            comments_by_prompt.setdefault(c["prompt"], []).append(c["comment"])

        for s in r.get("sections", []):
            for q in s.get("questions", []):
                row = {**base, "section": s["section"]}
                qtext = q.get("question", "")
                if qtext.isdigit() and "Effectiveness" in s["section"]:
                    row["question"] = "What is your overall rating of this instructor teaching effectiveness?"
                    row["Number of Responses"] = int(qtext)
                    keys = [k for k in q if k != "question"]
                    vals = [q[k] for k in keys]
                    correct = ["Response Rate", "Course Mean", "Dept. Mean", "Univ. Mean",
                               "Course Median", "Dept. Median", "Univ. Median"]
                    for i, k in enumerate(correct):
                        row[k] = vals[i] if i < len(vals) else ""
                    qtext = row["question"]
                else:
                    row["question"] = qtext
                    for k in ["Number of Responses", "Response Rate", "Course Mean",
                              "Dept. Mean", "Univ. Mean", "Course Median",
                              "Dept. Median", "Univ. Median"]:
                        row[k] = q.get(k, "")
                dist = score_dists.get(qtext, {})
                row["count_5"] = dist.get(5, 0)
                row["count_4"] = dist.get(4, 0)
                row["count_3"] = dist.get(3, 0)
                row["count_2"] = dist.get(2, 0)
                row["count_1"] = dist.get(1, 0)
                rows.append(row)

        for prompt, comment_list in comments_by_prompt.items():
            row = {**base, "section": "Comments",
                   "comment_prompt": prompt,
                   "comments_json": json.dumps(comment_list, ensure_ascii=False)}
            rows.append(row)

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"Saved {len(rows)} rows to {output_file}")


if __name__ == "__main__":
    s = requests.Session()
    s.cookies.update(COOKIES)
    s.headers.update({"User-Agent": "Mozilla/5.0"})

    print("Testing session...")
    test = fetch(s, "GET", LIST_URL)
    if not test or "Sign in" in test.text:
        print("ERROR: Cookies expired. Paste fresh ones.")
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
                nd = len(parsed.get("score_distributions", {}))
                results.append(parsed)
                new_dl += 1
                print(f"  [{i+1}/{total}] ✓ {report['name']} ({nc} comments, {nd} scored q's)")
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