import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from tqdm import tqdm
import csv
import time

BASE_SITE = "https://www.tusitiazo.com"
BLOG_URL = "https://www.tusitiazo.com/blog"
SITEMAP_URLS = [
    "https://www.tusitiazo.com/blog-posts-sitemap.xml",
    "https://www.tusitiazo.com/sitemap.xml",
]
STOP_URL_PREFIX = "https://www.tusitiazo.com/blog/categories/"
EXCLUDED_DOMAINS = {"www.facebook.com", "x.com", "www.linkedin.com"}
TIMEOUT = 10

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

def get_posts_from_sitemap():
    posts = set()

    for sitemap_url in SITEMAP_URLS:
        try:
            r = requests.get(sitemap_url, headers=headers, timeout=TIMEOUT)
            r.raise_for_status()
        except requests.RequestException:
            continue

        soup = BeautifulSoup(r.text, "xml")
        sitemap_locs = [loc.get_text(strip=True) for loc in soup.select("sitemap loc")]
        if sitemap_locs:
            for loc in sitemap_locs:
                try:
                    sub = requests.get(loc, headers=headers, timeout=TIMEOUT)
                    sub.raise_for_status()
                except requests.RequestException:
                    continue
                sub_soup = BeautifulSoup(sub.text, "xml")
                for loc_tag in sub_soup.select("url loc"):
                    url = loc_tag.get_text(strip=True)
                    if "/post/" in url:
                        posts.add(url)
        else:
            for loc_tag in soup.select("url loc"):
                url = loc_tag.get_text(strip=True)
                if "/post/" in url:
                    posts.add(url)

        if posts:
            break

    return sorted(posts)

def scrape_posts_from_blog():
    posts = set()
    page = 1
    while True:
        page_url = BLOG_URL if page == 1 else f"{BLOG_URL}?page={page}"
        try:
            r = requests.get(page_url, headers=headers, timeout=TIMEOUT)
            r.raise_for_status()
        except requests.RequestException:
            break
        soup = BeautifulSoup(r.text, "lxml")
        page_posts = {
            urljoin(BASE_SITE, a.get("href"))
            for a in soup.select("a[href]")
            if a.get("href") and "/post/" in a.get("href")
        }
        new_posts = page_posts - posts
        if not new_posts:
            break
        posts.update(new_posts)
        page += 1

    return sorted(posts)

def get_blog_posts():
    posts = get_posts_from_sitemap()
    if posts:
        return posts

    return scrape_posts_from_blog()

def fetch_post_soup(post_url):
    r = requests.get(post_url, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")

def extract_link_targets(soup, post_url):
    content = soup.select_one('section[data-hook="post-description"]')
    if content is None:
        return set()

    found = set()

    for tag in content.find_all(["a", "img"]):
        attr = "href" if tag.name == "a" else "src"
        link = tag.get(attr)
        if not link:
            continue
        full = urljoin(post_url, link)
        if full.startswith(STOP_URL_PREFIX):
            break
        parsed = urlparse(full)
        if parsed.netloc in EXCLUDED_DOMAINS:
            continue
        found.add(full)

    return found

def extract_post_context(soup, post_url):
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

    return post_title, content

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

def extract_seo_links(content, post_url):
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

def check_link(url):
    try:
        r = requests.head(url, allow_redirects=True, timeout=TIMEOUT)
        return r.status_code
    except requests.RequestException:
        return "ERROR"

def main():
    posts = get_blog_posts()
    link_results = []
    seo_results = []

    for post in tqdm(posts, desc="Revisando entradas"):
        try:
            soup = fetch_post_soup(post)
        except requests.RequestException:
            continue

        post_title, content = extract_post_context(soup, post)
        seo_links = extract_seo_links(content, post)
        for row in seo_links:
            row["post_title"] = post_title
            row["post_url"] = post
            seo_results.append(row)

        links = extract_link_targets(soup, post)
        for link in links:
            status = check_link(link)
            link_results.append([post_title, post, link, status])
            time.sleep(0.2)

    with open("reporte_enlaces_blog.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Titulo de entrada(post)",
                "url del post",
                "url del link dentro del contenido del post",
                "estatus",
            ]
        )
        writer.writerows(link_results)

    print("\nReporte generado: reporte_enlaces_blog.csv")

    with open("reporte_seo_posts.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
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
        for row in seo_results:
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
