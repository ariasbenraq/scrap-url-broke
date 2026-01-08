import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from tqdm import tqdm
import csv
import time

BASE_SITE = "https://www.tusitiazo.com"
BLOG_URL = "https://www.tusitiazo.com/blog"
TIMEOUT = 10

headers = {
    "User-Agent": "LinkChecker/1.0 (+SEO audit)"
}

def get_blog_posts():
    r = requests.get(BLOG_URL, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    links = set()
    for a in soup.select("a[href]"):
        href = a.get("href")
        if href and "/blog/" in href:
            links.add(urljoin(BASE_SITE, href))

    return sorted(links)

def extract_links(post_url):
    r = requests.get(post_url, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    found = set()

    for tag in soup.find_all(["a", "img"]):
        attr = "href" if tag.name == "a" else "src"
        link = tag.get(attr)
        if link:
            full = urljoin(post_url, link)
            found.add(full)

    return found

def check_link(url):
    try:
        r = requests.head(url, allow_redirects=True, timeout=TIMEOUT)
        return r.status_code
    except requests.RequestException:
        return "ERROR"

def main():
    posts = get_blog_posts()
    results = []

    for post in tqdm(posts, desc="Revisando entradas"):
        links = extract_links(post)
        for link in links:
            status = check_link(link)
            results.append([post, link, status])
            time.sleep(0.2)

    with open("reporte_enlaces_blog.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Entrada del blog", "Enlace", "Estado HTTP"])
        writer.writerows(results)

    print("\nReporte generado: reporte_enlaces_blog.csv")

if __name__ == "__main__":
    main()
