"""
NEU Faculty Headshot Scraper

Finds professor profile photos from Northeastern college websites.
Reads professor names from rmp_professors.csv and trace_courses.csv,
tries college-specific profile URLs, extracts headshot image URLs.

Outputs: professor_photos.csv (name, image_url, source_page)

Usage:
    python photo_scrape.py
    python photo_scrape.py --workers 10
    python photo_scrape.py --limit 50
"""

__author__ = "Benjamin"
__version__ = "1.0.0"

import csv
import os
import re
import time
import argparse
import unicodedata
from typing import List, Dict, Optional, Set, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed, Future

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# ---------------------------------------------------------------------------
# College → subdomain + URL patterns
# ---------------------------------------------------------------------------
# Each college has a people URL pattern. Some use /people/{slug}/,
# COE departments use /faculty/faculty-directory/ (not individual pages).
# We try the /people/{slug}/ pattern for all WordPress-based colleges.

COLLEGE_SUBDOMAINS = {
    "Khoury":               ["www.khoury"],
    "Engineering":          ["coe", "ece", "mie", "cee", "che", "bioe"],
    "Science":              ["cos"],
    "Business":             ["damore-mckim"],
    "CAMD":                 ["camd"],
    "Health Sciences":      ["bouve"],
    "CSSH":                 ["cssh"],
    "Law":                  ["law"],
    "Professional Studies": ["cps"],
}

# Department name → college key (matching your server.py COLLEGE_MAP)
DEPT_TO_COLLEGE = {
    "Computer Science": "Khoury", "Information Science": "Khoury",
    "Cybersecurity": "Khoury", "Data Science": "Khoury",
    "Computer Engineering": "Khoury",
    "Engineering": "Engineering", "Electrical Engineering": "Engineering",
    "Mechanical Engineering": "Engineering", "Civil Engineering": "Engineering",
    "Chemical Engineering": "Engineering", "Bioengineering": "Engineering",
    "Electrical & Computer Engr": "Engineering",
    "Mechanical & Industrial Eng": "Engineering",
    "Civil & Environmental Eng": "Engineering",
    "Mathematics": "Science", "Physics": "Science", "Chemistry": "Science",
    "Biology": "Science", "Biochemistry": "Science",
    "Environmental Science": "Science", "Marine Sciences": "Science",
    "Behavioral Neuroscience": "Science", "Math": "Science",
    "Business": "Business", "Finance": "Business", "Accounting": "Business",
    "Marketing": "Business", "Management": "Business",
    "Business Administration": "Business", "Entrepreneurship": "Business",
    "Supply Chain Management": "Business",
    "Art": "CAMD", "Communication Studies": "CAMD", "Communication": "CAMD",
    "Journalism": "CAMD", "Music": "CAMD", "Design": "CAMD",
    "Theater": "CAMD", "Architecture": "CAMD",
    "Health Science": "Health Sciences", "Nursing": "Health Sciences",
    "Pharmacy": "Health Sciences", "Physical Therapy": "Health Sciences",
    "Speech Language Pathology": "Health Sciences",
    "Political Science": "CSSH", "Economics": "CSSH", "History": "CSSH",
    "Psychology": "CSSH", "Sociology": "CSSH", "Philosophy": "CSSH",
    "English": "CSSH", "Writing": "CSSH", "Criminal Justice": "CSSH",
    "Linguistics": "CSSH", "Languages": "CSSH",
    "Law": "Law",
    "Education": "Professional Studies",
}

