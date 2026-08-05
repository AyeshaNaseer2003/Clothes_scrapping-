import os
import re
import stat
import json
import time
import random
import requests
from typing import Optional, List

BASE_URL = "https://www.gulahmedshop.com"
OUTPUT_NAME = "gulahmed_products.json"

FABRIC_KEYWORDS = [
    "Lawn", "Cotton", "Chiffon", "Karandi", "Khaddar", "Cambric",
    "Linen", "Organza", "Silk", "Net", "Velvet", "Dobby", "Slub",
    "Swiss", "Voile", "Jacquard", "Tissue", "Georgette", "Marina",
    "Mareena", "Viscose", "Wool", "Karandi",
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
            if values and values[0] not in {"Default Title", "Default"}:
                return values[0]
    return None


def extract_color(product: dict) -> Optional[str]:
    for name in ("Color", "Colour", "Men Color"):
        value = option_value(product, name)
        if value:
            return value

    for image in product.get("images") or []:
        src = image.get("src") or ""
        match = re.search(r"Color-([A-Za-z]+(?:-[A-Za-z]+)?)", src, re.I)
        if match:
            return match.group(1).replace("-", " ").upper()

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


def detect_category(title: str, tags: List[str], product_type: str, body: str) -> Optional[str]:
    blob = " ".join([title or "", " ".join(tags), product_type or "", body or ""]).lower()
    ptype = (product_type or "").lower()

    if "unstitched" in blob or "women fabric" in ptype or "fabric" == ptype:
        return "Unstitched"
    if "stitched" in blob and "unstitched" not in blob:
        return "Stitched"
    if ptype in {"women", "men", "salt", "kids"} and "fabric" not in blob:
        # apparel ready-made often has size options, not fabric type
        if any("size" in (o.get("name") or "").lower() for o in []):
            pass
    if re.search(r"\bstitched\b", blob) or "ready to wear" in blob:
        return "Stitched"
    if "women fabric" in ptype or "unstitched fabric" in blob or "gent unstitched" in blob:
        return "Unstitched"
    return None


def detect_department(tags: List[str], product_type: str, title: str) -> Optional[str]:
    tags_lower = {t.lower() for t in tags}
    ptype = (product_type or "").strip()
    title_l = (title or "").lower()
    blob = " ".join(list(tags_lower) + [ptype.lower(), title_l])

    if ptype == "Ideas Home" or any(
        x in blob for x in ["home", "comforter", "bedsheet", "towel", "cushion", "quilt", "pillow", "table linen"]
    ):
        if ptype == "Ideas Home" or any(
            x in blob
            for x in [
                "printed sheet",
                "fitted sheet",
                "comforter",
                "duvet",
                "cushion",
                "towel",
                "quilt",
                "pillow",
                "table linen",
                "bedding",
            ]
        ):
            return "Home"

    if ptype == "Accessories" or any(x in blob for x in ["bag", "scarf", "shawl", "stole"]):
        if "bag" in blob:
            return "Bags"
        return "Accessories"

    if ptype == "Kids" or "kids" in blob:
        return "Kids"

    if ptype == "Men" or any(x in blob for x in ["men suits", "men unstitched", "sale mens", "winter edit salt men"]):
        return "Men"

    if ptype in {"Women", "Women Fabric", "Salt"} or any(
        x in blob for x in ["women", "kurti", "dupatta", "women co-ords"]
    ):
        if ptype == "Salt" and "men" in blob:
            return "Men"
        if ptype == "Salt" and "kids" in blob:
            return "Kids"
        return "Women"

    if ptype == "Salt":
        return "Women"

    return None


def detect_subcategory(tags: List[str], product_type: str, title: str) -> Optional[str]:
    blob = " ".join([title or "", " ".join(tags), product_type or ""]).lower()
    rules = [
        ("Comforter Set", [r"\bcomforter\b"]),
        ("Printed Sheet Set", [r"\bprinted sheet\b", r"\bsheet set\b"]),
        ("Fitted Sheet", [r"\bfitted sheet\b"]),
        ("Quilt Cover", [r"\bquilt cover\b"]),
        ("Pillow Covers", [r"\bpillow cover\b"]),
        ("Cushion Covers", [r"\bcushion cover\b"]),
        ("Towel Set", [r"\btowel set\b", r"\btowel\b"]),
        ("Table Linen", [r"\btable linen\b", r"\btable mat\b", r"\brunner\b"]),
        ("Kurti", [r"\bkurti\b"]),
        ("Co-Ords", [r"\bco-?ords?\b"]),
        ("Dupatta", [r"\bdupatta\b"]),
        ("Men Suits", [r"\bmen suits?\b"]),
        ("Polo", [r"\bpolo\b"]),
        ("Tees", [r"\btees?\b"]),
        ("Trousers", [r"\btrousers?\b", r"\bpants\b"]),
    ]
    for label, patterns in rules:
        if any(re.search(p, blob, re.I) for p in patterns):
            return label
    return None


def detect_pieces(title: str, tags: List[str], body: str) -> Optional[str]:
    blob = " ".join([title or "", " ".join(tags), body or ""])
    for tag in tags:
        m = re.search(r"\b([123])\s*piece\b", tag, re.I)
        if m:
            return f"{m.group(1)} Piece"
    m = re.search(r"\b([123])\s*[- ]?\s*piece\b", blob, re.I)
    if m:
        return f"{m.group(1)} Piece"
    return None


def extract_size(product: dict) -> Optional[str]:
    for name in ("Women Sizes", "Men Sizes", "Home Sizes", "Kids Sizes", "Accessories Size", "Size"):
        value = option_value(product, name)
        if value:
            return value
    return None


def scrape_gulahmad(base_url: str = BASE_URL) -> dict:
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
            product_type = product.get("product_type")
            variant = (product.get("variants") or [{}])[0]
            images = product.get("images") or []
            handle = product.get("handle")

            # Refine category using product_type more reliably
            category = detect_category(title, tags, product_type, body)
            if product_type == "Women Fabric" or any("unstitched" in t.lower() for t in tags):
                category = "Unstitched"
            elif any("stitched" in t.lower() and "unstitched" not in t.lower() for t in tags):
                category = "Stitched"

            scraped_data.append(
                {
                    "title": title,
                    "color": extract_color(product),
                    "fabric": extract_fabric(product),
                    "price": variant.get("price"),
                    "compare_at_price": variant.get("compare_at_price"),
                    "image": images[0].get("src") if images else None,
                    "product_url": f"{base_url.rstrip('/')}/products/{handle}" if handle else None,
                    "department": detect_department(tags, product_type, title),
                    "subcategory": detect_subcategory(tags, product_type, title),
                    "category": category,
                    "product_type": product_type,
                    "pieces": detect_pieces(title, tags, body),
                    "size": extract_size(product),
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
        os.path.join(os.environ.get("TEMP", script_dir), OUTPUT_NAME),
    ]

    for path in candidates:
        if os.path.exists(path):
            try:
                os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            except Exception:
                pass
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4, ensure_ascii=False)
            print(f"Data successfully saved to {path}", flush=True)
            return path
        except Exception as err:
            print(f"Could not save to {path}: {err}", flush=True)

    print("ERROR: Could not save scraped data to any writable path.", flush=True)
    return None


if __name__ == "__main__":
    print("Starting GulAhmed FULL catalog scrape ...", flush=True)
    print(f"Source: {BASE_URL}/products.json", flush=True)
    result = scrape_gulahmad()
    print(f"Successfully scraped {len(result['data'])} products.", flush=True)
    save_json(result)
