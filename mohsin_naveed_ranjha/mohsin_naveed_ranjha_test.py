"""Scrape Mohsin Naveed Ranjha (www.mohsinnaveedranjha.com).

nopCommerce-based store; no Shopify /products.json. Products are served in
server-rendered HTML:
- Collection pages list <a href="/product"><img alt="..."> cards, paginated
  via ?pagenumber=N (the page embeds `var pagesCount = N;`).
- Product pages expose the title (h1), gallery images (data-src thumbnails,
  full-size via stripping "_<w>" suffix), and spec labels
  (Color / Fabric / Work Details).
Prices are "Call for pricing" (meta itemprop=price 0.00).
"""
from __future__ import annotations

import os
import re
import json
import time
import random
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin
from bs4 import BeautifulSoup

BASE_URL = "https://www.mohsinnaveedranjha.com"
OUTPUT_NAME = "mnr_products.json"
BRAND = "Mohsin Naveed Ranjha"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Paths that are NOT product collections (info/utility pages)
SKIP_PATHS = {
    "/", "/about-us", "/contactus", "/faqs", "/privacy-notice", "/register",
    "/shipping-returns", "/free-shipping", "/catalog-3", "/favicon.ico",
    "/celebrity-spotted", "/celebrity-style-file", "/designer-picks",
}

FABRIC_KEYWORDS = [
    "Lawn", "Cotton", "Chiffon", "Karandi", "Khaddar", "Cambric", "Linen",
    "Organza", "Silk", "Net", "Velvet", "Dobby", "Georgette", "Tissue",
    "Jacquard", "Tissue", "Sateen", "Viscose", "Boski", "Raw Silk",
]

DEPT_KEYWORDS = {
    "Men": ["men", "mans", "groom", "sherwani", "waistcoat", "nehru", "shalwar"],
    "Kids": ["kid", "child", "boy", "girl"],
    "Bridal": ["bridal", "bride", "wedding", "nikkah", "walima", "mehndi", "peshwaz", "lehenga", "gharara", "saree"],
    "Luxury Pret": ["luxury pret", "luxury-pret", "pret"],
    "Formals": ["formal", "evening", "gown"],
    "Unstitched": ["unstitched", "fabric", "ready to stitch", "rts"],
}


def full_image_url(thumb: str) -> str:
    """Convert a nopCommerce thumbnail into the full-size picture URL."""
    m = re.match(r"^(.*)_\d+(\.[a-zA-Z0-9]+)$", thumb)
    if m:
        return m.group(1) + m.group(2)
    return thumb


def clean_price(text) -> Optional[str]:
    if not text:
        return None
    digits = re.sub(r"[^\d.]", "", str(text).replace(",", ""))
    return digits or None


def detect_department(blob: str) -> str:
    b = (blob or "").lower()
    for dept, kws in DEPT_KEYWORDS.items():
        for kw in kws:
            if kw in b:
                return dept
    return "Women"


def detect_category(blob: str) -> Optional[str]:
    b = (blob or "").lower()
    if any(x in b for x in ["unstitched", "ready to stitch", "fabric "]) and "stitched" not in b:
        return "Unstitched"
    if any(x in b for x in ["pret", "stitched", "ready to wear", "formal", "bridal", "sherwani", "kurta", "saree"]):
        return "Stitched"
    return None


def detect_pieces(blob: str) -> Optional[str]:
    m = re.search(r"\b([1234])\s*[- ]?\s*(?:piece|pc)\b", blob or "", re.I)
    if m:
        return f"{m.group(1)} Piece"
    return None


def get_collection_paths() -> List[str]:
    r = requests.get(BASE_URL + "/", headers=HEADERS, timeout=60)
    r.raise_for_status()
    paths = set()
    for href in re.findall(r'href="(/[^"#]*)"', r.text):
        path = href
        if not path.startswith("/") or path.startswith(("/Themes", "/lib", "/js", "/images", "/css")):
            continue
        if path in SKIP_PATHS or path.startswith(("/about-us", "/contactus", "/faqs", "/pages")):
            continue
        if "?" in path or "." in path.split("/")[-1]:
            continue
        paths.add(path)
    return sorted(paths)


def scrape_collection(path: str) -> List[str]:
    """Return all product URLs on a collection across all its pages."""
    product_urls: List[str] = []
    page = 1
    while True:
        url = f"{BASE_URL}{path}?pagenumber={page}" if page > 1 else f"{BASE_URL}{path}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
        except Exception as e:
            print(f"  ERR {url}: {e}", flush=True)
            break
        if r.status_code != 200:
            break
        html = r.text
        found = list(
            dict.fromkeys(
                href
                for href in re.findall(r'<a[^>]+href="(/[a-z0-9\-]+)"[^>]*>\s*<img', html)
            )
        )
        already = set(product_urls)
        new = [u for u in found if u not in already]
        product_urls.extend(new)
        m = re.search(r"var pagesCount = (\d+);", html)
        total_pages = int(m.group(1)) if m else 1
        if page >= total_pages or not new:
            break
        page += 1
        time.sleep(random.uniform(0.5, 1.0))
    return product_urls


