import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
import os
import re

URL = "https://www.hackster.io/news/"
OUTPUT = "docs/feed.xml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
}


def get_og_meta(article_url):
    """Fetch og:image and og:description from an individual article page."""
    try:
        r = requests.get(article_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        image = ""
        description = ""
        og_image = soup.find("meta", property="og:image")
        if og_image:
            image = og_image.get("content", "")
        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            description = og_desc.get("content", "")
        return image, description
    except Exception as e:
        print(f"  Could not fetch {article_url}: {e}")
        return "", ""


def scrape_articles():
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    seen = set()
    articles = []

    for a in soup.select("a[href*='/news/']"):
        href = a.get("href", "")
        title = a.get_text(strip=True)

        if not title or len(title) < 15:
            continue
        if "?" in href:
            continue

        full_url = href if href.startswith("http") else "https://www.hackster.io" + href

        if full_url in seen:
            continue
        seen.add(full_url)

        parent = a.find_parent(class_=re.compile(r"article|card|post|item|story", re.I))
        author = ""
        if parent:
            author_el = parent.select_one("a[href*='/'][class*='author'], span[class*='author'], a[rel='author']")
            if author_el:
                author = author_el.get_text(strip=True)

        articles.append({"title": title, "url": full_url, "author": author})

    return articles


def build_feed(articles):
    os.makedirs("docs", exist_ok=True)

    fg = FeedGenerator()
    fg.id("https://www.hackster.io/news/")
    fg.title("Hackster.io News")
    fg.link(href="https://www.hackster.io/news/", rel="alternate")
    fg.description("Latest news from Hackster.io — scraped RSS feed")
    fg.language("en")
    fg.lastBuildDate(datetime.now(timezone.utc))

    for art in articles[:30]:
        print(f"  Fetching meta for: {art['title'][:60]}")
        image_url, description = get_og_meta(art["url"])

        fe = fg.add_entry()
        fe.id(art["url"])
        fe.title(art["title"])
        fe.link(href=art["url"])
        fe.published(datetime.now(timezone.utc))
        if art["author"]:
            fe.author({"name": art["author"]})

        # Build HTML content block with image + description
        content_html = ""
        if image_url:
            content_html += f'<img src="{image_url}" alt="{art["title"]}" style="max-width:100%;" /><br/>'
            fe.enclosure(image_url, 0, "image/jpeg")
        if description:
            content_html += f"<p>{description}</p>"
        if content_html:
            fe.content(content_html, type="html")

    fg.rss_file(OUTPUT, pretty=True)
    print(f"Feed written to {OUTPUT} with {len(articles)} items")


if __name__ == "__main__":
    print(f"Scraping {URL} ...")
    articles = scrape_articles()
    print(f"Found {len(articles)} articles")
    if not articles:
        print("No articles found — Hackster may be blocking. Feed not updated.")
    else:
        build_feed(articles)
