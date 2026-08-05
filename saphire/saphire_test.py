import os
import re
import json
import time
import random
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://pk.sapphireonline.pk"
GRID_URL = (
    f"{BASE_URL}/on/demandware.store/Sites-Sapphire-Site/default/"
    "Search-UpdateGrid?cgid=root&start=0&sz=36"
)
OUTPUT_NAME = "saphire_products.json"

FABRIC_KEYWORDS = [
    "Slub Lawn", "Lawn", "Cotton", "Chiffon", "Karandi", "Khaddar", "Cambric",
    "Linen", "Organza", "Silk", "Net", "Velvet", "Dobby", "Swiss", "Voile",
    "Jacquard", "Tissue", "Georgette", "Viscose", "Denim", "Knit",
]

COLOR_WORDS = [
    "Black", "White", "Ivory", "Cream", "Beige", "Brown", "Tan", "Mustard",
    "Yellow", "Gold", "Orange", "Rust", "Red", "Maroon", "Burgundy", "Pink",
    "Fuchsia", "Magenta", "Purple", "Lilac", "Lavender", "Blue", "Navy",
    "Teal", "Turquoise", "Green", "Olive", "Mint", "Grey", "Gray", "Silver",
    "Multi", "Multicolor", "Peach", "Coral", "Wine", "Indigo", "Aqua",
]


def clean_price(text):
    if not text:
        return None
    digits = re.sub(r"[^\d.]", "", text.replace(",", ""))
    return digits or None


def extract_fabric(title: str, alt: str, subtitle: str):
    blob = f"{alt or ''} {title or ''} {subtitle or ''}"
    for fabric in FABRIC_KEYWORDS:
        if re.search(rf"\b{re.escape(fabric)}\b", blob, re.I):
            return fabric.upper()
    return None


def extract_color(alt: str, pid: str):
    blob = alt or ""
    # Prefer explicit color words in alt text
    for color in sorted(COLOR_WORDS, key=len, reverse=True):
        if re.search(rf"\b{re.escape(color)}\b", blob, re.I):
            return color.title() if color.lower() != "multi" else "Multi"

    if pid:
        m = re.search(r"_([A-Za-z]{2,}|\d{3})$", pid)
        if m and not m.group(1).isdigit():
            return m.group(1).replace("-", " ").title()
    return None


def detect_pieces(title: str, alt: str):
    blob = f"{title or ''} {alt or ''}"
    m = re.search(r"\b([1234])\s*[- ]?\s*piece\b", blob, re.I)
    if m:
        return f"{m.group(1)} Piece"
    m = re.search(r"\b([1234])\s*[- ]?\s*pc\b", blob, re.I)
    if m:
        return f"{m.group(1)} Piece"
    return None


def detect_category(title: str, alt: str, subtitle: str, product_url: str):
    blob = f"{title or ''} {alt or ''} {subtitle or ''} {product_url or ''}".lower()
    if any(x in blob for x in ["unstitched", "ready to stitch", "/unstitched"]):
        return "Unstitched"
    if any(
        x in blob
        for x in [
            "ready to wear",
            "ready-to-wear",
            "rtw",
            "stitched",
            "kurta",
            "western",
            "co-ord",
            "dress",
        ]
    ):
        return "Stitched"
    return None


def detect_department(title: str, alt: str, subtitle: str, product_url: str):
    blob = f"{title or ''} {alt or ''} {subtitle or ''} {product_url or ''}".lower()

    if any(x in blob for x in ["fragrance", "perfume", "body mist", "eau de"]):
        return "Fragrances"
    if any(x in blob for x in ["bag", "handbag", "tote"]):
        return "Bags"
    if any(x in blob for x in ["shoe", "footwear", "sandal", "heel"]):
        return "Accessories"
    if any(x in blob for x in ["scarf", "hijab", "dupatta", "shawl", "abaya", "accessories"]):
        if "unstitched" not in blob and "rtw" not in blob and "ready to wear" not in blob:
            return "Accessories"
    if any(x in blob for x in ["kid", "boys", "girls", "children"]):
        return "Kids"
    if re.search(r"\bmen'?s\b", blob) or "/man" in blob or "mens-" in blob:
        return "Men"
    if re.search(r"\bwomen'?s\b", blob) or "woman" in blob or "rtw" in blob or "unstitched" in blob:
        return "Women"
    return "Women"


def detect_subcategory(title: str, alt: str, subtitle: str):
    if subtitle:
        return re.sub(r"\s+", " ", subtitle).strip()

    blob = f"{title or ''} {alt or ''}".lower()
    rules = [
        ("Ready to Wear", [r"\brtw\b", r"\bready to wear\b"]),
        ("Unstitched", [r"\bunstitched\b"]),
        ("Western Wear", [r"\bwestern\b"]),
        ("Fragrance", [r"\bfragrance\b", r"\bperfume\b"]),
        ("Bags", [r"\bbags?\b"]),
        ("Kurtas", [r"\bkurta\b"]),
    ]
    for label, patterns in rules:
        if any(re.search(p, blob, re.I) for p in patterns):
            return label
    return None


