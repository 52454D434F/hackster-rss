import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
import os

URL = "https://join1440.com/c/science-technology"
OUTPUT = "docs/1440-science-technology.xml"

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

    articles = []
    seen = set()

    # Each finding is an <a> that links to an external source
    # They contain an <h4> title and a description paragraph
    for a in soup.select("a[href^='http']:not([href*='join1440.com'])"):
        title_el = a.select_one("h4, h3, h2")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title or len(title) < 10:
            continue

        source_url = a.get("href", "")
        if source_url in seen:
            continue
        seen.add(source_url)

        # Description: first <p> inside the same container
        desc_el = a.select_one("p")
        description = desc_el.get_text(strip=True) if desc_el else ""

        # Topic tag: look for a topic link nearby
        parent = a.find_parent()
        topic = ""
        if parent:
            topic_el = parent.select_one("a[href*='/t/']")
            if topic_el:
                topic = topic_el.get_text(strip=True)

        articles.append({
            "title": title,
            "url": source_url,
            "description": description,
            "topic": topic,
        })

    return articles


def build_feed(articles):
    os.makedirs("docs", exist_ok=True)

    fg = FeedGenerator()
    fg.id(URL)
    fg.title("1440 — Science & Technology")
    fg.link(href=URL, rel="alternate")
    fg.description("Science & Technology findings curated by 1440")
    fg.language("en")
    fg.lastBuildDate(datetime.now(timezone.utc))

    for art in articles[:30]:
        fe = fg.add_entry()
        fe.id(art["url"])
        fe.title(f"[{art['topic']}] {art['title']}" if art["topic"] else art["title"])
        fe.link(href=art["url"])
        fe.published(datetime.now(timezone.utc))
        if art["description"]:
            fe.description(art["description"])

    fg.rss_file(OUTPUT, pretty=True)
    print(f"✅ Feed written to {OUTPUT} with {len(articles)} items")


if __name__ == "__main__":
    print(f"Scraping {URL} ...")
    articles = scrape_articles()
    print(f"Found {len(articles)} articles")
    if not articles:
        print("⚠️  No articles found — site structure may have changed. Feed not updated.")
    else:
        build_feed(articles)
