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


def scrape_articles():
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    seen = set()
    articles = []

    for a in soup.select("a[href*='/news/']"):
        href = a.get("href", "")
        title = a.get_text(strip=True)

        # Filter out nav links and short strings
        if not title or len(title) < 15:
            continue
        # Skip topic filter links like /news?topic=...
        if "?" in href:
            continue

        full_url = href if href.startswith("http") else "https://www.hackster.io" + href

        # Deduplicate
        if full_url in seen:
            continue
        seen.add(full_url)

        # Try to find an author near this link
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
        fe = fg.add_entry()
        fe.id(art["url"])
        fe.title(art["title"])
        fe.link(href=art["url"])
        fe.published(datetime.now(timezone.utc))
        if art["author"]:
            fe.author({"name": art["author"]})

    fg.rss_file(OUTPUT, pretty=True)
    print(f"✅ Feed written to {OUTPUT} with {len(articles)} items")


if __name__ == "__main__":
    print(f"Scraping {URL} ...")
    articles = scrape_articles()
    print(f"Found {len(articles)} articles")
    if not articles:
        print("⚠️  No articles found — Hackster may be blocking. Feed not updated.")
    else:
        build_feed(articles)
