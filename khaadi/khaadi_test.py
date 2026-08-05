import os
import re
import json
import time
import random
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://pk.khaadi.com"
GRID_URL = (
    f"{BASE_URL}/on/demandware.store/Sites-Khaadi_PK-Site/en_PK/"
    "Search-UpdateGrid?cgid=root&start=0&sz=24"
)
OUTPUT_NAME = "khaadi_products.json"

FABRIC_KEYWORDS = [
    "Khaddar", "Lawn", "Cotton", "Chiffon", "Karandi", "Cambric", "Linen",
    "Organza", "Silk", "Net", "Velvet", "Dobby", "Slub", "Swiss", "Voile",
    "Jacquard", "Tissue", "Georgette", "Wool", "Viscose", "Marina", "Mareena",
    "Textured Cotton", "Cotton Dobby", "Viscose Silk", "Heavy Textured Cotton",
]


def clean_price(text):
    if not text:
        return None
    digits = re.sub(r"[^\d.]", "", text.replace(",", ""))
    return digits or None


def extract_fabric_from_alt(alt: str):
    parts = [p.strip() for p in (alt or "").split("|")]
    if len(parts) >= 3:
        candidate = parts[1].strip()
        for fabric in FABRIC_KEYWORDS:
            if re.search(rf"\b{re.escape(fabric)}\b", candidate, re.I):
                return candidate.upper()
        if candidate and re.fullmatch(r"[A-Za-z][A-Za-z \-]{1,40}", candidate):
            if not re.search(r"\b(ML|OZ|Piece|Set)\b", candidate, re.I):
                return candidate.upper()

    blob = alt or ""
    for fabric in FABRIC_KEYWORDS:
        if re.search(rf"\b{re.escape(fabric)}\b", blob, re.I):
            return fabric.upper()
    return None


def extract_color_from_pid(pid):
    if not pid:
        return None
    match = re.search(r"_([A-Za-z][A-Za-z0-9\-]*)$", pid)
    if match:
        value = match.group(1).replace("-", " ").upper()
        if value.lower() not in {"html", "jpg", "png"}:
            return value
    return None


def detect_pieces(title: str, alt: str):
    blob = f"{title or ''} {alt or ''}"
    m = re.search(r"\b([123])\s*[- ]?\s*piece\b", blob, re.I)
    if m:
        return f"{m.group(1)} Piece"
    m = re.search(r"\b([123])\s*[- ]?\s*pc\b", blob, re.I)
    if m:
        return f"{m.group(1)} Piece"
    return None


def detect_category(title: str, alt: str, category_id: str):
    blob = f"{title or ''} {alt or ''} {category_id or ''}".lower()
    if any(x in blob for x in ["fabric", "unstitched", "ready to stitch"]):
        return "Unstitched"
    if any(x in blob for x in ["ready-to-wear", "ready to wear", "stitched", "tailored", "kurta", "pants"]):
        if "fabric" not in blob:
            return "Stitched"
    if "fabric" in (title or "").lower():
        return "Unstitched"
    return None


def detect_department(title: str, alt: str, category_id: str):
    blob = f"{title or ''} {alt or ''} {category_id or ''}".lower()

    if any(x in blob for x in ["fragrance", "eau de parfum", "perfume"]):
        return "Fragrances"
    if any(x in blob for x in ["home", "towel", "bedsheet", "cushion", "duvet"]):
        return "Home"
    if any(x in blob for x in ["bag", "handbag"]):
        return "Bags"
    if any(x in blob for x in ["man", "men", "001003", "mens"]):
        return "Men"
    if any(x in blob for x in ["kid", "children", "boys", "girls"]):
        return "Kids"
    if any(x in blob for x in ["woman", "women", "ready-to-wear", "fabric", "kurta", "001002"]):
        return "Women"
    return "Women"


def detect_subcategory(title: str, alt: str):
    blob = f"{title or ''} {alt or ''}".lower()
    parts = [p.strip() for p in (alt or "").split("|")]
    style = parts[0].strip() if parts else None

    rules = [
        ("Fabrics 3 Piece", [r"\bfabrics?\s*3\s*piece\b", r"\b3\s*piece\b.*fabric"]),
        ("Kurta", [r"\bkurta\b"]),
        ("Pants", [r"\bpants\b", r"\btrouser\b"]),
        ("Fragrance", [r"\beau de parfum\b", r"\bperfume\b"]),
        ("Embroidered", [r"\bembroidered\b"]),
        ("Printed", [r"\bprinted\b"]),
    ]
    for label, patterns in rules:
        if any(re.search(p, blob, re.I) for p in patterns):
            return label
    if style and re.fullmatch(r"[A-Za-z][A-Za-z \-]{1,40}", style):
        if not re.search(r"\b(ML|OZ|PKR)\b", style, re.I):
            return style.title()
    return None


def detect_product_type(title: str, alt: str):
    if title:
        return title
    parts = [p.strip() for p in (alt or "").split("|")]
    if len(parts) >= 3:
        return parts[2]
    return None


