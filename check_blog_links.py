import csv
import random
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DEFAULT_BASE_SITE = "https://www.tusitiazo.com"
TIMEOUT = 10

REPORTS_DIR = Path("Reports")
AUDIT_DIR = Path("Auditoria")
TEST_DIR = Path("Test")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def build_site_config(base_site):
    parsed = urlparse(base_site)
    if not parsed.netloc:
        raise ValueError("La URL base no es válida.")
    normalized_base = f"{parsed.scheme}://{parsed.netloc}"
    return {
        "base_site": normalized_base,
        "blog_index_url": urljoin(normalized_base, "/post/"),
        "sitemap_urls": [
            urljoin(normalized_base, "/blog-posts-sitemap.xml"),
            urljoin(normalized_base, "/sitemap.xml"),
        ],
        "internal_domain": parsed.netloc,
    }


def normalize_base_site(raw_value):
    raw_value = raw_value.strip()
    if not raw_value:
        return DEFAULT_BASE_SITE
    parsed = urlparse(raw_value)
    if not parsed.scheme:
        raw_value = f"https://{raw_value}"
        parsed = urlparse(raw_value)
    if not parsed.netloc:
        raise ValueError("La URL base no es válida.")
    return raw_value


def fetch_sitemap_posts(site_config):
    posts = set()

    for sitemap_url in site_config["sitemap_urls"]:
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


def fetch_sitemap_urls(site_config):
    urls = set()
    for sitemap_url in site_config["sitemap_urls"]:
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
                if url and "/post/" not in url:
                    urls.add(url)
        if urls:
            break
    return sorted(urls)


