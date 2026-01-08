import csv
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
        rel_tokens = normalize_rel(link.get("rel"))
        referrerpolicy = (link.get("referrerpolicy") or "").strip().lower()
        nofollow = "ON" if "nofollow" in rel_tokens else "OFF"
        noreferrer = (
            "ON"
            if "noreferrer" in rel_tokens or referrerpolicy == "no-referrer"
            else "OFF"
        )
        anchor_text = link.get_text(strip=True)
        rows.append(
            {
                "link_type": link_type,
                "anchor_text": anchor_text,
                "link_url": full_url,
                "nofollow": nofollow,
                "noreferrer": noreferrer,
            }
        )
    return rows


def main():
    post_urls = get_post_urls()
    all_rows = []
    for post_url in post_urls:
        post_title, _, content = extract_post_context(post_url)
        rows = extract_links(content, post_url)
        for row in rows:
            row["post_title"] = post_title
            row["post_url"] = post_url
            all_rows.append(row)

    with open("reporte_seo_posts.csv", "w", newline="", encoding="utf-8") as handle:
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
            ]
        )
        for row in all_rows:
            writer.writerow(
                [
                    row["post_title"],
                    row["post_url"],
                    row["link_type"],
                    row["anchor_text"],
                    row["link_url"],
                    row["nofollow"],
                    row["noreferrer"],
                ]
            )

    print("Reporte generado: reporte_seo_posts.csv")


if __name__ == "__main__":
    main()
