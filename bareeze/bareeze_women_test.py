"""Scrape Bareeze women's catalog (bareeze.com).

bareeze.com is a Next.js (App Router) storefront on the Ginkgo Retail
(Comverse) platform - it does NOT expose Shopify /products.json. The full
product catalog is server-rendered into the React Server Components (RSC)
payload embedded in each collection page as self.__next_f.push(...) chunks.

Each collection page paginates cumulatively: requesting
  /<category>?page=N  returns the first (N * 16) products embedded in the
payload, so one request per category at page=ceil(count/16) returns the
whole category. We crawl every unique category from the sitemap, collect all
products, dedupe by product id, and map them to the standard schema.
"""
from __future__ import annotations

import os
import re
import json
import time
import random
import requests
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin

BASE_URL = "https://www.bareeze.com"
OUTPUT_NAME = "bareeze_women_products.json"
BRAND = "Bareeze Women"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

PRODUCTS_PER_PAGE = 16

FABRIC_KEYWORDS = [
    "Lawn", "Cotton", "Chiffon", "Karandi", "Khaddar", "Cambric", "Linen",
    "Organza", "Silk", "Net", "Velvet", "Dobby", "Slub", "Swiss", "Voile",
    "Jacquard", "Tissue", "Georgette", "Sateen", "Viscose", "Latha",
    "Marina", "Raw Silk", "Boski", "Wash & Wear", "Wash and Wear",
]


def get_rsc_blob(url: str) -> str:
    """Fetch a page and extract the merged RSC flight payload."""
    response = requests.get(url, headers=HEADERS, timeout=60)
    response.raise_for_status()
    pushes = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', response.text, re.S)
    return " ".join(pushes).encode("utf-8").decode("unicode_escape", errors="replace")