def scrape_product(path: str) -> Optional[Dict[str, Any]]:
    url = BASE_URL + path
    try:
        r = requests.get(url, headers=HEADERS, timeout=60)
    except Exception as e:
        print(f"  ERR {url}: {e}", flush=True)
        return None
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")

    title_tag = soup.select_one("h1")
    title = title_tag.get_text(strip=True) if title_tag else None
    if not title:
        og = soup.select_one('meta[property="og:title"]')
        title = og.get("content") if og else None

    images_list = []
    for img in soup.select("img[data-src], img[src]"):
        src = img.get("data-src") or img.get("src") or ""
        if "images/thumbs" in src:
            images_list.append(full_image_url(urljoin(BASE_URL, src)))
    images_list = list(dict.fromkeys(images_list))

    spec_labels = {}
    for lab in soup.select("lable, label"):
        text = lab.get_text(strip=True)
        m = re.match(r"([\w ]+?):\s*(.*)", text)
        if m and m.group(2):
            spec_labels[m.group(1).strip().lower()] = m.group(2).strip()

    fabric = spec_labels.get("fabric")
    color = spec_labels.get("color")
    work_details = spec_labels.get("work details")

    price = None
    price_el = soup.select_one(".product-price .price, .prices .actual-price")
    if price_el:
        price = clean_price(price_el.get_text(strip=True))

    blob = " ".join(
        [title or "", color or "", fabric or "", work_details or "", path]
    )
    if not fabric:
        for kw in FABRIC_KEYWORDS:
            if re.search(rf"\b{re.escape(kw)}\b", blob, re.I):
                fabric = kw.upper()
                break

    return {
        "title": title,
        "color": color,
        "fabric": fabric,
        "price": price,
        "compare_at_price": None,
        "images_list": images_list,
        "product_url": url,
        "department": detect_department(blob),
        "subcategory": None,
        "category": detect_category(blob),
        "product_type": work_details,
        "pieces": detect_pieces(blob),
        "size_details": [],
        "sku": None,
        "available": True,
    }


def scrape_catalog() -> List[Dict[str, Any]]:
    paths = get_collection_paths()
    print(f"[{BRAND}] Collections found: {len(paths)}", flush=True)
    all_urls: List[str] = []
    for path in paths:
        try:
            urls = scrape_collection(path)
        except Exception as e:
            print(f"  ERR collection {path}: {e}", flush=True)
            urls = []
        print(f"[{BRAND}] {path}: {len(urls)} products", flush=True)
        all_urls.extend(urls)
        time.sleep(random.uniform(0.5, 1.0))

    uniq_urls = list(dict.fromkeys(all_urls))
    print(f"[{BRAND}] Unique product URLs: {len(uniq_urls)}", flush=True)

    items: List[Dict[str, Any]] = []
    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(scrape_product, path): path for path in uniq_urls}
        for fut in as_completed(futures):
            item = fut.result()
            if item:
                items.append(item)
            done += 1
            if done % 50 == 0:
                print(f"[{BRAND}] {done}/{len(uniq_urls)} products scraped ({len(items)} ok)", flush=True)
    return items


def report(items: List[Dict[str, Any]]) -> None:
    print(f"[{BRAND}] Total products: {len(items)}", flush=True)
    if not items:
        return
    with_images = sum(1 for p in items if p.get("images_list"))
    with_color = sum(1 for p in items if p.get("color"))
    with_fabric = sum(1 for p in items if p.get("fabric"))
    with_price = sum(1 for p in items if p.get("price"))
    print(f"[{BRAND}] products with images_list: {with_images}", flush=True)
    print(f"[{BRAND}] products with color:        {with_color}", flush=True)
    print(f"[{BRAND}] products with fabric:       {with_fabric}", flush=True)
    print(f"[{BRAND}] products with price:        {with_price}", flush=True)
    sample = items[0]
    print(f"[{BRAND}] sample images count: {len(sample.get('images_list') or [])}", flush=True)
    print(f"[{BRAND}] sample color: {sample.get('color')} | fabric: {sample.get('fabric')}", flush=True)
    print(f"[{BRAND}] sample price: {sample.get('price')}", flush=True)


def save_json(payload: dict, output_path: str) -> Optional[str]:
    folder = os.path.dirname(output_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, ensure_ascii=False)
        print(f"Saved {len(payload.get('data') or [])} products -> {output_path}", flush=True)
        return output_path
    except Exception as err:
        print(f"Could not save {output_path}: {err}", flush=True)
        return None


if __name__ == "__main__":
    print(f"Starting {BRAND} FULL catalog scrape ...", flush=True)
    print(f"Source: {BASE_URL} (nopCommerce HTML)", flush=True)
    items = scrape_catalog()
    result = {"data": items}
    report(items)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), OUTPUT_NAME)
    save_json(result, out)