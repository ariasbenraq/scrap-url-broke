import csv
import time
from collections import deque
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

BASE_SITE = "https://www.tusitiazo.com"
BLOG_URL = "https://www.tusitiazo.com/blog"
TIMEOUT = 10

headers = {
    "User-Agent": "LinkChecker/1.0 (+SEO audit)"
}

def get_blog_posts():
    posts = set()
    sitemap_posts = get_blog_posts_from_sitemap()
    if sitemap_posts:
        posts.update(sitemap_posts)

    if posts:
        return sorted(posts)

    return sorted(get_blog_posts_from_listing())


def get_blog_posts_from_listing():
    posts = set()
    visited = set()
    queue = deque([BLOG_URL])

    while queue:
        page_url = queue.popleft()
        if page_url in visited:
            continue
        visited.add(page_url)

        r = requests.get(page_url, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        for a in soup.select("a[href]"):
            href = a.get("href")
            if not href:
                continue
            full = urljoin(BASE_SITE, href)
            parsed = urlparse(full)
            if parsed.netloc and parsed.netloc != urlparse(BASE_SITE).netloc:
                continue

            path = parsed.path.rstrip("/")
            if path.startswith("/blog") and path != "/blog":
                if path.startswith("/blog/page") or "page" in parsed.query:
                    if full not in visited:
                        queue.append(full)
                else:
                    posts.add(full)

        next_link = soup.select_one("a[rel='next'], link[rel='next']")
        if next_link:
            next_href = next_link.get("href")
            if next_href:
                next_full = urljoin(BASE_SITE, next_href)
                if next_full not in visited:
                    queue.append(next_full)

    return posts


def get_blog_posts_from_sitemap():
    sitemap_candidates = [
        urljoin(BASE_SITE, "sitemap.xml"),
        urljoin(BASE_SITE, "sitemap_index.xml"),
        urljoin(BASE_SITE, "blog/sitemap.xml"),
        urljoin(BASE_SITE, "blog/sitemap_index.xml"),
    ]
    posts = set()

    for sitemap_url in sitemap_candidates:
        try:
            r = requests.get(sitemap_url, headers=headers, timeout=TIMEOUT)
            if r.status_code != 200:
                continue
        except requests.RequestException:
            continue

        soup = BeautifulSoup(r.text, "xml")
        sitemap_locs = [loc.get_text(strip=True) for loc in soup.select("sitemap > loc")]
        if sitemap_locs:
            for loc_url in sitemap_locs:
                if "/blog" not in loc_url:
                    continue
                posts.update(_extract_blog_posts_from_sitemap(loc_url))
            continue

        posts.update(_extract_blog_posts_from_sitemap(sitemap_url))

    return posts


def _extract_blog_posts_from_sitemap(sitemap_url):
    posts = set()
    try:
        r = requests.get(sitemap_url, headers=headers, timeout=TIMEOUT)
        if r.status_code != 200:
            return posts
    except requests.RequestException:
        return posts

    soup = BeautifulSoup(r.text, "xml")
    for loc in soup.select("url > loc"):
        url = loc.get_text(strip=True)
        if "/blog" not in url:
            continue
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        if path.startswith("/blog") and path != "/blog":
            if path.startswith("/blog/page") or "page" in parsed.query:
                continue
            posts.add(url)
    return posts


def get_content_root(soup):
    selectors = [
        "article",
        "main",
        ".post-content",
        ".entry-content",
        ".blog-content",
        ".post-body",
        ".content",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            return node
    return soup.body or soup


def get_post_title(soup, content_root):
    if content_root:
        h1 = content_root.find("h1")
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)
    article = soup.find("article")
    if article:
        h1 = article.find("h1")
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)
    title = soup.find("title")
    return title.get_text(strip=True) if title else "Sin título"

def extract_links(post_url):
    r = requests.get(post_url, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    content_root = get_content_root(soup)
    found = set()

    for tag in content_root.find_all(["a", "img"]):
        attrs = ["href"] if tag.name == "a" else ["src", "data-src", "data-lazy-src", "data-original"]
        for attr in attrs:
            link = tag.get(attr)
            if not link:
                continue
            if link.startswith(("mailto:", "tel:", "javascript:")):
                continue
            full = urljoin(post_url, link)
            found.add(full)

    return found, get_post_title(soup, content_root)

def check_link(url):
    try:
        r = requests.head(url, allow_redirects=True, timeout=TIMEOUT)
        if r.status_code in {403, 405}:
            r = requests.get(url, allow_redirects=True, timeout=TIMEOUT, stream=True)
        return r.status_code
    except requests.RequestException:
        return "ERROR"


def is_broken(status):
    return status == "ERROR" or (isinstance(status, int) and status >= 400)

def main():
    posts = get_blog_posts()
    results = []
    total_links_checked = 0

    if not posts:
        print("No se encontraron entradas del blog. Verifica BLOG_URL o el sitemap.")
        return

    for post in tqdm(posts, desc="Revisando entradas"):
        links, title = extract_links(post)
        for link in links:
            status = check_link(link)
            total_links_checked += 1
            if is_broken(status):
                results.append([title, post, link, status])
            time.sleep(0.2)

    with open("reporte_enlaces_blog.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Título de la entrada", "URL de la entrada", "Enlace roto", "Estado HTTP"])
        writer.writerows(results)

    print("\nReporte generado: reporte_enlaces_blog.csv")
    print(f"Entradas encontradas: {len(posts)}")
    print(f"Enlaces revisados: {total_links_checked}")
    print(f"Enlaces rotos: {len(results)}")

if __name__ == "__main__":
    main()
