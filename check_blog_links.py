import csv
import random
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE_SITE = "https://www.tusitiazo.com"
BLOG_INDEX_URL = "https://www.tusitiazo.com/post/"
SITEMAP_URLS = [
    "https://www.tusitiazo.com/blog-posts-sitemap.xml",
    "https://www.tusitiazo.com/sitemap.xml",
]
TIMEOUT = 10

REPORTS_DIR = Path("Reports")
TEST_DIR = Path("Test")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def fetch_sitemap_posts():
    posts = set()

    for sitemap_url in SITEMAP_URLS:
        try:
            response = requests.get(sitemap_url, headers=HEADERS, timeout=TIMEOUT)
            response.raise_for_status()
        except requests.RequestException:
            continue

        soup = BeautifulSoup(response.text, "xml")
        nested = [loc.get_text(strip=True) for loc in soup.select("sitemap loc")]
        sitemap_sources = nested if nested else [sitemap_url]
        for source in sitemap_sources:
            try:
                source_response = requests.get(
                    source, headers=HEADERS, timeout=TIMEOUT
                )
                source_response.raise_for_status()
            except requests.RequestException:
                continue
            source_soup = BeautifulSoup(source_response.text, "xml")
            for loc_tag in source_soup.select("url loc"):
                url = loc_tag.get_text(strip=True)
                if "/post/" in url:
                    posts.add(url)

        if posts:
            break

    return sorted(posts)


def fetch_posts_from_index():
    response = requests.get(BLOG_INDEX_URL, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    return sorted(
        {
            urljoin(BASE_SITE, link["href"])
            for link in soup.select("a[href]")
            if "/post/" in link["href"]
        }
    )


def get_post_urls():
    posts = fetch_sitemap_posts()
    if posts:
        return posts
    return fetch_posts_from_index()


def extract_post_context(post_url):
    response = requests.get(post_url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")

    title_tag = soup.select_one("title")
    if title_tag and title_tag.get_text(strip=True):
        post_title = title_tag.get_text(strip=True)
    else:
        h1_tag = soup.select_one('h1[data-hook="post-title"]')
        post_title = h1_tag.get_text(strip=True) if h1_tag else post_url

    content = soup.select_one('section[data-hook="post-description"]')
    if content is None:
        content = soup.select_one('div[data-hook="post-content"]')
    if content is None:
        content = soup.select_one("article")

    return post_title, soup, content


def normalize_rel(rel_value):
    if rel_value is None:
        return []
    if isinstance(rel_value, list):
        rel_tokens = rel_value
    else:
        rel_tokens = str(rel_value).split()
    return [token.strip().lower() for token in rel_tokens if token.strip()]


def classify_link(href):
    parsed = urlparse(href)
    if not parsed.netloc:
        return "internal"
    if parsed.netloc.endswith("tusitiazo.com"):
        return "internal"
    return "external"


def fetch_link_status(url):
    try:
        response = requests.head(
            url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True
        )
        if response.status_code == 405:
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        return str(response.status_code)
    except requests.RequestException:
        try:
            response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            return str(response.status_code)
        except requests.RequestException:
            return "ERROR"


def extract_links(content, post_url):
    if content is None:
        return []

    rows = []
    for link in content.find_all("a", href=True):
        href = link.get("href", "").strip()
        if not href:
            continue
        full_url = urljoin(post_url, href)
        link_type = classify_link(full_url)
        status = fetch_link_status(full_url)
        rel_tokens = normalize_rel(link.get("rel"))
        referrerpolicy = (link.get("referrerpolicy") or "").strip().lower()
        nofollow = "ON" if "nofollow" in rel_tokens else "OFF"
        noreferrer = (
            "ON"
            if "noreferrer" in rel_tokens or referrerpolicy == "no-referrer"
            else "OFF"
        )
        anchor_text = link.get_text(separator=" ", strip=True)
        anchor_text = " ".join(anchor_text.split())
        if not anchor_text:
            anchor_text = "[NO_TEXT]"
        target_blank = (link.get("target") or "").strip().lower() == "_blank"
        sponsored = "sponsored" in rel_tokens
        rows.append(
            {
                "link_type": link_type,
                "anchor_text": anchor_text,
                "link_url": full_url,
                "status": status,
                "nofollow": nofollow,
                "noreferrer": noreferrer,
                "open_in_new_tab": target_blank,
                "sponsored": sponsored,
            }
        )
    return rows


def build_reports(post_urls):
    link_rows = []
    seo_rows = []
    for post_url in post_urls:
        post_title, _, content = extract_post_context(post_url)
        rows = extract_links(content, post_url)
        for row in rows:
            row["post_title"] = post_title
            row["post_url"] = post_url
            link_rows.append(row)

        nofollow = "ON" if any(row["nofollow"] == "ON" for row in rows) else "OFF"
        noreferrer = (
            "ON" if any(row["noreferrer"] == "ON" for row in rows) else "OFF"
        )
        open_in_new_tab = (
            "ON" if any(row["open_in_new_tab"] for row in rows) else "OFF"
        )
        sponsored = "ON" if any(row["sponsored"] for row in rows) else "OFF"
        seo_rows.append(
            {
                "post_title": post_title,
                "post_url": post_url,
                "nofollow": nofollow,
                "noreferrer": noreferrer,
                "open_in_new_tab": open_in_new_tab,
                "sponsored": sponsored,
            }
        )

    return link_rows, seo_rows


def write_enlaces_report(rows, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Titulo de entrada(post)",
                "url del post",
                "anchor_text",
                "url del link dentro del contenido del post",
                "estatus",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["post_title"],
                    row["post_url"],
                    row["anchor_text"],
                    row["link_url"],
                    row["status"],
                ]
            )


def write_seo_report(rows, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "post_title",
                "post_url",
                "nofollow",
                "noreferrer",
                "open_in_new_tab",
                "sponsored",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["post_title"],
                    row["post_url"],
                    row["nofollow"],
                    row["noreferrer"],
                    row["open_in_new_tab"],
                    row["sponsored"],
                ]
            )


