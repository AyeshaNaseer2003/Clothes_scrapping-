"""Scrape Faraz Manan (www.farazmanan.com).

Magento-based lookbook store; no Shopify /products.json and no public REST
API. Products are listed as "lookbook panes" on collection pages:
  <div data-product-id=".." data-name=".." data-short-spec=".." ...>
    <img data-large-image="..">
Collections paginate via ?p=N. Prices are not published online (couture
"call for pricing" house) - we capture name + full-size image + collection.
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

BASE_URL = "https://www.farazmanan.com"
OUTPUT_NAME = "faraz_manan_products.json"
BRAND = "Faraz Manan"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

SEED_PATHS = [
    "/pk/bridal-couture.html",
    "/pk/ready-to-wear.html",
    "/pk/menswear.html",
    "/pk/ready-couture.html",
    "/pk/resort.html",
]


def get_page(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.text


def get_collection_urls(seed_pages: List[str]) -> List[str]:
    """Top-level collections plus every sub-collection linked from nav."""
    urls: List[str] = []
    seen = set()
    for seed in seed_pages:
        try:
            html = get_page(BASE_URL + seed)
        except Exception as e:
            print(f"  ERR {seed}: {e}", flush=True)
            continue
        for href in re.findall(r'href="(https://www\.farazmanan\.com/pk/[^"]+\.html)"', html):
            if href not in seen:
                seen.add(href)
                urls.append(href)
    return urls


def scrape_collection(url: str) -> List[Dict[str, Any]]:
    """Walk all ?p=N pages of a collection, collecting unique panes."""
    panes: Dict[str, Dict[str, Any]] = {}
    page = 1
    while True:
        page_url = f"{url}?p={page}" if page > 1 else url
        try:
            html = get_page(page_url)
        except Exception as e:
            print(f"  ERR {page_url}: {e}", flush=True)
            break
        found = 0
        for m in re.finditer(
            r'data-product-id="([^"]+)"[^>]*data-name="([^"]*)"[^>]*data-short-spec="([^"]*)"[^>]*class="lookbook-pane"',
            html,
        ):
            pid, name, spec = m.group(1), m.group(2), m.group(3)
            # image may come before/after the data-name attrs - search enclosing div
            start = html.rfind("<div", 0, m.start())
            end = html.find("</div>", m.end())
            chunk = html[start:end]
            img_m = re.search(r'data-large-image="([^"]+)"', chunk)
            img = img_m.group(1) if img_m else None
            panes[pid] = {
                "product_id": pid,
                "title": name.strip() or None,
                "short_spec": spec.strip() or None,
                "image": img,
                "collection_url": url,
            }
            found += 1
        if found == 0 and page > 1:
            break  # page 1 must yield panes; extra pages stop when empty
        m_total = re.search(r'class="pages"[^>]*>\s*<strong></strong>\s*<ol>(.*?)</ol>', html, re.S)
        if not m_total:
            break
        page_links = re.findall(rf'href="[^"]*\?p=(\d+)"', m_total.group(1))
        max_page = max(int(p) for p in page_links) if page_links else page
        if page >= max_page:
            break
        page += 1
        time.sleep(random.uniform(0.5, 1.2))
    return list(panes.values())


def pane_to_item(pane: Dict[str, Any], collection_label: str) -> Dict[str, Any]:
    blob = " ".join([pane.get("title") or "", pane.get("short_spec") or ""])
    b = blob.lower()
    department = "Men" if any(k in b for k in ["sherwani", "waistcoat", "menswear", "men"]) else "Women"
    category = None
    if any(k in b for k in ["bridal", "couture", "gown", "lehenga"]):
        category = "Stitched"
    elif any(k in b for k in ["rtw", "pret", "ready to wear", "ready-to-wear"]):
        category = "Stitched"
    elif any(k in b for k in ["unstitched", "fabric"]):
        category = "Unstitched"
    pieces = None
    m = re.search(r"\b([1234])\s*[- ]?\s*(?:piece|pc)\b", blob, re.I)
    if m:
        pieces = f"{m.group(1)} Piece"
    return {
        "title": pane.get("title"),
        "color": None,
        "fabric": None,
        "price": None,
        "compare_at_price": None,
        "images_list": [pane["image"]] if pane.get("image") else [],
        "product_url": None,
        "department": department,
        "subcategory": None,
        "category": category,
        "product_type": pane.get("short_spec"),
        "pieces": pieces,
        "size_details": [],
        "sku": None,
        "available": True,
        "collection": collection_label,
    }


def scrape_catalog() -> List[Dict[str, Any]]:
    collections = get_collection_urls(SEED_PATHS)
    print(f"[{BRAND}] Collections found: {len(collections)}", flush=True)
    all_panes: Dict[str, Dict[str, Any]] = {}
    for url in collections:
        try:
            panes = scrape_collection(url)
        except Exception as e:
            print(f"  ERR collection {url}: {e}", flush=True)
            continue
        label = url.replace(BASE_URL + "/pk/", "").replace(".html", "")
        for pane in panes:
            key = (pane.get("product_id"), pane.get("title"), pane.get("image"))
            agg = all_panes.setdefault(key, pane)
            agg["collection"] = agg.get("collection") or label
        print(f"[{BRAND}] {url}: {len(panes)} panes", flush=True)
        time.sleep(random.uniform(0.5, 1.2))

    print(f"[{BRAND}] Unique panes: {len(all_panes)}", flush=True)
    items = []
    for key, pane in all_panes.items():
        first_coll = pane.get("collection") or pane.get("collection_url") or ""
        items.append(pane_to_item(pane, first_coll))
    return items


def report(items: List[Dict[str, Any]]) -> None:
    print(f"[{BRAND}] Total products: {len(items)}", flush=True)
    if not items:
        return
    with_images = sum(1 for p in items if p.get("images_list"))
    with_name = sum(1 for p in items if p.get("title"))
    print(f"[{BRAND}] products with images_list: {with_images}", flush=True)
    print(f"[{BRAND}] products with title: {with_name}", flush=True)
    sample = items[0]
    print(f"[{BRAND}] sample title: {sample.get('title')}", flush=True)
    print(f"[{BRAND}] sample images count: {len(sample.get('images_list') or [])}", flush=True)
    print(f"[{BRAND}] sample collection: {sample.get('collection')}", flush=True)


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
    print(f"Source: {BASE_URL} (Magento lookbook HTML)", flush=True)
    items = scrape_catalog()
    result = {"data": items}
    report(items)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), OUTPUT_NAME)
    save_json(result, out)