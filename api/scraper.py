import re
import requests
from bs4 import BeautifulSoup
from functools import lru_cache

_session = requests.Session()
_session.headers.update({"User-Agent": "growtopia-wiki-scraper/1.0"})


def get_item_data(item_name: str, include_subitems: bool = False) -> dict:
    try:
        item_found = search_item(item_name, allow_partial_match=False)[0]
        item_page = get_raw_html(item_found["Url"])
    except IndexError:
        raise Exception(f"Item '{item_name}' not found")

    result = {}
    if len(item_page.select(".gtw-card")) == 1:
        parse_html_content(item_page, result)
    else:
        for idx, html_content_tabber in enumerate(item_page.select(".wds-tab__content")):
            tabber_result = {}
            parse_html_content(html_content_tabber, tabber_result)
            if idx == 0:
                result = tabber_result
                if not include_subitems:
                    break
            else:
                result.setdefault("SubItems", []).append(tabber_result)

    result["Url"] = item_found["Url"]
    return result


def search_item(item_name: str, allow_partial_match: bool = True, show_url: bool = True) -> list[dict]:
    try:
        if allow_partial_match:
            params = {"action": "query", "srlimit": 20, "list": "search", "srsearch": item_name, "format": "json"}
            url = "https://growtopia.fandom.com/api.php"
            data = _session.get(url, params=params, timeout=10).json()
            raw_items = data["query"]["search"]
        else:
            params = {"query": item_name}
            url = "https://growtopia.fandom.com/api/v1/SearchSuggestions/List"
            data = _session.get(url, params=params, timeout=10).json()
            raw_items = data["items"]

        skip_keywords = ["category:", "update", "disambiguation", "week", "mods/"]
        items = []
        for item in raw_items:
            title = item["title"]
            title_lower = title.lower()
            if allow_partial_match:
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


@lru_cache(maxsize=128)
def get_raw_html(url: str) -> BeautifulSoup:
    try:
        response = _session.get(url, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as error:
        raise Exception(f"Wiki page fetch failed: {error}")


def parse_html_content(html_content: BeautifulSoup, result: dict):
    result["Title"] = get_item_title(html_content)
    result["Rarity"] = get_item_rarity(html_content)
    result["Description"] = get_item_description(html_content)
    result["Properties"] = get_item_properties(html_content)
    result["Type"] = get_simple_item_data(html_content, 1, " - ")
    result["Chi"] = get_simple_item_data(html_content, 2)
    result["TextureType"] = get_simple_item_data(html_content, 3)
    result["CollisionType"] = get_simple_item_data(html_content, 4)
    result["Hardness"] = get_item_hardness(html_content)
    result["SeedColor"] = get_simple_item_data(html_content, 6, " ")
    result["GrowTime"] = get_simple_item_data(html_content, 7)
    result["DefaultGemsDrop"] = get_simple_item_data(html_content, 8)
    result["Sprite"] = get_item_sprite(html_content)
    result["Recipe"] = get_item_recipes(html_content)


def get_item_title(html_content: BeautifulSoup) -> str:
    tag = html_content.select_one("span.mw-headline")
    if not tag:
        return "Unknown"
    return tag.get_text(strip=True, separator="\n").split("\n")[0].replace("\xa0", " ")


def get_item_rarity(html_content: BeautifulSoup):
    rarity_tag = html_content.select_one('small:-soup-contains("Rarity")')
    if not rarity_tag:
        return "None"
    match = re.search(r"\d+", rarity_tag.text)
    return int(match.group()) if match else "None"


def get_item_description(html_content: BeautifulSoup) -> str:
    tag = html_content.select_one("div.card-text")
    return tag.text if tag else ""


def get_item_properties(html_content: BeautifulSoup) -> list:
    tag = html_content.select_one('b:-soup-contains("Properties") + div.card-text')
    if not tag:
        return []
    for br in tag.find_all("br"):
        br.replace_with("--split--")
    return [p for p in tag.text.split("--split--") if p.strip()]


def get_simple_item_data(html_content: BeautifulSoup, order: int, separator: str = ""):
    tag = html_content.select_one(f"tbody > tr:nth-of-type({order}) > td")
    if not tag:
        return [] if separator else ""
    text = tag.get_text(strip=True, separator=" ")
    return text.split(separator) if separator else text


def get_item_hardness(html_content: BeautifulSoup) -> dict:
    text = get_simple_item_data(html_content, 5)
    digits = list(map(int, re.findall(r"\d+", text)))
    return {
        "Fist": digits[0] if len(digits) > 0 else None,
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
        recipe.select_one("th").get_text(strip=True)
        for recipe in html_content.select("div.recipebox")
        if recipe.select_one("th")
    ]