def parse_tile(tile):
    html = tile.decode_contents()
    pid_match = re.search(r"id:\s*'([^']+)'", html)
    pid = pid_match.group(1) if pid_match else None

    cat_match = re.search(r"categoryId\s*=\s*'([^']+)'", html)
    category_id = cat_match.group(1) if cat_match else ""

    link = tile.select_one("a[href*='.html']")
    href = link.get("href") if link else None
    if not pid and href:
        pid = href.split("/")[-1].split(".html")[0]

    product_url = None
    if href:
        clean = href.split("?")[0]
        product_url = BASE_URL + clean if clean.startswith("/") else clean

    title_el = tile.select_one("h2.pdp-link-heading, h2")
    title = title_el.get_text(strip=True) if title_el else None

    # Sale price preferred; list/strike = compare_at_price
    sales_el = tile.select_one(".sales .value, .sales span, .sales")
    list_el = tile.select_one(".price .strike-through .value, .strike-through, .price-standard, .list .value")
    price_el = tile.select_one("span.cc-price")

    price = clean_price(sales_el.get_text(strip=True) if sales_el else None)
    compare_at_price = clean_price(list_el.get_text(strip=True) if list_el else None)
    if not price:
        price = clean_price(price_el.get_text(strip=True) if price_el else None)
    # If only one price shown in cc-price and no sales, compare may equal price — drop it
    if compare_at_price and price and compare_at_price == price:
        compare_at_price = None

    img = tile.select_one("div.image-container img, img.tile-image, img")
    image = img.get("src") if img else None
    alt = (img.get("alt") if img else "") or ""

    if image and image.startswith("//"):
        image = "https:" + image
    elif image and image.startswith("/"):
        image = BASE_URL + image

    # availability: listed products are generally available; mark false if sold-out label
    labels = " ".join(
        el.get_text(" ", strip=True).lower()
        for el in tile.select(".product-labels, .product-flag, .badge")
    )
    available = not any(x in labels for x in ["sold out", "out of stock", "unavailable"])

    return {
        "title": title,
        "color": extract_color_from_pid(pid),
        "fabric": extract_fabric_from_alt(alt),
        "price": price,
        "compare_at_price": compare_at_price,
        "image": image,
        "product_url": product_url,
        "department": detect_department(title or "", alt, category_id),
        "subcategory": detect_subcategory(title or "", alt),
        "category": detect_category(title or "", alt, category_id),
        "product_type": detect_product_type(title or "", alt),
        "pieces": detect_pieces(title or "", alt),
        "size": None,
        "sku": pid,
        "available": available,
        "_pid": pid,
    }


def scrape_khaadi():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    url = GRID_URL
    scraped_data = []
    seen = set()
    page = 0

    while url:
        page += 1
        print(f"Fetching page {page}: {url}", flush=True)

        try:
            response = requests.get(url, headers=headers, timeout=40)
        except Exception as e:
            print(f"Request error: {e}", flush=True)
            break

        if response.status_code != 200:
            print(f"Failed with status {response.status_code}", flush=True)
            break

        soup = BeautifulSoup(response.text, "html.parser")
        tiles = soup.select("div.tile")
        if not tiles:
            print("No more products found.", flush=True)
            break

        new_count = 0
        for tile in tiles:
            item = parse_tile(tile)
            if not item:
                continue
            pid = item.pop("_pid", None)
            if not pid or pid in seen:
                continue
            seen.add(pid)
            scraped_data.append(item)
            new_count += 1

        print(
            f"Page {page}: batch={len(tiles)} new={new_count} total={len(scraped_data)}",
            flush=True,
        )

        placeholder = soup.select_one("div.infinite-scroll-placeholder[data-grid-url]")
        next_url = placeholder.get("data-grid-url") if placeholder else None
        if not next_url:
            print("Pagination end detected.", flush=True)
            break
        if next_url.startswith("/"):
            next_url = BASE_URL + next_url
        if next_url == url:
            break
        url = next_url
        time.sleep(random.uniform(0.25, 0.6))

    return {"data": scraped_data}


def save_json(payload):
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), OUTPUT_NAME),
        os.path.join(r"D:\My work\khaadi", OUTPUT_NAME),
        os.path.join(os.path.expanduser("~"), OUTPUT_NAME),
        os.path.join(os.environ.get("TEMP", "."), OUTPUT_NAME),
    ]
    for output_file in candidates:
        folder = os.path.dirname(output_file)
        if folder and not os.path.isdir(folder):
            continue
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4, ensure_ascii=False)
            print(f"Data successfully saved to {output_file}", flush=True)
            return output_file
        except Exception as err:
            print(f"Could not save to {output_file}: {err}", flush=True)
    return None


if __name__ == "__main__":
    print("Starting Khaadi FULL catalog scrape ...", flush=True)
    print("Source: https://pk.khaadi.com (cgid=root)", flush=True)
    result = scrape_khaadi()
    print(f"Successfully scraped {len(result['data'])} products.", flush=True)
    save_json(result)
