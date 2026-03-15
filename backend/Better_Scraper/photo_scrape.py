"""
NEU Faculty Headshot Scraper (v2 — Directory-First)

Two-phase approach:
  Phase 1: Scrape college directory listing pages (each page has ~10-50 people
           with photos already embedded). ~220 pages covers ~3000+ faculty.
  Phase 2: For professors not found in directories, fall back to slug-based
           URL guessing across all college subdomains.

Reads professor names from rmp_professors.csv and trace_courses.csv.
Outputs: professor_photos.csv (name, image_url, source_page)

Usage:
    python photo_scrape.py
    python photo_scrape.py --workers 10
    python photo_scrape.py --limit 50
    python photo_scrape.py --skip-directories   # slug-only mode (old behavior)
"""

__author__ = "Benjamin"
__version__ = "2.0.0"

import csv
import os
import re
import argparse
import unicodedata
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# ---------------------------------------------------------------------------
# College directory configurations
# ---------------------------------------------------------------------------
# Each entry: subdomain, directory path prefix, people path prefix
# Directory pages are paginated as {path}page/{n}/

DIRECTORY_CONFIGS = [
    {"subdomain": "www.khoury", "dir_path": "/people/",        "person_path": "/people/"},
    {"subdomain": "cos",        "dir_path": "/people/",        "person_path": "/people/"},
    {"subdomain": "damore-mckim","dir_path": "/people/",       "person_path": "/people/"},
    {"subdomain": "camd",       "dir_path": "/people/",        "person_path": "/people/"},
    {"subdomain": "bouve",      "dir_path": "/directory/",      "person_path": "/directory/"},
    {"subdomain": "cssh",       "dir_path": "/faculty/",        "person_path": "/faculty/"},
    {"subdomain": "law",        "dir_path": "/faculty/",        "person_path": "/faculty/"},
    {"subdomain": "cps",        "dir_path": "/faculty/",        "person_path": "/faculty/"},
]

# All subdomains to try for slug-based fallback (Phase 2)
ALL_SUBDOMAINS = [
    "www.khoury", "cos", "damore-mckim", "camd", "bouve", "cssh",
    "law", "cps", "coe", "ece", "mie", "cee", "che", "bioe",
]

# Department → preferred subdomains (tried first in Phase 2)
DEPT_TO_SUBDOMAINS = {
    "Computer Science": ["www.khoury"], "Information Science": ["www.khoury"],
    "Cybersecurity": ["www.khoury"], "Data Science": ["www.khoury"],
    "Computer Engineering": ["www.khoury"],
    "Engineering": ["coe", "ece", "mie", "cee", "che", "bioe"],
    "Electrical Engineering": ["ece", "coe"],
    "Mechanical Engineering": ["mie", "coe"],
    "Civil Engineering": ["cee", "coe"],
    "Chemical Engineering": ["che", "coe"],
    "Bioengineering": ["bioe", "coe"],
    "Electrical & Computer Engr": ["ece", "coe"],
    "Mechanical & Industrial Eng": ["mie", "coe"],
    "Civil & Environmental Eng": ["cee", "coe"],
    "Mathematics": ["cos"], "Physics": ["cos"], "Chemistry": ["cos"],
    "Biology": ["cos"], "Biochemistry": ["cos"],
    "Environmental Science": ["cos"], "Marine Sciences": ["cos"],
    "Behavioral Neuroscience": ["cos"], "Math": ["cos"],
    "Business": ["damore-mckim"], "Finance": ["damore-mckim"],
    "Accounting": ["damore-mckim"], "Marketing": ["damore-mckim"],
    "Management": ["damore-mckim"], "Business Administration": ["damore-mckim"],
    "Entrepreneurship": ["damore-mckim"], "Supply Chain Management": ["damore-mckim"],
    "Art": ["camd"], "Communication Studies": ["camd"], "Communication": ["camd"],
    "Journalism": ["camd"], "Music": ["camd"], "Design": ["camd"],
    "Theater": ["camd"], "Architecture": ["camd"],
    "Health Science": ["bouve"], "Nursing": ["bouve"],
    "Pharmacy": ["bouve"], "Physical Therapy": ["bouve"],
    "Speech Language Pathology": ["bouve"],
    "Political Science": ["cssh"], "Economics": ["cssh"], "History": ["cssh"],
    "Psychology": ["cssh"], "Sociology": ["cssh"], "Philosophy": ["cssh"],
    "English": ["cssh"], "Writing": ["cssh"], "Criminal Justice": ["cssh"],
    "Linguistics": ["cssh"], "Languages": ["cssh"],
    "Law": ["law"],
    "Education": ["cps"],
}

