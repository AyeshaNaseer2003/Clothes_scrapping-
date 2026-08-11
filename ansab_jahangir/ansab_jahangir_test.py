"""Scrape Ansab Jahangir Studio (Apparelverse / nopCommerce)."""
import os
import re
import json
import time
import random
import requests
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

BASE_URL = "https://www.ansabjahangirstudio.com"
OUTPUT_NAME = "ansab_jahangir_products.json"

# Prefer leaf/collection category paths (avoid mega-menu parents that overlap)
SEED_PATHS = [
    "/new-arrivals",
    "/ready-to-ship",
    "/best-sellers",
    "/luxepret",
    "/luxe-pret-25",
    "/basics",
    "/formals",
    "/light-formals",
    "/velvets",
    "/artisan-prints-26",
    "/resort-26",
    "/summer-kaftans",
    "/girls-club",
    "/the-girls-club",
    "/cest-parti-25",
    "/sorbet-stories-25",
    "/digital-silk",
    "/chikankari",
    "/the-velvet-dynasty",
    "/so-hot",
    "/nikkah",
]

FABRIC_KEYWORDS = [
    "Lawn", "Cotton", "Chiffon", "Silk", "Khadi", "Organza", "Net",
    "Velvet", "Georgette", "Tissue", "Cambric", "Linen", "Raw Silk",
]


def clean_price(text: str) -> Optional[str]:
    if not text:
        return None
    digits = re.sub(r"[^\d.]", "", text.replace(",", ""))
    return digits or None


def detect_fabric(blob: str) -> Optional[str]:
    for fabric in FABRIC_KEYWORDS:
        if re.search(rf"\b{re.escape(fabric)}\b", blob or "", re.I):
            return fabric.upper()
    return None


def detect_pieces(blob: str) -> Optional[str]:
    m = re.search(r"\b([1234])\s*[- ]?\s*piece\b", blob or "", re.I)
    if m:
        return f"{m.group(1)} Piece"
    return None


def detect_category(blob: str) -> Optional[str]:
    b = (blob or "").lower()
    if "unstitched" in b:
        return "Unstitched"
    if any(x in b for x in ["pret", "stitched", "ready to wear", "rtw", "shirt", "kaftan", "formal"]):
        return "Stitched"
    return None


def detect_department(blob: str) -> Optional[str]:
    b = (blob or "").lower()
    if "girl" in b or "kids" in b:
        return "Kids"
    if re.search(r"\bmen\b", b):
        return "Men"
    return "Women"


def parse_item(box, category_path: str) -> Optional[Dict[str, Any]]:
    title_el = box.select_one(".product-title a, .product-title, h2 a, h2")
    if not title_el:
        return None
    title = title_el.get_text(" ", strip=True)
    href = title_el.get("href") if title_el.name == "a" else None
    if not href:
        link = box.select_one("a[href]")
        href = link.get("href") if link else None
    product_url = urljoin(BASE_URL, href) if href else None

    pid_match = re.search(r"/addproducttocart/catalog/(\d+)/", str(box))
    sku = pid_match.group(1) if pid_match else None
    if not sku and product_url:
        sku = urlparse(product_url).path.strip("/").split("/")[-1]

    price_el = box.select_one(".actual-price, .price.actual-price, .prices .actual-price, .price")
    old_el = box.select_one(".old-price, .price.old-price")
    price = clean_price(price_el.get_text(" ", strip=True) if price_el else "")
    compare = clean_price(old_el.get_text(" ", strip=True) if old_el else "")
    if compare and price and compare == price:
        compare = None

    img = box.select_one("img")
    image = None
    alt = ""
    if img:
        image = img.get("data-lazyloadsrc") or img.get("data-src") or img.get("src")
        alt = img.get("alt") or ""
        if image and image.startswith("//"):
            image = "https:" + image
        elif image and image.startswith("/"):
            image = BASE_URL + image

    desc_el = box.select_one(".description, .product-description")
    desc = desc_el.get_text(" ", strip=True) if desc_el else ""
    blob = " ".join([title or "", alt, desc, category_path])

    labels = box.get_text(" ", strip=True).lower()
    available = not any(x in labels for x in ["sold out", "out of stock", "unavailable"])

    return {
        "title": title,
        "color": None,
        "fabric": detect_fabric(blob),
        "price": price,
        "compare_at_price": compare,
        "images_list": [image] if image else [],
        "product_url": product_url,
        "department": detect_department(blob),
        "subcategory": category_path.strip("/").replace("-", " ").title() if category_path else None,
        "category": detect_category(blob),
        "product_type": title,
        "pieces": detect_pieces(blob),
        "size_details": [],
        "sku": sku,
        "available": available,
    }


def discover_categories(session: requests.Session) -> List[str]:
    paths = list(SEED_PATHS)
    try:
        r = session.get(BASE_URL + "/", timeout=40)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select("a[href]"):
            href = (a.get("href") or "").split("?")[0]
            if not href.startswith("/"):
                continue
            if any(
                x in href.lower()
                for x in [
                    "cart", "login", "register", "wishlist", "contact", "policy",
                    "account", "search", "plugin", "content", "theme", ".css", ".js",
                    "addproduct", "blog",
                ]
            ):
                continue
            if 1 < len(href.strip("/")) < 60:
                paths.append(href)
    except Exception as e:
        print(f"Category discovery warning: {e}", flush=True)

    # unique preserve order
    seen = set()
    out = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def scrape_category(session: requests.Session, path: str, seen: set) -> List[dict]:
    items = []
    page = 1
    while page <= 200:
        url = f"{BASE_URL}{path}?pagenumber={page}"
        print(f"Fetching {url}", flush=True)
        try:
            r = session.get(url, timeout=45)
        except Exception as e:
            print(f"Request error: {e}", flush=True)
            break
        if r.status_code != 200:
            print(f"Status {r.status_code}", flush=True)
            break

        soup = BeautifulSoup(r.text, "html.parser")
        boxes = soup.select(".item-box, .product-item")
        if not boxes:
            break

        new_count = 0
        for box in boxes:
            item = parse_item(box, path)
            if not item:
                continue
            key = item.get("sku") or item.get("product_url") or item.get("title")
            if not key or key in seen:
                continue
            seen.add(key)
            items.append(item)
            new_count += 1

        print(f"  page {page}: boxes={len(boxes)} new={new_count} total_unique={len(seen)}", flush=True)
        if new_count == 0:
            break
        page += 1
        time.sleep(random.uniform(0.35, 0.8))

    return items


def scrape_ansab() -> dict:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
    )
    seen = set()
    data = []
    cats = discover_categories(session)
    print(f"Scanning {len(cats)} category paths ...", flush=True)
    for path in cats:
        data.extend(scrape_category(session, path, seen))
    return {"data": data}


def save_json(payload: dict) -> Optional[str]:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, OUTPUT_NAME)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4, ensure_ascii=False)
    print(f"Saved {len(payload['data'])} products -> {path}", flush=True)
    return path


if __name__ == "__main__":
    print("Starting Ansab Jahangir FULL catalog scrape ...", flush=True)
    print(f"Source: {BASE_URL}", flush=True)
    result = scrape_ansab()
    print(f"Successfully scraped {len(result['data'])} products.", flush=True)
    save_json(result)