def extract_json_arrays(blob: str, marker: str = '"count":') -> List[List[Dict[str, Any]]]:
    """Extract every JSON array that follows a `<marker>:<n>,"data":[` fragment."""
    out: List[List[Dict[str, Any]]] = []
    for m in re.finditer(r'("count":\d+,"data":\[)', blob):
        start = m.end() - 1  # position of '['
        i = start + 1
        depth = 1
        in_str = False
        esc = False
        while i < len(blob) and depth > 0:
            ch = blob[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
            i += 1
        seg = blob[start:i].replace('\\"', '"')
        try:
            arr = json.loads(seg)
            if isinstance(arr, list):
                out.append(arr)
        except Exception:
            pass
    return out


def get_category_handles() -> List[str]:
    """All unique category paths from the sitemap (skipping junk pages)."""
    sitemap_url = urljoin(BASE_URL, "/sitemap/sitemap_cat_0.xml")
    response = requests.get(sitemap_url, headers=HEADERS, timeout=60)
    response.raise_for_status()
    handles = []
    seen = set()
    for loc in re.findall(r"<loc>([^<]+)</loc>", response.text):
        path = loc.replace("https://bareeze.com", "").replace(BASE_URL, "").strip("/")
        parts = [p for p in path.split("/") if p]
        if not parts:
            continue
        if parts[0] in {"lookbook", "pages", "test", "bareeze"}:
            continue
        if path not in seen:
            seen.add(path)
            handles.append(path)
    return handles


def feature_value(product: dict, name: str) -> Optional[str]:
    name_l = name.strip().lower()
    for f in product.get("features") or []:
        if (f.get("name") or "").strip().lower() == name_l:
            v = (f.get("value") or "").strip()
            if v:
                return v
    return None


def clean_price(text) -> Optional[str]:
    if not text:
        return None
    digits = re.sub(r"[^\d.]", "", str(text).replace(",", ""))
    return digits or None


def detect_category(product: dict, blob: str) -> Optional[str]:
    b = (blob or "").lower()
    ptype = feature_value(product, "Category") or ""
    if any(x in b for x in ["unstitched", "ready to stitch", "fabric"]) or "fabric" in (ptype or "").lower():
        return "Unstitched"
    if any(x in b for x in ["ready to wear", "rtw", "pret", "stitched", "kurta", "shirt"]):
        return "Stitched"
    return None


def detect_department(product: dict, blob: str) -> Optional[str]:
    b = (blob or "").lower()
    if any(x in b for x in ["man ", " men", "menswear"]) and "women" not in b:
        return "Men"
    if "kid" in b or "girl" in b or "boy" in b:
        return "Kids"
    if any(x in b for x in ["shawl", "bag", "home", "bedsheet", "towel"]):
        return "Accessories"
    return "Women"


def detect_pieces(product: dict, blob: str) -> Optional[str]:
    m = re.search(r"\b([1234])\s*[- ]?\s*(?:piece|pc)\b", blob or "", re.I)
    if m:
        return f"{m.group(1)} Piece"
    return None


def product_to_item(product: dict) -> Dict[str, Any]:
    title = product.get("title")
    handle = product.get("handle")
    features = product.get("features") or []
    blob = " ".join([title or "", " ".join(str(f.get("value")) for f in features)])
    fabric = feature_value(product, "Fabric")
    if not fabric:
        for kw in FABRIC_KEYWORDS:
            if re.search(rf"\b{re.escape(kw)}\b", blob, re.I):
                fabric = kw.upper()
                break
    color = feature_value(product, "Color")
    variant = product.get("variant_detail") or {}
    price = clean_price(variant.get("discounted_price"))
    compare = clean_price(variant.get("original_price"))
    if compare and price and str(compare) == str(price):
        compare = None
    images = product.get("images") or []
    images_list = []
    for img in images:
        if isinstance(img, str):
            images_list.append(img)
        elif isinstance(img, dict) and img.get("cdn_link"):
            images_list.append(img["cdn_link"])
    return {
        "title": title,
        "color": color,
        "fabric": fabric,
        "price": price,
        "compare_at_price": compare,
        "images_list": images_list,
        "product_url": f"{BASE_URL}/{handle}" if handle else None,
        "department": detect_department(product, blob),
        "subcategory": feature_value(product, "Category"),
        "category": detect_category(product, blob),
        "product_type": feature_value(product, "Type"),
        "pieces": detect_pieces(product, blob),
        "size_details": [],
        "sku": None,
        "available": not bool(product.get("sold_out")),
    }


def scrape_catalog() -> List[Dict[str, Any]]:
    handles = get_category_handles()
    print(f"[{BRAND}] Categories found: {len(handles)}", flush=True)

    by_id: Dict[str, Dict[str, Any]] = {}
    fetched = 0
    for path in handles:
        url = f"{BASE_URL}/{path}"
        try:
            blob_page1 = get_rsc_blob(url)
        except Exception as e:
            print(f"[{BRAND}] ERR {path}: {e}", flush=True)
            time.sleep(2)
            continue
        arrays = extract_json_arrays(blob_page1)
        count = None
        m = re.search(r'"count":(\d+)', blob_page1)
        if m:
            count = int(m.group(1))
        if not arrays or not count:
            fetched += 1
            continue
        # cumulative pagination: one more request returns everything
        needed_pages = max(1, (count + PRODUCTS_PER_PAGE - 1) // PRODUCTS_PER_PAGE)
        try:
            final_blob = get_rsc_blob(f"{url}?page={needed_pages}") if needed_pages > 1 else blob_page1
            for arr in extract_json_arrays(final_blob):
                for p in arr:
                    pid = str(p.get("id") or "")
                    if pid:
                        by_id[pid] = p
        except Exception as e:
            print(f"[{BRAND}] ERR paginate {path}: {e}", flush=True)
        fetched += 1
        if fetched % 25 == 0:
            print(f"[{BRAND}] {fetched}/{len(handles)} categories, unique products: {len(by_id)}", flush=True)
        time.sleep(random.uniform(0.6, 1.4))

    print(f"[{BRAND}] Total unique products collected: {len(by_id)}", flush=True)
    items = [product_to_item(p) for p in by_id.values()]
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
    print(f"[{BRAND}] sample price: {sample.get('price')} | compare: {sample.get('compare_at_price')}", flush=True)
    print(f"[{BRAND}] sample color: {sample.get('color')} | fabric: {sample.get('fabric')}", flush=True)


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
    print(f"Source: {BASE_URL} (Next.js / Ginkgo Retail RSC payload)", flush=True)
    items = scrape_catalog()
    result = {"data": items}
    report(items)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), OUTPUT_NAME)
    save_json(result, out)