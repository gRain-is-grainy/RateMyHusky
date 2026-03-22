"""
TRACE Report Scraper - SUMMER 2025
Run: source ~/trace-env/bin/activate && python3 trace_summer.py
"""

import requests
import json
import time
import re
import sys
import os
from bs4 import BeautifulSoup
from html.parser import HTMLParser

COOKIES = {
    "_ga": "GA1.1.509540977.1774198087",
    "cookiesession1": "678B2A87D44C29A1595AAB0DF919F4B6",
    "BlueNextOriginalPath": "/rv.aspx?uid=5660d4f83cbd7a5460463a3454acf9bb&redi=1&SelectedIDforPrint=c0d7284255dab34acc9fd045c1e1ea53e7b9e7efa42c4841dac738545aa34abbf47a5f340cb81c1ec2b5ac2b3844c7cf&ReportType=2&isLive=0&dsid=498dbdbc97a49b840a35dfe28dbd4975&regl=en-US",
    "BlueNextRefreshToken": "F0F89D92CCB9F8601FCF65C3FC86C7E0EB8A2716A6A2ACE6539C7D14F3E46255",
    "BlueNextAccessToken": "eyJhbGciOiJSUzI1NiIsImtpZCI6IkEyOTk1ODFDQTAwRDE0QUZCRkQ0RjgzOEMwQzVDNTdERDgwMzJGOENSUzI1NiIsIng1dCI6Im9wbFlIS0FORkstXzFQZzR3TVhGZmRnREw0dyIsInR5cCI6ImF0K2p3dCJ9.eyJuYmYiOjE3NzQyMTM3MjgsImV4cCI6MTc3NDIxNzMyOCwiaXNzIjoiaHR0cHM6Ly9ub3J0aGVhc3Rlcm4tYXV0aC5ibHVlcmEuY29tIiwiY2xpZW50X2lkIjoiQUE2M0U3NjMtRTdFRS00NEU4LUI5M0UtQTYwRTA2QTM3QzkyIiwic3ViIjoiYWIyNjI1NWItYzVjOS00NDM5LTk4YzQtMDQxNDFhNzEwMGRhIiwiYXV0aF90aW1lIjoxNzc0MjEzNzIzLCJpZHAiOiIwNjc0ZDVlNi0wYWVjLTRhZGEtODc2Yy03MDkwZDIxMjllNzEiLCJnc2lkIjoiMkYwRDMxRkEzN0MwQkI4N0ExRTJCRThGQTQzRjE1Q0UiLCJzc29faWQiOiIxIiwiZXh0ZXJuYWxfaWRwX3VzZXJuYW1lIjoiMDAyNTcxOTkzIiwianRpIjoiNDBBNkRGQ0YxMDUyMUUyNDcwNEUwMkNEMzBGNEUyQzUiLCJpYXQiOjE3NzQyMTM3MjgsInNjb3BlIjpbIm9wZW5pZCIsIm9mZmxpbmVfYWNjZXNzIl0sImFtciI6WyJleHRlcm5hbCJdfQ.vLLznsG3J-bDwrMT876alsb2bANhch-Eybl9aC0gBwRi4BLnmZ4w93n6w_qrkhTLrNOL3UDaPvXe4JRpS2rqbvKorRayTetA_LUVWo6o0HAoREwOe6MtKAOHYAbPoPeqh_KVw0fESrI49kfv4Am5aNjnn2tn621LdJIPlhhzrTbQlqbtGSmHh-npt-NK8dP-FoUME_k83nhrYvv2c_UHZFd8bJM-mERF_RPMGt5YUAKIjISC8Aeisqz-CuruZvVFtbxhFZuAmR6tPsJ6OZzz7prM0CgcsymVYypPKuiBEmIGz3IoiXdDmZxb51bLi-mWYlTBE97lFuhi5ZlrF3smbPUXZAzVNT_k2JIu6HKXhZKklp-qOQn1JoXOkcB8ARsYbDnnkvYwHC4bosXUARgppSQPR8L9A10zhW--hEpfeeBZkENcBDbaLjao70lOMAVaFQhVmfO6gw2KpUCEA3ViwT7T32neBHshsWkWEVn5wR-9nFyMaMCu3Sr70B4btvfbckdsAV8CmNnwtY8YFxlOlruD2vlh70gBYIVwSHxw7MdVtsf2VHovulRXu-kOOmPaSR8RUBfWFfRw1LRcldlTc54lLhcpux0O9v79oMqUzIQ1ZuJg_NFfZHF85Nx5IZIrtjzsj5QXRqAr_tlWVLPBCOzAnqdChyOANq_M2b-a8nM",
    "BlueNextIdToken": "eyJhbGciOiJSUzI1NiIsImtpZCI6IkEyOTk1ODFDQTAwRDE0QUZCRkQ0RjgzOEMwQzVDNTdERDgwMzJGOENSUzI1NiIsIng1dCI6Im9wbFlIS0FORkstXzFQZzR3TVhGZmRnREw0dyIsInR5cCI6IkpXVCJ9.eyJuYmYiOjE3NzQyMTM3MjgsImV4cCI6MTc3NDIxNDAyOCwiaXNzIjoiaHR0cHM6Ly9ub3J0aGVhc3Rlcm4tYXV0aC5ibHVlcmEuY29tIiwiYXVkIjoiQUE2M0U3NjMtRTdFRS00NEU4LUI5M0UtQTYwRTA2QTM3QzkyIiwiaWF0IjoxNzc0MjEzNzI4LCJhdF9oYXNoIjoiR01GMjJENkhkVmlNRlBfRUJyRHU4ZyIsInNfaGFzaCI6IlZZUjFmZUE2WXVJREdkY1o0X3FlWGciLCJzdWIiOiJhYjI2MjU1Yi1jNWM5LTQ0MzktOThjNC0wNDE0MWE3MTAwZGEiLCJhdXRoX3RpbWUiOjE3NzQyMTM3MjMsImlkcCI6IjA2NzRkNWU2LTBhZWMtNGFkYS04NzZjLTcwOTBkMjEyOWU3MSIsImFtciI6WyJleHRlcm5hbCJdLCJnc2lkIjoiMkYwRDMxRkEzN0MwQkI4N0ExRTJCRThGQTQzRjE1Q0UifQ.oT9Rb_ggNsaxT140Gp3H4wFBbadN1yHUk_gSc_pHiWOKNee52KErr8hz9rRSGyhoh_kray4-gABmdJnSa24C4AdJp7Jn0a7tWekqvNuLhvZdEnc8zt3_sj-rdmSKm5hOG8cz5TpMtNM9tUlgL5AUBkfTXyV8-zv2oP97Zh96g2q52LQSSyY4kkpG3zXTPDHngv9vE1yF-K98Uy-1WbQ7Hk_oAKl5AdyxdChGqtkNecjl-dUud2Jmbcju-sWyiOztm9hmnXlTNZjDXrP1hgPI6JLVQumnqrXRjNI-7tYH45OBFQcVEoD7OTxNpDM6odh32YFm1SdLRA8SY3Z6-WgIWSZ17-i4n7B4b_Vea2eEJ0lI-GCFSZNsrMH-ygfcUk4z5oDN7dFE1wcaQzw4_R5itIHbgn2560gjKC5D850swv9R2d_E8y3y2l2bJBRHUTWos1tJYlu_9DMflrDKJXRNrA9aNsP_1bE6L3Qw2Htd33xJmb3g3JU-6RSJ3syJNFfHN_PIlUlYrA-Od3KrapuLBU-rPL0s5E22jRMVm2Jr7coDX9C2NDg-qM_kz3YWQzzN0OQwy5HFmtVc6USj5AGlrYk-J2Cy4RmJMrLGkY_r2BZ2nlkFKW8yc6iej4R0-FjC0P_A9ocfGgJAn4p-gWtzOX0OGplpfYUh_l8M1mFJRiI",
    "ASP.NET_SessionId": "ufnvtyfqdeyzp0dvwcdblj3t",
    "CookieName": "68B7F3E08C927BD6EF03132E8FE61CCF1028CA4F0DD0D35512F5E4935E662945726BEE6C353790F066CF4603167B6C2BB1B9335178DE13E85B4D0A61DD8CE40F108AC1AE4EF365C57459159D696D0F96B5BC9456260F21DEA7E8B067F23EB7CA43A10158066F2B60A983477BEEC124F84088E88C37FB908CA0A1A218CA2CD5C4D30E2A2C4A28D6D8B6C4A181924A43612F6FF8E84BED14A563559726FA881553298A16687CE884A8BA004A35189FD4B2E394D2D8DD7E284DFE0CB3150F40EFAC52D5BE897782424FE848B656AB18BAABC6E0165429E024ED3AF80DA528C802A4",
    "session_token": "1e544f013d274e50b18ce916fe6fadc6",
    "_ga_262EDTH0JM": "GS2.1.s1774213724$o3$g1$t1774213771$j13$l0$h0",
}

