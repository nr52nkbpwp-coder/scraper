import re
import requests
from bs4 import BeautifulSoup
from functools import lru_cache

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; growtopia-wiki-scraper/1.0)",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
})


def get_item_data(item_name: str, include_subitems: bool = False) -> dict:
    try:
        item_found = search_item(item_name)[0]
        item_page = get_raw_html(item_found["Url"])
    except IndexError:
        raise Exception(f"Item '{item_name}' not found")

    result = {}
    tabs = item_page.select(".wds-tab__content")
    cards = item_page.select(".gtw-card")

    if not tabs or len(cards) == 1:
        parse_html_content(item_page, result)
    else:
        for idx, tab in enumerate(tabs):
            tabber_result = {}
            parse_html_content(tab, tabber_result)
            if idx == 0:
                result = tabber_result
                if not include_subitems:
                    break
            else:
                result.setdefault("SubItems", []).append(tabber_result)

    result["Url"] = item_found["Url"]
    return result


def search_item(item_name: str, show_url: bool = True) -> list[dict]:
    """
    Search using MediaWiki api.php — most reliable endpoint, works from any IP.
    Tries exact title lookup first, falls back to fulltext search.
    """
    base = "https://growtopia.fandom.com/api.php"

    # 1. Try exact title first (fastest, most accurate)
    try:
        resp = _session.get(base, params={
            "action": "query",
            "titles": item_name,
            "format": "json",
            "redirects": 1,
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        # -1 means page not found
        exact = [p for p in pages.values() if p.get("pageid", -1) != -1]
        if exact:
            title = exact[0]["title"]
            entry = {"Title": title}
            if show_url:
                entry["Url"] = f"https://growtopia.fandom.com/wiki/{title.replace(' ', '_')}"
            return [entry]
    except Exception:
        pass  # fall through to fulltext search

    # 2. Fulltext search
    try:
        resp = _session.get(base, params={
            "action": "query",
            "list": "search",
            "srsearch": item_name,
            "srlimit": 20,
            "srnamespace": 0,
            "format": "json",
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        raw_items = data.get("query", {}).get("search", [])
        skip_keywords = ["category:", "update", "disambiguation", "week", "mods/"]
        items = []
        for item in raw_items:
            title = item["title"]
            title_lower = title.lower()
            if item_name.lower() not in title_lower:
                continue
            if any(kw in title_lower for kw in skip_keywords):
                continue
            entry = {"Title": title}
            if show_url:
                entry["Url"] = f"https://growtopia.fandom.com/wiki/{title.replace(' ', '_')}"
            items.append(entry)

        return items

    except requests.RequestException as error:
        raise Exception(f"Wiki search fetch failed: {error}")
    except (KeyError, ValueError) as error:
        raise Exception(f"Wiki search parse failed: {error}")


@lru_cache(maxsize=128)
def get_raw_html(url: str) -> BeautifulSoup:
    try:
        response = _session.get(url, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as error:
        raise Exception(f"Wiki page fetch failed: {error}")


def parse_html_content(html_content: BeautifulSoup, result: dict):
    result["Title"]          = get_item_title(html_content)
    result["Rarity"]         = get_item_rarity(html_content)
    result["Description"]    = get_item_description(html_content)
    result["Properties"]     = get_item_properties(html_content)
    result["Type"]           = get_simple_item_data(html_content, 1, " - ")
    result["Chi"]            = get_simple_item_data(html_content, 2)
    result["TextureType"]    = get_simple_item_data(html_content, 3)
    result["CollisionType"]  = get_simple_item_data(html_content, 4)
    result["Hardness"]       = get_item_hardness(html_content)
    result["SeedColor"]      = get_simple_item_data(html_content, 6, " ")
    result["GrowTime"]       = get_simple_item_data(html_content, 7)
    result["DefaultGemsDrop"]= get_simple_item_data(html_content, 8)
    result["Sprite"]         = get_item_sprite(html_content)
    result["Recipe"]         = get_item_recipes(html_content)


def get_item_title(html_content: BeautifulSoup) -> str:
    tag = html_content.select_one("span.mw-headline")
    if not tag:
        return "Unknown"
    return tag.get_text(strip=True, separator="\n").split("\n")[0].replace("\xa0", " ")


def get_item_rarity(html_content: BeautifulSoup):
    tag = html_content.select_one('small:-soup-contains("Rarity")')
    if not tag:
        return "None"
    match = re.search(r"\d+", tag.text)
    return int(match.group()) if match else "None"


def get_item_description(html_content: BeautifulSoup) -> str:
    tag = html_content.select_one("div.card-text")
    return tag.text.strip() if tag else ""


def get_item_properties(html_content: BeautifulSoup) -> list:
    tag = html_content.select_one('b:-soup-contains("Properties") + div.card-text')
    if not tag:
        return []
    for br in tag.find_all("br"):
        br.replace_with("--split--")
    return [p.strip() for p in tag.text.split("--split--") if p.strip()]


def get_simple_item_data(html_content: BeautifulSoup, order: int, separator: str = ""):
    tag = html_content.select_one(f"tbody > tr:nth-of-type({order}) > td")
    if not tag:
        return [] if separator else ""
    text = tag.get_text(strip=True, separator=" ")
    return text.split(separator) if separator else text


def get_item_hardness(html_content: BeautifulSoup) -> dict:
    text = get_simple_item_data(html_content, 5)
    digits = list(map(int, re.findall(r"\d+", str(text))))
    return {
        "Fist":    digits[0] if len(digits) > 0 else None,
        "Pickaxe": digits[1] if len(digits) > 1 else None,
        "Restore": digits[2] if len(digits) > 2 else None,
    }


def get_item_sprite(html_content: BeautifulSoup) -> dict:
    def safe_src(selector):
        tag = html_content.select_one(selector)
        return tag.get("src") if tag else None
    return {
        "Item": safe_src("div.card-header img"),
        "Tree": safe_src('th:-soup-contains("Grow Time") + td img'),
        "Seed": safe_src("td.seedColor img"),
    }


def get_item_recipes(html_content: BeautifulSoup) -> list:
    return [
        r.select_one("th").get_text(strip=True)
        for r in html_content.select("div.recipebox")
        if r.select_one("th")
    ]