def parse_tile(tile):
    html = str(tile)
    product = tile.select_one("div.product[data-pid]")
    pid = product.get("data-pid") if product else None
    if not pid:
        m = re.search(r"id:\s*'([^']+)'", html)
        pid = m.group(1) if m else None

    link = tile.select_one("div.pdp-link a.link") or tile.select_one("a.link[href*='.html']")
    href = link.get("href") if link else None
    title = link.get_text(strip=True) if link else None

    product_url = None
    if href:
        clean = href.split("?")[0]
        product_url = BASE_URL + clean if clean.startswith("/") else clean

    subtitle_el = tile.select_one("div.subtitle")
    subtitle = subtitle_el.get_text(" ", strip=True) if subtitle_el else ""

    sales_el = tile.select_one(".sales .value.cc-price, .sales .cc-price, span.value.cc-price")
    list_el = tile.select_one(
        ".price .strike-through .value, .strike-through .cc-price, .price-standard, .list .value"
    )

    price = None
    if sales_el:
        price = sales_el.get("content") or clean_price(sales_el.get_text(strip=True))
    if not price:
        price_el = tile.select_one("span.cc-price")
        price = (
            price_el.get("content") if price_el else None
        ) or clean_price(price_el.get_text(strip=True) if price_el else None)

    compare_at_price = None
    if list_el:
        compare_at_price = list_el.get("content") or clean_price(list_el.get_text(strip=True))
    if compare_at_price in {"0.00", "0", 0} or (
        compare_at_price and price and compare_at_price == price
    ):
        compare_at_price = None

    img = tile.select_one("img.tile-image, div.image-container img, img")
    image = None
    alt = ""
    if img:
        image = img.get("data-src") or img.get("src")
        alt = img.get("alt") or ""
        if image and image.startswith("data:"):
            image = img.get("data-src")
    if image and image.startswith("//"):
        image = "https:" + image
    elif image and image.startswith("/"):
        image = BASE_URL + image

    labels = " ".join(
        el.get_text(" ", strip=True).lower()
        for el in tile.select(".product-labels, .product-flag, .badge, .newIn")
    )
    available = not any(x in labels for x in ["sold out", "out of stock", "unavailable"])

    # sizes from hover panel if present
    size_els = tile.select(".js-size-details button, .size-detail-hover button, .size-value")
    size = None
    if size_els:
        size = size_els[0].get_text(strip=True) or size_els[0].get("data-attr-value")

    return {
        "title": title,
        "color": extract_color(alt, pid or ""),
        "fabric": extract_fabric(title or "", alt, subtitle),
        "price": price,
        "compare_at_price": compare_at_price,
        "image": image,
        "product_url": product_url,
        "department": detect_department(title or "", alt, subtitle, product_url or ""),
        "subcategory": detect_subcategory(title or "", alt, subtitle),
        "category": detect_category(title or "", alt, subtitle, product_url or ""),
        "product_type": title,
        "pieces": detect_pieces(title or "", alt),
        "size": size,
        "sku": pid,
        "available": available,
        "_pid": pid,
    }


def scrape_sapphire():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    scraped_data = []
    seen = set()
    start = 0
    page_size = 36
    page = 0

    while True:
        page += 1
        url = (
            f"{BASE_URL}/on/demandware.store/Sites-Sapphire-Site/default/"
            f"Search-UpdateGrid?cgid=root&start={start}&sz={page_size}"
        )
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
        tiles = soup.select("div.plp-tile")
        if not tiles:
            print("No more products found.", flush=True)
            break

        new_count = 0
        for tile in tiles:
            item = parse_tile(tile)
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

        if new_count == 0:
            print("No new products; stopping.", flush=True)
            break

        start += page_size
        time.sleep(random.uniform(0.25, 0.6))

    return {"data": scraped_data}


def save_json(payload):
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), OUTPUT_NAME),
        os.path.join(os.path.expanduser("~"), OUTPUT_NAME),
        os.path.join(os.environ.get("TEMP", "."), OUTPUT_NAME),
    ]
    for output_file in candidates:
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4, ensure_ascii=False)
            print(f"Data successfully saved to {output_file}", flush=True)
            return output_file
        except Exception as err:
            print(f"Could not save to {output_file}: {err}", flush=True)
    return None


if __name__ == "__main__":
    print("Starting Sapphire FULL catalog scrape ...", flush=True)
    print("Source: https://pk.sapphireonline.pk (cgid=root)", flush=True)
    print(f"Seed grid: {GRID_URL}", flush=True)
    result = scrape_sapphire()
    print(f"Successfully scraped {len(result['data'])} products.", flush=True)
    save_json(result)