# Images to skip — banners, placeholders, research images, etc.
SKIP_PATTERNS = [
    "placeholder", "default", "silhouette", "no-photo", "avatar",
    "generic", "blank", "mystery", "logo", "icon", "default-person",
    "person-banner", "notched-n", "behrakis", "headshot-placeholder",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_name(name):
    """Normalize a name for matching: lowercase, ASCII, single spaces."""
    s = str(name).strip().lower()
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def name_to_key(name):
    """Create a matching key: sorted words, no punctuation."""
    s = normalize_name(name)
    s = re.sub(r'[^a-z0-9 ]', '', s)
    return s


def name_to_slug(name):
    """Convert 'Jonathan Bell' → 'jonathan-bell'."""
    s = normalize_name(name)
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s


def slug_variations(name):
    """Generate multiple slug variations for a name.

    E.g. 'David John Choffnes' → ['david-john-choffnes', 'david-choffnes']
    'Mary O'Brien' → ['mary-obrien', 'mary-o-brien']
    """
    slugs = set()
    base = name_to_slug(name)
    slugs.add(base)

    parts = normalize_name(name).split()
    if len(parts) >= 2:
        # first-last (skip middle names)
        slugs.add(re.sub(r'[^a-z0-9]+', '-', f"{parts[0]} {parts[-1]}").strip('-'))
    if len(parts) >= 3:
        # first-middle-last
        slugs.add(re.sub(r'[^a-z0-9]+', '-', f"{parts[0]} {parts[1]} {parts[-1]}").strip('-'))

    return list(slugs)


def is_valid_photo(url):
    """Check if URL looks like an actual headshot, not a placeholder."""
    if not url:
        return False
    lower = url.lower()
    if any(p in lower for p in SKIP_PATTERNS):
        return False
    path = lower.split('?')[0]
    if not any(path.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
        return False
    return True


def make_absolute(url, page_url):
    """Convert a potentially relative URL to absolute."""
    if not url:
        return url
    if url.startswith('//'):
        return 'https:' + url
    if url.startswith('/'):
        parsed = urlparse(page_url)
        return f"{parsed.scheme}://{parsed.netloc}{url}"
    if not url.startswith('http'):
        return urljoin(page_url, url)
    return url


def make_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36"
        ),
    })
    return session


# ---------------------------------------------------------------------------
# Phase 1: Scrape directory listing pages
# ---------------------------------------------------------------------------

def _find_card_for_link(link):
    """Walk up from a link to find its enclosing card container.

    A valid card must be a block container (article/li/div) that is large
    enough to contain both the person's name and image. We skip small
    wrappers that match class keywords but only contain one element.
    """
    container = link
    for _ in range(7):
        container = container.parent
        if not container or container.name in ('body', 'html', '[document]'):
            return None
        if container.name == 'article':
            return container
        cls = ' '.join(container.get('class') or []).lower()
        is_card = False
        if container.name == 'li':
            is_card = True
        elif container.name == 'div' and (
            'card' in cls or 'member' in cls or 'profile' in cls
        ):
            is_card = True
        # For "person"-class divs, only match if they contain headings
        # (to avoid matching small wrappers like person-line-thumbnail)
        elif container.name == 'div' and ('person' in cls or 'directory' in cls):
            if container.find(['h2', 'h3', 'h4']):
                is_card = True
        if is_card:
            return container
    return None


