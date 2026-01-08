import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from tqdm import tqdm
import csv
import time

BASE_SITE = "https://www.tusitiazo.com"
TARGET_POSTS = [
    "https://www.tusitiazo.com/post/google-renueva-el-logo-de-search-console-en-2025"
]
STOP_URL_PREFIX = "https://www.tusitiazo.com/blog/categories/"
EXCLUDED_DOMAINS = {"www.facebook.com", "x.com", "www.linkedin.com"}
TIMEOUT = 10

headers = {
    "User-Agent": "LinkChecker/1.0 (+SEO audit)"
}

def extract_links(post_url):
    r = requests.get(post_url, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else post_url

    found = set()

    for tag in soup.find_all(["a", "img"]):
        attr = "href" if tag.name == "a" else "src"
        link = tag.get(attr)
        if link:
            full = urljoin(post_url, link)
            if full.startswith(STOP_URL_PREFIX):
                break
            parsed = urlparse(full)
            if parsed.netloc in EXCLUDED_DOMAINS:
                continue
            found.add(full)

    return title, found

def check_link(url):
    try:
        r = requests.head(url, allow_redirects=True, timeout=TIMEOUT)
        return r.status_code
    except requests.RequestException:
        return "ERROR"

def main():
    posts = TARGET_POSTS
    results = []

    for post in tqdm(posts, desc="Revisando entradas"):
        title, links = extract_links(post)
        for link in links:
            status = check_link(link)
            results.append([title, post, link, status])
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
        writer.writerows(results)

    print("\nReporte generado: reporte_enlaces_blog.csv")

if __name__ == "__main__":
    main()