# Placeholder / generic images to skip
SKIP_PATTERNS = [
    "placeholder", "default", "silhouette", "no-photo", "avatar",
    "generic", "blank", "mystery", "logo", "icon",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_name(name):
    s = str(name).strip().lower()
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def name_to_slug(name):
    """Convert 'Jonathan Bell' → 'jonathan-bell'"""
    s = normalize_name(name)
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s


def is_valid_photo(url):
    """Check if URL looks like an actual headshot, not a placeholder."""
    if not url:
        return False
    lower = url.lower()
    if any(p in lower for p in SKIP_PATTERNS):
        return False
    # Must be an image
    if not any(lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
        # Check if URL has image extension before query params
        path = lower.split('?')[0]
        if not any(path.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
            return False
    return True


def extract_photo_from_html(html, page_url):
    """Extract the professor headshot URL from a profile page's HTML.

    Strategy:
    1. Look for wp-content/uploads images in the main content area
    2. Skip navigation/header images, logos, and tiny icons
    3. Prefer images that are reasonably large (not thumbnails)
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Strategy 1: Find images in the main content with wp-content/uploads
    # These are the actual uploaded headshots
    candidates = []

    for img in soup.find_all('img'):
        src = img.get('src', '') or img.get('data-src', '')
        if not src:
            continue

        # Must be a wp-content upload (not theme assets, logos, etc.)
        if 'wp-content/uploads' not in src:
            continue

        # Skip tiny images (likely icons or thumbnails in nav)
        width = img.get('width')
        height = img.get('height')
        if width and height:
            try:
                w, h = int(width), int(height)
                if w < 100 or h < 100:
                    continue
            except ValueError:
                pass

        # Skip navigation images (usually in header/nav/footer)
        parent_classes = set()
        for parent in img.parents:
            if parent.get('class'):
                parent_classes.update(c.lower() for c in parent['class'])
            if parent.get('id'):
                parent_classes.add(parent['id'].lower())

        nav_indicators = {'nav', 'header', 'footer', 'menu', 'sidebar', 'featured-nav'}
        if nav_indicators & parent_classes:
            continue

        if is_valid_photo(src):
            # Score: prefer larger images, images near the person's name
            score = 0
            # Images inside main/article/content areas get a boost
            content_indicators = {'main', 'content', 'entry', 'article', 'person', 'profile', 'bio'}
            if content_indicators & parent_classes:
                score += 10
            # Larger srcset images get a boost
            srcset = img.get('srcset', '')
            if srcset:
                score += 5

            candidates.append((score, src))

    if not candidates:
        return None

    # Sort by score descending, pick best
    candidates.sort(key=lambda x: x[0], reverse=True)
    best_url = candidates[0][1]

    # Make absolute URL if relative
    if best_url.startswith('//'):
        best_url = 'https:' + best_url
    elif best_url.startswith('/'):
        from urllib.parse import urlparse
        parsed = urlparse(page_url)
        best_url = f"{parsed.scheme}://{parsed.netloc}{best_url}"

    return best_url


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

def try_fetch_photo(session, name, slug, subdomains):
    """Try to find a professor's photo. HEAD first, GET only on 200."""
    # Try both /people/ and /faculty/ URL patterns
    patterns = [
        "/people/{slug}/",
        "/faculty/{slug}/",
        "/person/{slug}/",
        "/directory/{slug}/",
    ]

    for subdomain in subdomains:
        for pattern in patterns:
            url = f"https://{subdomain}.northeastern.edu{pattern.format(slug=slug)}"

            try:
                head = session.head(url, timeout=5, allow_redirects=True)

                if head.status_code != 200:
                    continue
                if not any(p.split('/')[1] in head.url for p in patterns):
                    continue

                resp = session.get(url, timeout=10, allow_redirects=True)
                if resp.status_code != 200:
                    continue

                photo_url = extract_photo_from_html(resp.text, resp.url)
                if photo_url:
                    return photo_url, resp.url

            except Exception:
                continue

    return None, None

def load_professors(data_dir):
    """Load unique professor names + departments from CSVs."""
    profs = {}  # name_key → {name, department}

    # From RMP
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

    # From TRACE
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

def get_subdomains_for_prof(department):
    """Get ONLY the professor's college subdomain — no fallbacks."""
    college = DEPT_TO_COLLEGE.get(department)
    if college and college in COLLEGE_SUBDOMAINS:
        return COLLEGE_SUBDOMAINS[college]
    # Unknown department — try the 3 biggest colleges only
    return ["www.khoury", "cos", "cssh"]

def scrape_photos(profs, workers=15, limit=None):
    """Scrape headshot URLs for all professors.

    Args:
        profs: List of {name, department} dicts.
        workers: Parallel threads.
        limit: Max professors to scrape.

    Returns:
        List of {name, image_url, source_page} dicts.
    """
    if limit:
        profs = profs[:limit]

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    })

    results = []
    found = 0

    pbar = tqdm(total=len(profs), desc="Scraping photos", unit=" prof")

    def scrape_one(prof):
        name = prof['name']
        dept = prof['department']
        slug = name_to_slug(name)
        subdomains = get_subdomains_for_prof(dept)
        photo_url, source_page = try_fetch_photo(session, name, slug, subdomains)
        return {
            'name': name,
            'image_url': photo_url or '',
            'source_page': source_page or '',
        }

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(scrape_one, p): p for p in profs}

        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
                if result['image_url']:
                    found += 1
            except Exception:
                pass
            pbar.update(1)

    pbar.close()
    print(f"  Found photos for {found}/{len(profs)} professors")
    return results


def save_csv(results, output_path):
    """Save results to CSV."""
    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

    # Only save professors with photos
    with_photos = [r for r in results if r['image_url']]
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['name', 'image_url', 'source_page'])
        writer.writeheader()
        for row in with_photos:
            writer.writerow(row)

    print(f"  ✓ Saved {len(with_photos)} photo URLs to: {output_path}")


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
        help="Parallel threads (default 15, be gentle on NEU servers)",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max professors to scrape (for testing)",
    )
    parser.add_argument(
        "-o", "--output", type=str, default=None,
        help="Output CSV path",
    )

    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = args.data_dir or os.path.join(script_dir, "output_data")
    output_path = args.output or os.path.join(data_dir, "professor_photos.csv")

    # Load professors
    profs = load_professors(data_dir)
    print(f"  Loaded {len(profs)} unique professors")

    if not profs:
        print("  ✗ No professors found. Check your data directory.")
        return

    # Scrape
    results = scrape_photos(profs, workers=args.workers, limit=args.limit)

    # Save
    save_csv(results, output_path)
    print()


if __name__ == "__main__":
    main()