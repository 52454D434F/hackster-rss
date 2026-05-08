"""
Scraper for Hackster.io channel project pages (JS-rendered).
Uses Hackster's internal API (api.hackster.io) which the browser calls
to populate the project listing pages.
"""
import requests
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone
import os
import sys

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.hackster.io/",
    "Origin": "https://www.hackster.io",
    "X-Requested-With": "XMLHttpRequest",
}

FEEDS = [
    {
        "channel": "iot",
        "title": "Hackster.io — IoT Projects",
        "description": "Latest Internet of Things projects from Hackster.io",
        "output": "docs/hackster-iot-projects.xml",
        "url": "https://www.hackster.io/iot/projects?sort=published",
    },
    {
        "channel": "home-automation",
        "title": "Hackster.io — Home Automation Projects",
        "description": "Latest Home Automation projects from Hackster.io",
        "output": "docs/hackster-home-automation-projects.xml",
        "url": "https://www.hackster.io/home-automation/projects?sort=published",
    },
]


def fetch_projects_via_api(channel, per_page=20):
    """
    Call Hackster's internal API to get projects for a channel.
    Tries multiple known endpoint patterns.
    """
    endpoints = [
        f"https://api.hackster.io/v2/channels/{channel}/projects?sort=published&per_page={per_page}",
        f"https://www.hackster.io/{channel}/projects.json?sort=published&per_page={per_page}",
        f"https://api.hackster.io/v2/projects?channel={channel}&sort=published&per_page={per_page}",
    ]

    for endpoint in endpoints:
        try:
            r = requests.get(endpoint, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                data = r.json()
                print(f"  ✅ API hit: {endpoint}")
                return data
            else:
                print(f"  ❌ {r.status_code} — {endpoint}")
        except Exception as e:
            print(f"  ❌ Error — {endpoint}: {e}")

    return None


def parse_projects(data):
    """Parse projects from API response — handles multiple response shapes."""
    projects = []

    # Common response shapes from Hackster's API
    if isinstance(data, list):
        raw = data
    elif isinstance(data, dict):
        raw = (
            data.get("projects")
            or data.get("data")
            or data.get("items")
            or data.get("results")
            or []
        )

    for item in raw:
        # Normalise field names across API versions
        title = item.get("name") or item.get("title") or ""
        slug = item.get("slug") or item.get("url") or ""
        description = item.get("description_preview") or item.get("description") or item.get("summary") or ""
        author = ""
        owner = item.get("owner") or item.get("user") or item.get("author") or {}
        if isinstance(owner, dict):
            author = owner.get("name") or owner.get("username") or owner.get("login") or ""

        # Build URL
        if slug.startswith("http"):
            url = slug
        elif slug:
            url = f"https://www.hackster.io/{slug}"
        else:
            continue

        # Image
        image_url = ""
        cover = item.get("cover_image_url") or item.get("image") or item.get("cover") or {}
        if isinstance(cover, str):
            image_url = cover
        elif isinstance(cover, dict):
            image_url = cover.get("url") or cover.get("src") or ""

        if not image_url:
            # Try nested image fields
            for key in ("image_url", "thumbnail", "photo", "preview_image"):
                val = item.get(key)
                if val and isinstance(val, str):
                    image_url = val
                    break
                elif val and isinstance(val, dict):
                    image_url = val.get("url") or val.get("src") or ""
                    if image_url:
                        break

        if title:
            projects.append({
                "title": title,
                "url": url,
                "description": description,
                "author": author,
                "image_url": image_url,
            })

    return projects


def build_feed(feed_cfg, projects):
    os.makedirs("docs", exist_ok=True)

    fg = FeedGenerator()
    fg.id(feed_cfg["url"])
    fg.title(feed_cfg["title"])
    fg.link(href=feed_cfg["url"], rel="alternate")
    fg.description(feed_cfg["description"])
    fg.language("en")
    fg.lastBuildDate(datetime.now(timezone.utc))

    for p in projects[:30]:
        fe = fg.add_entry()
        fe.id(p["url"])
        fe.title(p["title"])
        fe.link(href=p["url"])
        fe.published(datetime.now(timezone.utc))
        if p["author"]:
            fe.author({"name": p["author"]})

        content_html = ""
        if p["image_url"]:
            content_html += f'<img src="{p["image_url"]}" alt="{p["title"]}" style="max-width:100%;" /><br/>'
            fe.enclosure(p["image_url"], 0, "image/jpeg")
        if p["description"]:
            content_html += f"<p>{p['description']}</p>"
        if content_html:
            fe.content(content_html, type="html")

    fg.rss_file(feed_cfg["output"], pretty=True)
    print(f"  ✅ Written {feed_cfg['output']} ({len(projects)} items)")


if __name__ == "__main__":
    all_ok = True

    for feed_cfg in FEEDS:
        print(f"\nFetching: {feed_cfg['title']}")
        data = fetch_projects_via_api(feed_cfg["channel"])

        if data is None:
            print(f"  ⚠️  All API endpoints failed for {feed_cfg['channel']} — feed not updated.")
            all_ok = False
            continue

        projects = parse_projects(data)
        print(f"  Parsed {len(projects)} projects")

        if not projects:
            print(f"  ⚠️  No projects parsed — API response shape may have changed.")
            all_ok = False
            continue

        build_feed(feed_cfg, projects)

    sys.exit(0 if all_ok else 1)