def scrape_directory_page(session, url):
    """Scrape one directory listing page, returning list of people found.

    Returns list of dicts: {name, photo_url, profile_url}
    """
    try:
        resp = session.get(url, timeout=15, allow_redirects=True)
        if resp.status_code != 200:
            return [], False

        # Detect redirects away from the college site (e.g. COE -> coeaway)
        if urlparse(resp.url).netloc != urlparse(url).netloc:
            return [], False

        soup = BeautifulSoup(resp.text, 'html.parser')
        people = []
        profile_pattern = re.compile(
            r'/(people|faculty|directory|person)/[a-z0-9][\w-]+/?$', re.I
        )

        seen_urls = set()
        for link in soup.find_all('a', href=True):
            href = link['href']
            abs_href = make_absolute(href, resp.url)

            path = urlparse(abs_href).path.rstrip('/')
            if not profile_pattern.search(path):
                continue

            if abs_href in seen_urls:
                continue
            seen_urls.add(abs_href)

            # Find the enclosing card container for this link
            card = _find_card_for_link(link)

            # --- Extract name ---
            name = ''
            # Strategy 1: heading inside the link
            heading = link.find(['h2', 'h3', 'h4'])
            if heading:
                name = heading.get_text(strip=True)
            # Strategy 2: link text itself
            if not name:
                name = link.get_text(strip=True)

            # Clean up action phrases before checking if name is valid
            name = re.sub(
                r'\b(Read\s+bio|View\s+(Bio|Profile|Path)|See\s+(Path|Bio))\b',
                '', name, flags=re.I
            ).strip()
            name = name.replace('\u201c', '').replace('\u201d', '').replace('"', '')

            # Strategy 3: if name is still empty/short, try heading in card
            if card and (not name or len(name) < 3):
                for h in card.find_all(['h2', 'h3', 'h4']):
                    candidate = h.get_text(strip=True)
                    if candidate and len(candidate) >= 3 and not re.search(
                        r'\b(program|department|center|office|view|read)\b', candidate, re.I
                    ):
                        name = candidate
                        break

            if not name or len(name) < 3 or len(name) > 80:
                continue
            if name.lower() in ('next', 'previous', 'show all', 'load more'):
                continue

            # --- Extract photo ---
            photo_url = ''
            if card:
                img = card.find('img')
                if img:
                    src = img.get('src', '') or img.get('data-src', '')
                    src = make_absolute(src, resp.url)
                    if is_valid_photo(src):
                        photo_url = src

            people.append({
                'name': name,
                'photo_url': photo_url,
                'profile_url': abs_href,
            })

        # Find the next page URL (different colleges use different formats)
        next_url = None
        next_link = (
            soup.find('a', class_=re.compile(r'\bnext\b', re.I))
            or soup.find('a', attrs={'aria-label': re.compile(r'next', re.I)})
        )
        # Fallback: find link with "Next" in text
        if not next_link:
            for a in soup.find_all('a', href=True):
                if re.search(r'^Next\b', a.get_text(strip=True), re.I):
                    next_link = a
                    break
        if next_link and next_link.get('href'):
            next_url = make_absolute(next_link['href'], resp.url)

        return people, next_url

    except Exception:
        return [], None


def scrape_all_directories(session, workers=10):
    """Scrape all college directory pages, returning name→{photo_url, profile_url} mapping.

    Uses threading to scrape multiple colleges in parallel.
    """
    print("\n  Phase 1: Scraping college directory pages...")
    directory_map = {}  # normalized_name → {name, photo_url, profile_url}

    def scrape_one_college(config):
        """Scrape all pages for one college directory."""
        subdomain = config['subdomain']
        dir_path = config['dir_path']
        url = f"https://{subdomain}.northeastern.edu{dir_path}"
        college_people = []

        max_pages = 100  # safety limit
        for _ in range(max_pages):
            people, next_url = scrape_directory_page(session, url)
            college_people.extend(people)

            if not next_url or not people:
                break
            url = next_url

        return subdomain, college_people

    # Scrape all colleges in parallel
    college_results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(scrape_one_college, c): c for c in DIRECTORY_CONFIGS}
        pbar = tqdm(total=len(DIRECTORY_CONFIGS), desc="  Directories", unit=" college")

        for future in as_completed(futures):
            try:
                subdomain, people = future.result()
                college_results.append((subdomain, people))
                pbar.set_postfix_str(f"{subdomain}: {len(people)} people")
            except Exception:
                pass
            pbar.update(1)

        pbar.close()

    # Build the mapping
    total_people = 0
    total_with_photos = 0
    for subdomain, people in college_results:
        for person in people:
            key = name_to_key(person['name'])
            if not key:
                continue
            total_people += 1
            # Prefer entries that have photos over those that don't
            existing = directory_map.get(key)
            if existing and existing['photo_url'] and not person['photo_url']:
                continue  # keep the one with a photo
            directory_map[key] = person
            if person['photo_url']:
                total_with_photos += 1

    print(f"  Found {total_people} people in directories ({total_with_photos} with photos)")
    return directory_map


# ---------------------------------------------------------------------------
# Phase 2: Slug-based fallback for individual profile pages
# ---------------------------------------------------------------------------

