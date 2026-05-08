import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
import os
from email.utils import parsedate_to_datetime

URL = "https://www.home-assistant.io/blog/"
OUTPUT = "docs/home-assistant-blog.xml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def scrape_posts():
    resp = requests.get(URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    posts = []
    seen = set()

    # Each blog post is an <article> or a block with an <h1>/<h2> containing a link
    for heading in soup.select("h1 a[href*='/blog/'], h2 a[href*='/blog/']"):
        href = heading.get("href", "")
        title = heading.get_text(strip=True)
        if not title or not href:
            continue

        full_url = href if href.startswith("http") else "https://www.home-assistant.io" + href
        if full_url in seen:
            continue
        seen.add(full_url)

        # Walk up to find the post container
        container = heading.find_parent(["article", "section", "div"])

        # Date: look for <time> or a date-like element
        pub_date = datetime.now(timezone.utc)
        time_el = container.find("time") if container else None
        if time_el:
            dt_str = time_el.get("datetime") or time_el.get_text(strip=True)
            try:
                pub_date = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except Exception:
                pass

        # Author
        author = ""
        author_el = container.find("a", href=lambda h: h and "github.com" in h) if container else None
        if author_el:
            author = author_el.get_text(strip=True)

        # Image: look for <img> in the container
        image_url = ""
        img_el = container.find("img") if container else None
        if img_el:
            src = img_el.get("src", "")
            if src and not src.endswith(".svg"):
                image_url = src if src.startswith("http") else "https://www.home-assistant.io" + src

        # Description: the paragraph after the heading
        description = ""
        if container:
            for p in container.find_all("p"):
                text = p.get_text(strip=True)
                if text and len(text) > 30:
                    description = text
                    break

        # Categories
        categories = []
        if container:
            for cat_el in container.select("a[href*='/blog/categories/']"):
                categories.append(cat_el.get_text(strip=True))

        posts.append({
            "title": title,
            "url": full_url,
            "pub_date": pub_date,
            "author": author,
            "image_url": image_url,
            "description": description,
            "categories": categories,
        })

    return posts


def build_feed(posts):
    os.makedirs("docs", exist_ok=True)

    fg = FeedGenerator()
    fg.id(URL)
    fg.title("Home Assistant Blog")
    fg.link(href=URL, rel="alternate")
    fg.description("Official blog of the Home Assistant project")
    fg.language("en")
    fg.lastBuildDate(datetime.now(timezone.utc))

    for post in posts[:30]:
        fe = fg.add_entry()
        fe.id(post["url"])
        fe.title(post["title"])
        fe.link(href=post["url"])
        fe.published(post["pub_date"])
        fe.updated(post["pub_date"])
        if post["author"]:
            fe.author({"name": post["author"]})
        for cat in post["categories"]:
            fe.category({"term": cat})

        content_html = ""
        if post["image_url"]:
            content_html += f'<img src="{post["image_url"]}" alt="{post["title"]}" style="max-width:100%;" /><br/>'
            fe.enclosure(post["image_url"], 0, "image/webp")
        if post["description"]:
            content_html += f"<p>{post['description']}</p>"
        if content_html:
            fe.content(content_html, type="html")

    fg.rss_file(OUTPUT, pretty=True)
    print(f"✅ Feed written to {OUTPUT} with {len(posts)} items")


if __name__ == "__main__":
    print(f"Scraping {URL} ...")
    posts = scrape_posts()
    print(f"Found {len(posts)} posts")
    if not posts:
        print("⚠️  No posts found — site structure may have changed. Feed not updated.")
    else:
        build_feed(posts)
