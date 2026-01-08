import csv
import re
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import xml.etree.ElementTree as ET

BASE_SITE = "https://www.tusitiazo.com"
BLOG_URL = "https://www.tusitiazo.com/blog"
SITEMAP_URL = "https://www.tusitiazo.com/sitemap.xml"
OUTPUT_CSV = "entradas_blog.csv"
TIMEOUT = 15
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BlogScraper/1.0; +https://www.tusitiazo.com)"
}


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = set()

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.links.add(value)


def fetch_url(url):
    request = Request(url, headers=HEADERS)
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="ignore")
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"No se pudo descargar {url}: {exc}")


def parse_sitemap(xml_text):
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise RuntimeError(f"XML de sitemap inválido: {exc}")

    return [node.text.strip() for node in root.findall(".//{*}loc") if node.text]


def collect_posts_from_sitemaps():
    to_visit = [SITEMAP_URL]
    visited = set()
    post_urls = set()

    while to_visit:
        sitemap_url = to_visit.pop()
        if sitemap_url in visited:
            continue
        visited.add(sitemap_url)

        xml_text = fetch_url(sitemap_url)
        locations = parse_sitemap(xml_text)

        for loc in locations:
            if loc.endswith(".xml") and "/post/" not in loc:
                if loc not in visited:
                    to_visit.append(loc)
                continue
            if "/post/" in loc:
                post_urls.add(loc)

        time.sleep(0.2)

    return sorted(post_urls)


def extract_links_from_html(html_text, base_url):
    parser = LinkParser()
    parser.feed(html_text)

    found = {urljoin(base_url, link) for link in parser.links}

    regex_links = set()
    for match in re.findall(r"https?://[^\"'\s>]+", html_text):
        regex_links.add(match)
    for match in re.findall(r"/post/[^\"'\s>]+", html_text):
        regex_links.add(urljoin(base_url, match))

    return found | regex_links


def is_blog_listing(url):
    if not url.startswith(BLOG_URL):
        return False
    if "/post/" in url:
        return False
    if url == BLOG_URL:
        return True
    return "page=" in url or "/page/" in url


def crawl_blog_listings(max_pages=50):
    to_visit = [BLOG_URL]
    visited = set()
    post_urls = set()

    while to_visit and len(visited) < max_pages:
        page_url = to_visit.pop(0)
        if page_url in visited:
            continue
        visited.add(page_url)

        html_text = fetch_url(page_url)
        links = extract_links_from_html(html_text, page_url)

        for link in links:
            if "/post/" in link:
                post_urls.add(link)
            elif is_blog_listing(link) and link not in visited and link not in to_visit:
                to_visit.append(link)

        time.sleep(0.2)

    return sorted(post_urls)


def build_rows(post_urls):
    rows = []
    for url in post_urls:
        slug = urlparse(url).path.split("/post/")[-1].strip("/")
        rows.append([url, slug])
    return rows


def main():
    try:
        post_urls = collect_posts_from_sitemaps()
    except RuntimeError as exc:
        print(f"Aviso: {exc}")
        post_urls = []

    if not post_urls:
        print("No se encontraron entradas en el sitemap. Buscando en el listado del blog...")
        post_urls = crawl_blog_listings()

    rows = build_rows(post_urls)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["URL", "Slug"])
        writer.writerows(rows)

    print(f"Se generó {OUTPUT_CSV} con {len(rows)} entradas.")


if __name__ == "__main__":
    main()
