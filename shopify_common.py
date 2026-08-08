"""Shared Shopify full-catalog scraper used by left brands."""
from __future__ import annotations

import os
import re
import json
import time
import random
import requests
from typing import Optional, List, Dict, Any

FABRIC_KEYWORDS = [
    "Lawn", "Cotton", "Chiffon", "Karandi", "Khaddar", "Cambric", "Linen",
    "Organza", "Silk", "Net", "Velvet", "Dobby", "Slub", "Swiss", "Voile",
    "Jacquard", "Tissue", "Georgette", "Sateen", "Viscose", "Latha",
    "Marina", "Raw Silk", "Boski", "Wash & Wear", "Wash and Wear",
]


def normalize_tags(tags) -> List[str]:
    if not tags:
        return []
    if isinstance(tags, str):
        return [t.strip() for t in tags.split(",") if t.strip()]
    return [str(t).strip() for t in tags if str(t).strip()]


def option_value(product: dict, option_name: str) -> Optional[str]:
    name = option_name.strip().lower()
    for option in product.get("options") or []:
        if (option.get("name") or "").strip().lower() == name:
            values = option.get("values") or []
            if values and values[0] not in {"Default Title", "Default", "Select"}:
                return values[0]
    return None


def body_field(body: str, label: str) -> Optional[str]:
    if not body:
        return None
    patterns = [
        rf"{label}\s*:\s*</strong>\s*([^<\n]+)",
        rf"<strong>\s*{label}\s*:\s*</strong>\s*([^<\n]+)",
        rf"{label}\s*:\s*([^<\n]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, body, re.I)
        if m:
            value = re.sub(r"&nbsp;?", " ", m.group(1)).strip()
            value = re.sub(r"\s+", " ", value).strip(" .")
            if value and value.lower() not in {"n/a", "-", "none"}:
                return value
    return None


def extract_fabric(product: dict) -> Optional[str]:
    value = option_value(product, "Fabric")
    if value:
        return value
    body = product.get("body_html") or ""
    for label in ("Shirt Fabric", "Fabric", "Trouser Fabric", "Dupatta Fabric"):
        value = body_field(body, label)
        if value:
            return value
    for tag in normalize_tags(product.get("tags")):
        m = re.match(r"fabric\s*=\s*(.+)$", tag, re.I)
        if m:
            return m.group(1).strip()
    blob = " ".join(
        [
            product.get("title") or "",
            product.get("product_type") or "",
            " ".join(normalize_tags(product.get("tags"))),
            body,
        ]
    )
    for fabric in FABRIC_KEYWORDS:
        if re.search(rf"\b{re.escape(fabric)}\b", blob, re.I):
            return fabric.upper()
    return None


def extract_color(product: dict) -> Optional[str]:
    value = option_value(product, "Color") or option_value(product, "Colour")
    if value:
        return value
    return body_field(product.get("body_html") or "", "Colou?r")


def detect_category(title: str, tags: List[str], product_type: str) -> Optional[str]:
    blob = " ".join([title or "", " ".join(tags), product_type or ""]).lower()
    ptype = (product_type or "").lower()
    if any(
        x in blob
        for x in [
            "fragrance",
            "perfume",
            "footwear",
            "shoes",
            "bags",
            "handbag",
            "accessories",
            "jewelry",
            "jewellery",
            "scarf",
            "hijab",
        ]
    ) and not any(x in blob for x in ["unstitched", "stitched", "pret", "rtw", "rts", "suit"]):
        return None
    if (
        "unstitched" in blob
        or re.search(r"\brts\b", blob)
        or "ready to stitch" in blob
        or "fabric" in ptype
        or "pack suit" in ptype
    ):
        return "Unstitched"
    if (
        "ready to wear" in blob
        or re.search(r"\brtw\b", blob)
        or re.search(r"\bpret\b", blob)
        or "stitched" in blob
        or "kurta" in blob
        or "western" in blob
        or "co-ord" in blob
        or "coord" in blob
    ):
        return "Stitched"
    return None


def detect_department(tags: List[str], product_type: str, title: str) -> Optional[str]:
    tags_lower = {t.lower() for t in tags}
    tags_blob = " ".join(tags_lower)
    ptype = (product_type or "").lower()
    title_l = (title or "").lower()
    blob = f"{tags_blob} {ptype} {title_l}"

    if any(x in blob for x in ["fragrance", "perfume", "body mist", "eau de"]):
        return "Fragrances"
    if any(x in blob for x in ["home", "bedsheet", "towel", "cushion", "duvet"]):
        return "Home"
    if "bag" in blob or "handbag" in blob or "tote" in blob:
        return "Bags"
    if any(x in blob for x in ["jewelry", "jewellery", "earring", "necklace", "bracelet"]):
        return "Jewellery"
    if any(x in blob for x in ["shoe", "footwear", "sandal", "heel", "scarf", "hijab", "dupatta"]) and not any(
        x in blob for x in ["unstitched", "rtw", "pret", "suit"]
    ):
        return "Accessories"
    if "accessories" in blob and not any(x in blob for x in ["unstitched", "rtw", "pret", "suit", "stitched"]):
        return "Accessories"
    if any(t for t in tags_lower if "kid" in t) or "kids" in blob or "boys" in blob or "girls" in blob:
        return "Kids"
    has_men = any(
        t in {"men", "man", "mens", "menswear"} or t.startswith("men-") or t.startswith("men/") or t.startswith("mens")
        for t in tags_lower
    ) or re.search(r"\bmen'?s\b", blob) or "menswear" in blob
    has_women = any(
        t in {"women", "woman", "womens", "ladies"} or t.startswith("women") or t.startswith("woman")
        for t in tags_lower
    ) or re.search(r"\bwomen'?s\b", blob)
    if has_men and not has_women:
        return "Men"
    if has_women and not has_men:
        return "Women"
    if has_men and has_women:
        return "Men" if any(t.startswith("men") for t in tags_lower) else "Women"
    return "Women"


def detect_subcategory(tags: List[str], product_type: str, title: str) -> Optional[str]:
    ptype = (product_type or "").strip()
    if ptype and ptype.lower() not in {"", "default", "true", "product"}:
        return ptype
    blob = " ".join([title or "", " ".join(tags)]).lower()
    rules = [
        ("Fragrances", [r"\bfragrance", r"\bperfume\b"]),
        ("Bags", [r"\bbags?\b", r"\bhandbag\b"]),
        ("Footwear", [r"\bfootwear\b", r"\bshoes?\b"]),
        ("Kids", [r"\bkids?\b"]),
        ("Ready to Wear", [r"\brtw\b", r"\bready to wear\b", r"\bpret\b"]),
        ("Unstitched", [r"\bunstitched\b", r"\brts\b"]),
        ("Accessories", [r"\baccessories\b"]),
    ]
    for label, patterns in rules:
        if any(re.search(p, blob, re.I) for p in patterns):
            return label
    return None


def detect_pieces(title: str, tags: List[str], body: str) -> Optional[str]:
    blob = " ".join([title or "", " ".join(tags), body or ""])
    m = re.search(r"\b([1234])\s*[- ]?\s*piece\b", blob, re.I)
    if m:
        return f"{m.group(1)} Piece"
    m = re.search(r"\b([1234])\s*[- ]?\s*pc\b", blob, re.I)
    if m:
        return f"{m.group(1)} Piece"
    return None


def scrape_shopify_catalog(base_url: str, brand_name: str = "") -> Dict[str, Any]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    page = 1
    scraped_data = []
    base = base_url.rstrip("/")

    while True:
        url = f"{base}/products.json?limit=250&page={page}"
        print(f"[{brand_name or base}] Fetching: {url}", flush=True)
        try:
            response = requests.get(url, headers=headers, timeout=45)
        except Exception as e:
            print(f"Request error: {e}", flush=True)
            break
        if response.status_code != 200:
            print(f"Failed status {response.status_code}", flush=True)
            break
        try:
            payload = response.json()
        except Exception as e:
            print(f"JSON parse error: {e}", flush=True)
            break

        products = payload.get("products") or []
        if not products:
            print("No more products found.", flush=True)
            break

        print(f"Page {page}: {len(products)} products", flush=True)
        for product in products:
            title = product.get("title")
            tags = normalize_tags(product.get("tags"))
            body = product.get("body_html") or ""
            raw_type = (product.get("product_type") or "").strip()
            product_type = raw_type if raw_type and raw_type.lower() not in {"default", "true"} else None
            variant = (product.get("variants") or [{}])[0]
            images = product.get("images") or []
            handle = product.get("handle")
            price = variant.get("price")
            compare = variant.get("compare_at_price")
            if compare in {"0.00", "0", 0} or (compare and price and str(compare) == str(price)):
                compare = None

            scraped_data.append(
                {
                    "title": title,
                    "color": extract_color(product),
                    "fabric": extract_fabric(product),
                    "price": price,
                    "compare_at_price": compare,
                    "image": images[0].get("src") if images else None,
                    "product_url": f"{base}/products/{handle}" if handle else None,
                    "department": detect_department(tags, product_type or "", title or ""),
                    "subcategory": detect_subcategory(tags, product_type or "", title or ""),
                    "category": detect_category(title or "", tags, product_type or ""),
                    "product_type": product_type,
                    "pieces": detect_pieces(title or "", tags, body),
                    "size": option_value(product, "Size")
                    or option_value(product, "SIZE")
                    or option_value(product, "SIze"),
                    "sku": variant.get("sku"),
                    "available": variant.get("available"),
                }
            )

        page += 1
        time.sleep(random.uniform(0.8, 1.6))

    return {"data": scraped_data}


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