def extract_photo_from_profile(html, page_url):
    """Extract the professor headshot URL from an individual profile page."""
    soup = BeautifulSoup(html, 'html.parser')
    candidates = []

    for img in soup.find_all('img'):
        src = img.get('src', '') or img.get('data-src', '')
        if not src:
            continue

        # Must be an uploaded image (not theme assets)
        if 'wp-content/uploads' not in src and 'pcdn.co' not in src:
            continue

        # Skip tiny images
        width = img.get('width')
        height = img.get('height')
        if width and height:
            try:
                if int(width) < 100 or int(height) < 100:
                    continue
            except ValueError:
                pass

        # Skip nav/header/footer images
        parent_classes = set()
        for parent in img.parents:
            for cls in (parent.get('class') or []):
                parent_classes.add(cls.lower())
            if parent.get('id'):
                parent_classes.add(parent['id'].lower())

        if {'nav', 'header', 'footer', 'menu', 'sidebar', 'featured-nav'} & parent_classes:
            continue

        src = make_absolute(src, page_url)
        if not is_valid_photo(src):
            continue

        score = 0
        if {'main', 'content', 'entry', 'article', 'person', 'profile', 'bio', 'figure'} & parent_classes:
            score += 10
        if img.get('srcset'):
            score += 5
        # Images with person-related alt text get a boost
        alt = (img.get('alt') or '').lower()
        if alt and alt not in ('', 'image', 'photo'):
            score += 3

        candidates.append((score, src))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def try_slug_lookup(session, name, department):
    """Try to find a professor's photo via slug-based URL guessing.

    Uses HEAD requests first to quickly filter 404s, then GET for 200s.
    Only tries the professor's college subdomains + a small fallback set.
    """
    slugs = slug_variations(name)
    path_patterns = ["/people/{slug}/", "/faculty/{slug}/", "/directory/{slug}/"]

    # Only try department-specific subdomains + the 3 biggest colleges as fallback
    preferred = DEPT_TO_SUBDOMAINS.get(department, [])
    fallback = [s for s in ["www.khoury", "cos", "cssh", "damore-mckim", "camd", "bouve"]
                if s not in preferred]
    subdomains = preferred + fallback

    for slug in slugs:
        for subdomain in subdomains:
            for pattern in path_patterns:
                url = f"https://{subdomain}.northeastern.edu{pattern.format(slug=slug)}"
                try:
                    head = session.head(url, timeout=5, allow_redirects=True)
                    if head.status_code != 200:
                        continue
                    if urlparse(head.url).netloc != urlparse(url).netloc:
                        continue

                    resp = session.get(url, timeout=10, allow_redirects=True)
                    if resp.status_code != 200:
                        continue

                    photo_url = extract_photo_from_profile(resp.text, resp.url)
                    if photo_url:
                        return photo_url, resp.url
                except Exception:
                    continue

    return None, None


# ---------------------------------------------------------------------------
# Loading professors & matching
# ---------------------------------------------------------------------------

