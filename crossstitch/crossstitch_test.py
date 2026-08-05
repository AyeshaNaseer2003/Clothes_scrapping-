import os
import re
import json
import time
import random
import requests
from typing import Optional, List

BASE_URL = "https://www.crossstitch.pk"
OUTPUT_NAME = "shopify_products.json"

FABRIC_KEYWORDS = [
    "Lawn", "Cotton", "Chiffon", "Karandi", "Khaddar", "Cambric", "Linen",
    "Organza", "Silk", "Net", "Velvet", "Dobby", "Slub", "Swiss", "Voile",
    "Jacquard", "Tissue", "Georgette", "Sateen", "Viscose", "Marina",
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


def extract_fabric(product: dict) -> Optional[str]:
    value = option_value(product, "Fabric")
    if value:
        return value

    blob = " ".join(
        [
            product.get("title") or "",
            product.get("product_type") or "",
            " ".join(normalize_tags(product.get("tags"))),
            product.get("body_html") or "",
        ]
    )
    for fabric in FABRIC_KEYWORDS:
        if re.search(rf"\b{re.escape(fabric)}\b", blob, re.I):
            return fabric.upper()
    return None


def detect_category(title: str, tags: List[str], product_type: str) -> Optional[str]:
    blob = " ".join([title or "", " ".join(tags), product_type or ""]).lower()
    ptype = (product_type or "").lower()

    if any(
        x in blob
        for x in ["footwear", "scarves", "bags", "packaging", "easify_addon", "accessories"]
    ) and not any(x in blob for x in ["unstitched", "pret", "ready to wear", "rtw", "suit"]):
        return None

    if (
        "unstitched" in blob
        or re.search(r"\brts\b", blob)
        or "ready to stitch" in blob
        or ptype.endswith("suits")
        or ptype in {"exclusive suits", "luxury suits", "basic suits", "wedding suits", "basic suit"}
    ):
        return "Unstitched"
    if (
        "ready to wear" in blob
        or re.search(r"\brtw\b", blob)
        or "pret" in blob
        or "stitched" in blob
        or "pants" in ptype
        or "co ords" in blob
        or "co-ords" in blob
    ):
        return "Stitched"
    return None


def detect_department(tags: List[str], product_type: str, title: str) -> Optional[str]:
    tags_lower = {t.lower() for t in tags}
    tags_blob = " ".join(tags_lower)
    ptype = (product_type or "").lower()
    title_l = (title or "").lower()
    blob = f"{tags_blob} {ptype} {title_l}"

    if ptype in {"packaging", "easify_addon_product"}:
        return None
    if "bag" in blob or ptype == "bags":
        return "Bags"
    if ptype == "footwear" or "footwear" in blob or "shoe" in blob:
        return "Accessories"
    if ptype == "scarves" or "scarf" in blob or (
        "accessories" in tags_blob
        and not any(x in blob for x in ["pret", "unstitched", "rtw", "suit", "pants"])
    ):
        return "Accessories"
    if any(t in {"men", "man"} or t.startswith("men") for t in tags_lower):
        return "Men"
    if any(t for t in tags_lower if "kid" in t):
        return "Kids"
    return "Women"


def detect_subcategory(tags: List[str], product_type: str, title: str) -> Optional[str]:
    ptype = (product_type or "").strip()
    if ptype and ptype.lower() not in {"easify_addon_product", "packaging"}:
        return ptype.title() if ptype.isupper() else ptype

    blob = " ".join([title or "", " ".join(tags)]).lower()
    rules = [
        ("Bags", [r"\bbags?\b"]),
        ("Footwear", [r"\bfootwear\b", r"\bshoes?\b"]),
        ("Scarves", [r"\bscarves?\b", r"\bscarf\b"]),
        ("Luxury Pret", [r"\bluxury pret\b", r"\blux pret\b"]),
        ("Exclusive Pret", [r"\bexclusive pret\b"]),
        ("Wedding Pret", [r"\bwedding pret\b"]),
        ("Ready to Wear", [r"\bready to wear\b", r"\brtw\b"]),
        ("Unstitched", [r"\bunstitched\b", r"\brts\b"]),
    ]
    for label, patterns in rules:
        if any(re.search(p, blob, re.I) for p in patterns):
            return label
    return None


def detect_pieces(title: str, tags: List[str], body: str) -> Optional[str]:
    blob = " ".join([title or "", " ".join(tags), body or ""])
    m = re.search(r"\b([1234])\s*[- ]?\s*pc\b", blob, re.I)
    if m:
        return f"{m.group(1)} Piece"
    m = re.search(r"\b([1234])\s*[- ]?\s*piece\b", blob, re.I)
    if m:
        return f"{m.group(1)} Piece"
    m = re.search(r"\brtw-([1234])\s*piece\b", blob, re.I)
    if m:
        return f"{m.group(1)} Piece"
    return None


def scrape_crossstitch(base_url: str = BASE_URL) -> dict:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    page = 1
    scraped_data = []

    while True:
        url = f"{base_url.rstrip('/')}/products.json?limit=250&page={page}"
        print(f"Fetching URL: {url}", flush=True)

        try:
            response = requests.get(url, headers=headers, timeout=40)
        except Exception as e:
            print(f"Request error: {e}", flush=True)
            break

        if response.status_code != 200:
            print(f"Blocked or failed with status code {response.status_code}", flush=True)
            break

        try:
            payload = response.json()
        except Exception as e:
            print(f"Failed to parse JSON response: {e}", flush=True)
            break

        products = payload.get("products") or []
        if not products:
            print("No more products found.", flush=True)
            break

        print(f"Page {page}: Scraped {len(products)} products", flush=True)

        for product in products:
            title = product.get("title")
            tags = normalize_tags(product.get("tags"))
            body = product.get("body_html") or ""
            product_type = product.get("product_type") or None
            if product_type in {"", "easify_addon_product", "PACKAGING"}:
                # keep packaging/addon typed but department may be null
                pass
            variant = (product.get("variants") or [{}])[0]
            images = product.get("images") or []
            handle = product.get("handle")
            compare = variant.get("compare_at_price")
            price = variant.get("price")
            if compare in {"0.00", "0", 0} or (compare and price and str(compare) == str(price)):
                compare = None

            scraped_data.append(
                {
                    "title": title,
                    "color": option_value(product, "Color") or option_value(product, "Colour"),
                    "fabric": extract_fabric(product),
                    "price": price,
                    "compare_at_price": compare,
                    "image": images[0].get("src") if images else None,
                    "product_url": f"{base_url.rstrip('/')}/products/{handle}" if handle else None,
                    "department": detect_department(tags, product_type or "", title or ""),
                    "subcategory": detect_subcategory(tags, product_type or "", title or ""),
                    "category": detect_category(title or "", tags, product_type or ""),
                    "product_type": product_type,
                    "pieces": detect_pieces(title or "", tags, body),
                    "size": option_value(product, "Size"),
                    "sku": variant.get("sku"),
                    "available": variant.get("available"),
                }
            )

        page += 1
        time.sleep(random.uniform(1.0, 2.0))

    return {"data": scraped_data}


def save_json(payload: dict) -> Optional[str]:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, OUTPUT_NAME),
        os.path.join(os.path.expanduser("~"), OUTPUT_NAME),
        os.path.join(os.environ.get("TEMP", "."), OUTPUT_NAME),
    ]
    for path in candidates:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4, ensure_ascii=False)
            print(f"Data successfully saved to {path}", flush=True)
            return path
        except Exception as err:
            print(f"Could not save to {path}: {err}", flush=True)
    return None


if __name__ == "__main__":
    print("Starting Cross Stitch FULL catalog scrape ...", flush=True)
    print(f"Source: {BASE_URL}/products.json", flush=True)
    result = scrape_crossstitch()
    print(f"Successfully scraped {len(result['data'])} products.", flush=True)
    save_json(result)