def fetch_posts_from_index(site_config):
    response = requests.get(
        site_config["blog_index_url"], headers=HEADERS, timeout=TIMEOUT
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    return sorted(
        {
            urljoin(site_config["base_site"], link["href"])
            for link in soup.select("a[href]")
            if "/post/" in link["href"]
        }
    )


def get_post_urls(site_config):
    posts = fetch_sitemap_posts(site_config)
    if posts:
        return posts
    return fetch_posts_from_index(site_config)


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


def classify_link(href, internal_domain):
    parsed = urlparse(href)
    if not parsed.netloc:
        return "internal"
    if parsed.netloc.endswith(internal_domain):
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


def fetch_page_response(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        return response
    except requests.RequestException:
        return None


def extract_links(content, post_url, internal_domain):
    if content is None:
        return []

    rows = []
    for link in content.find_all("a", href=True):
        href = link.get("href", "").strip()
        if not href:
            continue
        full_url = urljoin(post_url, href)
        link_type = classify_link(full_url, internal_domain)
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


def build_reports(post_urls, internal_domain):
    link_rows = []
    total_posts = len(post_urls)
    for index, post_url in enumerate(post_urls, start=1):
        print(f"Procesando post {index}/{total_posts}: {post_url}")
        post_title, _, content = extract_post_context(post_url)
        rows = extract_links(content, post_url, internal_domain)
        for row in rows:
            row["post_title"] = post_title
            row["post_url"] = post_url
            link_rows.append(row)

    return link_rows


def extract_page_audit(page_url, internal_domain):
    response = fetch_page_response(page_url)
    if response is None:
        return {
            "page_url": page_url,
            "status": "ERROR",
            "title": "",
            "meta_description": "",
            "h1": "",
            "h2": "",
            "h3": "",
            "paragraphs": "",
            "image_alts": "",
            "image_filenames": "",
            "internal_urls": "",
        }
    status = str(response.status_code)
    soup = BeautifulSoup(response.text, "lxml")
    title_tag = soup.select_one("title")
    title_text = title_tag.get_text(strip=True) if title_tag else ""
    meta_desc = soup.select_one('meta[name="description"]')
    meta_description = meta_desc.get("content", "").strip() if meta_desc else ""

    def join_text(selector):
        texts = [tag.get_text(separator=" ", strip=True) for tag in soup.select(selector)]
        normalized = [" ".join(text.split()) for text in texts if text.strip()]
        return " | ".join(normalized)

    h1_text = join_text("h1")
    h2_text = join_text("h2")
    h3_text = join_text("h3")
    paragraphs_text = join_text("p")

    image_alts = []
    image_filenames = []
    for img in soup.select("img"):
        alt_text = (img.get("alt") or "").strip()
        if alt_text:
            image_alts.append(alt_text)
        src = (img.get("src") or "").strip()
        if src:
            parsed = urlparse(src)
            filename = Path(parsed.path).name
            if filename:
                image_filenames.append(filename)
    image_alts_text = " | ".join(image_alts)
    image_filenames_text = " | ".join(image_filenames)

    internal_urls = []
    for link in soup.select("a[href]"):
        href = (link.get("href") or "").strip()
        if not href:
            continue
        full_url = urljoin(page_url, href)
        if classify_link(full_url, internal_domain) == "internal":
            internal_urls.append(full_url)
    internal_urls_text = " | ".join(sorted(set(internal_urls)))

    return {
        "page_url": page_url,
        "status": status,
        "title": title_text,
        "meta_description": meta_description,
        "h1": h1_text,
        "h2": h2_text,
        "h3": h3_text,
        "paragraphs": paragraphs_text,
        "image_alts": image_alts_text,
        "image_filenames": image_filenames_text,
        "internal_urls": internal_urls_text,
    }


def build_audit_report(page_urls, internal_domain):
    rows = []
    total_pages = len(page_urls)
    for index, page_url in enumerate(page_urls, start=1):
        print(f"Auditando pagina {index}/{total_pages}: {page_url}")
        rows.append(extract_page_audit(page_url, internal_domain))
    return rows


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


def write_audit_report(rows, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "page_url",
                "status",
                "title",
                "meta_description",
                "h1",
                "h2",
                "h3",
                "paragraphs",
                "image_alts",
                "image_filenames",
                "internal_urls",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row["page_url"],
                    row["status"],
                    row["title"],
                    row["meta_description"],
                    row["h1"],
                    row["h2"],
                    row["h3"],
                    row["paragraphs"],
                    row["image_alts"],
                    row["image_filenames"],
                    row["internal_urls"],
                ]
            )


def next_versioned_path(directory, prefix, timestamp):
    directory.mkdir(parents=True, exist_ok=True)
    base_name = f"{prefix}_{timestamp}"
    candidate = directory / f"{base_name}.csv"
    if not candidate.exists():
        return candidate
    counter = 1
    while True:
        candidate = directory / f"{base_name}_{counter:02d}.csv"
        if not candidate.exists():
            return candidate
        counter += 1


def run_test_mode(site_config):
    post_urls = get_post_urls(site_config)
    if not post_urls:
        raise RuntimeError("No se encontraron posts para analizar.")
    selected_post = random.choice(post_urls)
    link_rows = build_reports([selected_post], site_config["internal_domain"])
    enlaces_path = TEST_DIR / "enlaces_blog_test.csv"
    seo_path = TEST_DIR / "seo_posts_test.csv"
    write_enlaces_report(link_rows, enlaces_path)
    write_seo_report(link_rows, seo_path)
    print(f"Reporte generado: {enlaces_path}")
    print(f"Reporte generado: {seo_path}")


def run_full_mode(site_config):
    post_urls = get_post_urls(site_config)
    if not post_urls:
        raise RuntimeError("No se encontraron posts para analizar.")
    link_rows = build_reports(post_urls, site_config["internal_domain"])
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    enlaces_path = next_versioned_path(REPORTS_DIR, "enlaces_blog", timestamp)
    seo_path = next_versioned_path(REPORTS_DIR, "seo_posts", timestamp)
    write_enlaces_report(link_rows, enlaces_path)
    write_seo_report(link_rows, seo_path)
    print(f"Reporte generado: {enlaces_path}")
    print(f"Reporte generado: {seo_path}")


def run_audit_mode(site_config):
    page_urls = fetch_sitemap_urls(site_config)
    if not page_urls:
        raise RuntimeError("No se encontraron URLs para auditar en el sitemap.")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    site_name = urlparse(site_config["base_site"]).netloc.replace(".", "_") or "sitio"
    audit_path = next_versioned_path(
        AUDIT_DIR, f"auditoria_{site_name}", timestamp
    )
    rows = build_audit_report(page_urls, site_config["internal_domain"])
    write_audit_report(rows, audit_path)
    print(f"Reporte generado: {audit_path}")


def main():
    if len(sys.argv) != 2:
        print("Uso: python check_blog_links.py [test|full|audit]")
        raise SystemExit(1)
    try:
        base_site = normalize_base_site(
            input(
                f"Ingrese la URL base a analizar (Enter para {DEFAULT_BASE_SITE}): "
            )
        )
        site_config = build_site_config(base_site)
    except ValueError as exc:
        print(str(exc))
        raise SystemExit(1) from exc
    mode = sys.argv[1].lower()
    if mode == "test":
        run_test_mode(site_config)
        return
    if mode == "full":
        run_full_mode(site_config)
        return
    if mode == "audit":
        run_audit_mode(site_config)
        return
    print("Modo inválido. Usa: python check_blog_links.py [test|full|audit]")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
