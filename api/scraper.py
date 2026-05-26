import re
import requests
from bs4 import BeautifulSoup
from functools import lru_cache

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://growtopia.fandom.com/",
})

WIKI_BASE = "https://growtopia.fandom.com"
API_BASE  = f"{WIKI_BASE}/api.php"


# ── Public entry points ────────────────────────────────────────────────────────

def get_item_data(item_name: str, include_subitems: bool = False) -> dict:
    results = search_item(item_name)
    if not results:
        raise Exception(f"Item '{item_name}' not found")

    item_found = results[0]
    title = item_found["Title"]

    html = fetch_page_html_via_api(title)
    soup = BeautifulSoup(html, "html.parser")

    result = {}
    tabs  = soup.select(".wds-tab__content")
    cards = soup.select(".gtw-card")

    if not tabs or len(cards) == 1:
        parse_html_content(soup, result)
    else:
        for idx, tab in enumerate(tabs):
            tab_result = {}
            parse_html_content(tab, tab_result)
            if idx == 0:
                result = tab_result
                if not include_subitems:
                    break
            else:
                result.setdefault("SubItems", []).append(tab_result)

    result["Url"] = item_found["Url"]
    return result


def search_item(item_name: str, show_url: bool = True) -> list[dict]:
    """Search via MediaWiki api.php — reliable from any IP."""
    # Step 1: exact title match
    try:
        resp = _session.get(API_BASE, params={
            "action": "query",
            "titles": item_name,
            "format": "json",
            "redirects": 1,
        }, timeout=15)
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
        exact = [p for p in pages.values() if p.get("pageid", -1) != -1]
        if exact:
            title = exact[0]["title"]
            return [_make_entry(title, show_url)]
    except Exception:
        pass

    # Step 2: fulltext search
    try:
        resp = _session.get(API_BASE, params={
            "action": "query",
            "list": "search",
            "srsearch": item_name,
            "srlimit": 20,
            "srnamespace": 0,
            "format": "json",
        }, timeout=15)
        resp.raise_for_status()
        raw = resp.json().get("query", {}).get("search", [])

        skip = ["category:", "update", "disambiguation", "week", "mods/"]
        items = []
        for item in raw:
            t = item["title"]
            tl = t.lower()
            if item_name.lower() not in tl:
                continue
            if any(kw in tl for kw in skip):
                continue
            items.append(_make_entry(t, show_url))
        return items

    except requests.RequestException as e:
        raise Exception(f"Wiki search failed: {e}")


# ── Internal helpers ───────────────────────────────────────────────────────────

def _make_entry(title: str, show_url: bool) -> dict:
    entry = {"Title": title}
    if show_url:
        entry["Url"] = f"{WIKI_BASE}/wiki/{title.replace(' ', '_')}"
    return entry


def fetch_page_html_via_api(title: str) -> str:
    """
    Fetch page HTML through MediaWiki parse API.
    This endpoint returns JSON (not raw HTML), so Fandom cannot block it
    the same way they block direct wiki page requests from datacenter IPs.
    """
    try:
        resp = _session.get(API_BASE, params={
            "action": "parse",
            "page": title,
            "prop": "text",
            "format": "json",
            "disableeditsection": 1,
            "disabletoc": 1,
        }, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            raise Exception(f"MediaWiki API error: {data['error'].get('info', 'unknown')}")

        html = data["parse"]["text"]["*"]
        return html

    except requests.RequestException as e:
        raise Exception(f"Wiki page fetch failed: {e}")
    except (KeyError, ValueError) as e:
        raise Exception(f"Wiki page parse failed: {e}")


# ── Parsers ────────────────────────────────────────────────────────────────────

def parse_html_content(soup: BeautifulSoup, result: dict):
    result["Title"]           = get_item_title(soup)
    result["Rarity"]          = get_item_rarity(soup)
    result["Description"]     = get_item_description(soup)
    result["Properties"]      = get_item_properties(soup)
    result["Type"]            = get_simple_item_data(soup, 1, " - ")
    result["Chi"]             = get_simple_item_data(soup, 2)
    result["TextureType"]     = get_simple_item_data(soup, 3)
    result["CollisionType"]   = get_simple_item_data(soup, 4)
    result["Hardness"]        = get_item_hardness(soup)
    result["SeedColor"]       = get_simple_item_data(soup, 6, " ")
    result["GrowTime"]        = get_simple_item_data(soup, 7)
    result["DefaultGemsDrop"] = get_simple_item_data(soup, 8)
    result["Sprite"]          = get_item_sprite(soup)
    result["Recipe"]          = get_item_recipes(soup)


def get_item_title(soup: BeautifulSoup) -> str:
    tag = soup.select_one("span.mw-headline")
    if not tag:
        return "Unknown"
    return tag.get_text(strip=True, separator="\n").split("\n")[0].replace("\xa0", " ")


def get_item_rarity(soup: BeautifulSoup):
    tag = soup.select_one('small:-soup-contains("Rarity")')
    if not tag:
        return "None"
    m = re.search(r"\d+", tag.text)
    return int(m.group()) if m else "None"


def get_item_description(soup: BeautifulSoup) -> str:
    tag = soup.select_one("div.card-text")
    return tag.text.strip() if tag else ""


def get_item_properties(soup: BeautifulSoup) -> list:
    tag = soup.select_one('b:-soup-contains("Properties") + div.card-text')
    if not tag:
        return []
    for br in tag.find_all("br"):
        br.replace_with("--split--")
    return [p.strip() for p in tag.text.split("--split--") if p.strip()]


def get_simple_item_data(soup: BeautifulSoup, order: int, separator: str = ""):
    tag = soup.select_one(f"tbody > tr:nth-of-type({order}) > td")
    if not tag:
        return [] if separator else ""
    text = tag.get_text(strip=True, separator=" ")
    return text.split(separator) if separator else text


def get_item_hardness(soup: BeautifulSoup) -> dict:
    text = str(get_simple_item_data(soup, 5))
    digits = list(map(int, re.findall(r"\d+", text)))
    return {
        "Fist":    digits[0] if len(digits) > 0 else None,
        "Pickaxe": digits[1] if len(digits) > 1 else None,
        "Restore": digits[2] if len(digits) > 2 else None,
    }


def get_item_sprite(soup: BeautifulSoup) -> dict:
    def safe_src(sel):
        t = soup.select_one(sel)
        return t.get("src") if t else None
    return {
        "Item": safe_src("div.card-header img"),
        "Tree": safe_src('th:-soup-contains("Grow Time") + td img'),
        "Seed": safe_src("td.seedColor img"),
    }


def get_item_recipes(soup: BeautifulSoup) -> list:
    return [
        r.select_one("th").get_text(strip=True)
        for r in soup.select("div.recipebox")
        if r.select_one("th")
    ]