def load_professors(data_dir):
    """Load unique professor names + departments from CSVs."""
    profs = {}  # name_key → {name, department}

    rmp_path = os.path.join(data_dir, "rmp_professors.csv")
    if os.path.exists(rmp_path):
        with open(rmp_path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                name = str(row.get('name', '')).strip()
                dept = str(row.get('department', '')).strip()
                if name:
                    key = normalize_name(name)
                    if key not in profs:
                        profs[key] = {'name': name, 'department': dept}

    trace_path = os.path.join(data_dir, "trace_courses.csv")
    if os.path.exists(trace_path):
        with open(trace_path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                first = str(row.get('instructorFirstName', '')).strip()
                last = str(row.get('instructorLastName', '')).strip()
                dept = str(row.get('departmentName', '')).strip()
                if first and last:
                    name = f"{first} {last}"
                    key = normalize_name(name)
                    if key not in profs:
                        profs[key] = {'name': name, 'department': dept}

    return list(profs.values())


def match_prof_to_directory(prof, directory_map):
    """Try to match a professor to a directory entry using multiple strategies."""
    name = prof['name']

    # Strategy 1: Exact key match
    key = name_to_key(name)
    if key in directory_map:
        return directory_map[key]

    # Strategy 2: first-last match (skip middle names in our name)
    parts = normalize_name(name).split()
    if len(parts) >= 3:
        first_last = re.sub(r'[^a-z0-9 ]', '', f"{parts[0]} {parts[-1]}")
        if first_last in directory_map:
            return directory_map[first_last]

    # Strategy 3: Check if directory has an entry with middle name where we don't
    # e.g., our "David Choffnes" matches directory's "David R Choffnes"
    if len(parts) == 2:
        first, last = parts[0], parts[-1]
        for dir_key, entry in directory_map.items():
            dir_parts = dir_key.split()
            if len(dir_parts) >= 2 and dir_parts[0] == first and dir_parts[-1] == last:
                return entry

    return None


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def scrape_photos(profs, workers=15, limit=None, skip_directories=False):
    """Full two-phase scraping pipeline."""
    if limit:
        profs = profs[:limit]

    session = make_session()
    results = []

    # Phase 1: Directory scraping
    if not skip_directories:
        directory_map = scrape_all_directories(session, workers=min(workers, 8))
    else:
        directory_map = {}

    # Match professors against directory
    unmatched = []         # no directory match at all
    matched_no_photo = []  # matched but no photo in directory listing
    dir_found = 0

    print(f"\n  Matching {len(profs)} professors against directory...")
    for prof in profs:
        match = match_prof_to_directory(prof, directory_map)
        if match and match['photo_url']:
            results.append({
                'name': prof['name'],
                'image_url': match['photo_url'],
                'source_page': match['profile_url'],
            })
            dir_found += 1
        elif match and match['profile_url']:
            # Have profile URL but no photo — will fetch the profile page directly
            matched_no_photo.append((prof, match['profile_url']))
        else:
            unmatched.append(prof)

    print(f"  Phase 1 matched: {dir_found}/{len(profs)} professors with photos")
    print(f"  ({len(matched_no_photo)} matched without photo, {len(unmatched)} unmatched)")

    # Phase 1.5: Fetch individual profile pages for directory-matched professors without photos
    if matched_no_photo:
        print(f"\n  Phase 1.5: Fetching {len(matched_no_photo)} known profile pages...")
        profile_found = 0
        pbar = tqdm(total=len(matched_no_photo), desc="  Profiles", unit=" prof")

        def fetch_profile(item):
            prof, profile_url = item
            try:
                resp = session.get(profile_url, timeout=10, allow_redirects=True)
                if resp.status_code == 200:
                    photo_url = extract_photo_from_profile(resp.text, resp.url)
                    if photo_url:
                        return prof, photo_url, resp.url
            except Exception:
                pass
            return prof, None, None

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(fetch_profile, item): item for item in matched_no_photo}
            for future in as_completed(futures):
                try:
                    prof, photo_url, source_page = future.result()
                    if photo_url:
                        results.append({
                            'name': prof['name'],
                            'image_url': photo_url,
                            'source_page': source_page,
                        })
                        profile_found += 1
                    else:
                        unmatched.append(prof)
                except Exception:
                    pass
                pbar.update(1)
        pbar.close()
        print(f"  Phase 1.5 found: {profile_found} additional professors")

    # Phase 2: Slug-based fallback for fully unmatched professors
    if unmatched:
        print(f"\n  Phase 2: Slug-based lookup for {len(unmatched)} remaining professors...")
        slug_found = 0
        pbar = tqdm(total=len(unmatched), desc="  Slug lookup", unit=" prof")

        def lookup_one(prof):
            return prof, try_slug_lookup(session, prof['name'], prof['department'])

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(lookup_one, p): p for p in unmatched}

            for future in as_completed(futures):
                try:
                    prof, (photo_url, source_page) = future.result()
                    if photo_url:
                        results.append({
                            'name': prof['name'],
                            'image_url': photo_url,
                            'source_page': source_page,
                        })
                        slug_found += 1
                except Exception:
                    pass
                pbar.update(1)

        pbar.close()
        print(f"  Phase 2 found: {slug_found} additional professors")

    total = len([r for r in results if r.get('image_url')])
    print(f"\n  Total: {total}/{len(profs)} professors with photos")
    return results


def save_csv(results, output_path):
    """Save results to CSV."""
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    with_photos = [r for r in results if r['image_url']]
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['name', 'image_url', 'source_page'])
        writer.writeheader()
        for row in with_photos:
            writer.writerow(row)

    print(f"  Saved {len(with_photos)} photo URLs to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Scrape NEU faculty headshot photos from college websites"
    )
    parser.add_argument(
        "--data-dir", type=str, default=None,
        help="Directory containing rmp_professors.csv and trace_courses.csv",
    )
    parser.add_argument(
        "--workers", type=int, default=15,
        help="Parallel threads (default 15)",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max professors to process (for testing)",
    )
    parser.add_argument(
        "-o", "--output", type=str, default=None,
        help="Output CSV path",
    )
    parser.add_argument(
        "--skip-directories", action="store_true",
        help="Skip Phase 1 directory scraping (slug-only mode)",
    )

    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = args.data_dir or os.path.join(script_dir, "output_data")
    output_path = args.output or os.path.join(data_dir, "professor_photos.csv")

    profs = load_professors(data_dir)
    print(f"  Loaded {len(profs)} unique professors")

    if not profs:
        print("  No professors found. Check your data directory.")
        return

    results = scrape_photos(
        profs,
        workers=args.workers,
        limit=args.limit,
        skip_directories=args.skip_directories,
    )

    save_csv(results, output_path)


if __name__ == "__main__":
    main()