BASE_URL = "https://northeastern-bc.bluera.com"
LIST_URL = f"{BASE_URL}/rpvlf.aspx?rid=fdf8a2a3-773c-42df-9284-09b0303fb52a&regl=en-US&haslang=true"
TIMEOUT = 60
URLS_FILE = "trace_urls_summer.json"
RESULTS_FILE = "trace_summer.json"


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


def parse_report_html(html):
    soup = BeautifulSoup(html, "html.parser")
    title_text = soup.find("title").text if soup.find("title") else ""
    m = re.search(r"Student TRACE report for (.+)", title_text)
    course_info = m.group(1).strip() if m else title_text
    aud = soup.find("span", id=re.compile(r"lblInvited"))
    resp_el = soup.find("span", id=re.compile(r"lblResponded"))
    rate = soup.find("span", id=re.compile(r"lblRespRateValue"))
    headings = [h3.find("strong").get_text(strip=True) for h3 in soup.find_all("h3") if h3.find("strong")]
    tables = re.findall(r"<table class='block-table[^']*'>.*?</table>", html, re.DOTALL)
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
    return {
        "course_info": course_info,
        "audience": int(aud.text.strip()) if aud else None,
        "responses": int(resp_el.text.strip()) if resp_el else None,
        "response_rate": rate.text.strip() if rate else None,
        "sections": sections,
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


if __name__ == "__main__":
    s = requests.Session()
    s.cookies.update(COOKIES)
    s.headers.update({"User-Agent": "Mozilla/5.0"})

    print("Testing session...")
    test = fetch(s, "GET", LIST_URL)
    if not test or "Sign in" in test.text:
        print("ERROR: Cookies expired. Paste fresh ones and re-run.")
        sys.exit(1)
    print("Session valid!\n")

    # ── STEP 1: Collect all URLs (with resume) ──
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE) as f:
            all_reports = json.load(f)
        print(f"Found {URLS_FILE} with {len(all_reports)} URLs already collected.")
        ans = input("Skip URL collection and go to downloads? (y/n): ").strip().lower()
        if ans != "y":
            all_reports = []
    else:
        all_reports = []

    if not all_reports:
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
                print(f"\nAll pages collected! {len(all_reports)} URLs total.")
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
                print(f"\nConnection lost at page {page}. Progress saved. Re-run to resume.")
                break
            page += 1
            time.sleep(0.5)
        with open(URLS_FILE, "w") as f: json.dump(all_reports, f)
        print(f"Saved {len(all_reports)} URLs to {URLS_FILE}\n")

    # ── STEP 2: Download & parse (with resume) ──
    done_names = set()
    results = []
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            results = json.load(f)
        done_names = {r["report_name"] for r in results}
        print(f"Resuming downloads: {len(done_names)} done, {len(all_reports) - len(done_names)} remaining.\n")
    else:
        print(f"Downloading and parsing {len(all_reports)} reports...\n")

    total = len(all_reports)
    for i, report in enumerate(all_reports):
        if report["name"] in done_names:
            continue
        r = fetch(s, "GET", report["url"])
        if r:
            try:
                parsed = parse_report_html(r.text)
                parsed["report_name"] = report["name"]
                results.append(parsed)
                print(f"  [{i+1}/{total}] ✓ {report['name']}")
            except Exception as e:
                results.append({"report_name": report["name"], "error": str(e)})
                print(f"  [{i+1}/{total}] ✗ {e}")
        else:
            results.append({"report_name": report["name"], "error": "download failed"})
            print(f"  [{i+1}/{total}] ✗ download failed")

        if len(results) % 50 == 0:
            with open(RESULTS_FILE, "w") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"  ... progress saved ({len(results)} reports)")

        time.sleep(0.4)

    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    ok = sum(1 for r in results if "error" not in r)
    print(f"\n{'='*50}")
    print(f"DONE! {ok}/{total} reports saved to {RESULTS_FILE}")
    print(f"{'='*50}")