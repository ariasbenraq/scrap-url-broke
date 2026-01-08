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
    "User-Agent": "LinkChecker/1.0 (+SEO audit)"
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

def extract_links_from_soup(soup, post_url):
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

def extract_seo_data(soup, post_url):
    title_tag = soup.select_one('h1[data-hook="post-title"]')
    h1_title = title_tag.get_text(strip=True) if title_tag else ""

    page_title_tag = soup.find("title")
    page_title = page_title_tag.get_text(strip=True) if page_title_tag else ""

    meta_description_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = (
        meta_description_tag.get("content", "").strip()
        if meta_description_tag
        else ""
    )
    meta_description_length = len(meta_description)

    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    canonical_url = canonical_tag.get("href", "").strip() if canonical_tag else ""

    post_title = h1_title or page_title or post_url

    return [
        post_title,
        post_url,
        page_title,
        h1_title,
        meta_description,
        meta_description_length,
        canonical_url,
    ]

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
            seo_results.append([post, post, "", "", "", 0, ""])
            continue

        seo_results.append(extract_seo_data(soup, post))
        links = extract_links_from_soup(soup, post)
        post_title = seo_results[-1][0]
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
                "Titulo de entrada(post)",
                "url del post",
                "title tag",
                "h1",
                "meta description",
                "longitud meta description",
                "canonical",
            ]
        )
        writer.writerows(seo_results)

    print("Reporte generado: reporte_seo_posts.csv")

if __name__ == "__main__":
    main()