def write_seo_test_report(rows, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "post_title",
                "post_url",
                "link_type",
                "anchor_text",
                "link_url",
                "nofollow",
                "noreferrer",
                "open_in_new_tab",
                "sponsored",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["post_title"],
                    row["post_url"],
                    row["link_type"],
                    row["anchor_text"],
                    row["link_url"],
                    row["nofollow"],
                    row["noreferrer"],
                    "ON" if row["open_in_new_tab"] else "OFF",
                    "ON" if row["sponsored"] else "OFF",
                ]
            )


def next_versioned_path(directory, prefix, date_stamp):
    directory.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(rf"{re.escape(prefix)}_{date_stamp}_v(\\d+)\\.csv")
    max_version = 0
    for path in directory.iterdir():
        match = pattern.fullmatch(path.name)
        if match:
            max_version = max(max_version, int(match.group(1)))
    return directory / f"{prefix}_{date_stamp}_v{max_version + 1}.csv"


def run_test_mode():
    post_urls = get_post_urls()
    if not post_urls:
        raise RuntimeError("No se encontraron posts para analizar.")
    selected_post = random.choice(post_urls)
    link_rows, _ = build_reports([selected_post])
    enlaces_path = TEST_DIR / "enlaces_blog_test.csv"
    seo_path = TEST_DIR / "seo_posts_test.csv"
    write_enlaces_report(link_rows, enlaces_path)
    write_seo_test_report(link_rows, seo_path)
    print(f"Reporte generado: {enlaces_path}")
    print(f"Reporte generado: {seo_path}")


def run_full_mode():
    post_urls = get_post_urls()
    if not post_urls:
        raise RuntimeError("No se encontraron posts para analizar.")
    link_rows, seo_rows = build_reports(post_urls)
    date_stamp = datetime.now().strftime("%Y%m%d")
    enlaces_path = next_versioned_path(REPORTS_DIR, "enlaces_blog", date_stamp)
    seo_path = next_versioned_path(REPORTS_DIR, "seo_posts", date_stamp)
    write_enlaces_report(link_rows, enlaces_path)
    write_seo_report(seo_rows, seo_path)
    print(f"Reporte generado: {enlaces_path}")
    print(f"Reporte generado: {seo_path}")


def main():
    if len(sys.argv) != 2:
        print("Uso: python check_blog_links.py [test|full]")
        raise SystemExit(1)
    mode = sys.argv[1].lower()
    if mode == "test":
        run_test_mode()
        return
    if mode == "full":
        run_full_mode()
        return
    print("Modo inválido. Usa: python check_blog_links.py [test|full]")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
