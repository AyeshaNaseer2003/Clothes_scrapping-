import os
import re
import json
import time
import random
import requests
from typing import Optional, List

BASE_URL = "https://nishatlinen.com"
OUTPUT_NAME = "nishat_products.json"

FABRIC_KEYWORDS = [
    "Lawn", "Cotton", "Chiffon", "Karandi", "Khaddar", "Cambric", "Linen",
    "Organza", "Silk", "Net", "Velvet", "Dobby", "Slub", "Swiss", "Voile",
    "Jacquard", "Tissue", "Georgette", "Sateen", "Viscose", "Latha",
    "Signature Cotton", "Boski", "Wash & Wear", "Wash and Wear",
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
            value = re.sub(r"\s+", " ", value)
            if value and value.lower() not in {"n/a", "-", "none"}:
                return value
    return None


def extract_fabric(product: dict) -> Optional[str]:
    value = option_value(product, "Fabric")
    if value:
        return value

    body = product.get("body_html") or ""
    value = body_field(body, "Fabric")
    if value:
        return value.upper() if len(value) <= 40 else value

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

    if (
        "unstitched" in blob
        or "ready to stitch" in blob
        or re.search(r"\brts\b", blob)
        or ptype in {"pack suit", "meter"}
        or "fabric by meter" in blob
    ):
        return "Unstitched"
    if (
        "ready to wear" in blob
        or "stitched" in blob
        or re.search(r"\brtw\b", blob)
        or re.search(r"\bpret\b", blob)
        or ptype == "ready to wear"
    ):
        return "Stitched"
    return None


def detect_department(tags: List[str], product_type: str, title: str) -> Optional[str]:
    tags_lower = {t.lower() for t in tags}
    ptype = (product_type or "").lower()
    title_l = (title or "").lower()
    blob = " ".join(list(tags_lower) + [ptype, title_l])

    if any(
        t in tags_lower
        for t in {"bags", "hand bags", "handbags", "tote-bags", "shoulder bags", "phone bags", "vanity bags"}
    ) or "bag" in title_l:
        return "Bags"

    if "scarf" in blob or "dupatta" in ptype:
        return "Accessories"

    if any(t in tags_lower for t in {"kids", "kid", "children"}):
        return "Kids"

    has_women = any(
        t in {"woman", "women"} or t.startswith("women") or t.startswith("woman")
        for t in tags_lower
    )
    has_men = any(
        t in {"man", "men"} or t.startswith("men") or t.startswith("man-") or t.startswith("men-")
        for t in tags_lower
    )

    # Prefer explicit gender tags; "women scarf" etc. already handled above.
    if has_men and not has_women:
        return "Men"
    if has_women and not has_men:
        return "Women"
    if has_men and has_women:
        # Prefer men when men-* collection tags dominate product intent.
        if any(t.startswith("men") for t in tags_lower):
            return "Men"
        return "Women"

    if ptype in {"ready to wear", "pack suit", "meter"}:
        return "Women"
    if ptype == "fashion":
        return "Accessories"
    return None


def detect_subcategory(tags: List[str], product_type: str, title: str) -> Optional[str]:
    ptype = product_type or ""
    tags_l = " ".join(tags).lower()
    title_l = (title or "").lower()
    blob = f"{title_l} {tags_l} {ptype.lower()}"

    rules = [
        ("Hand Bags", [r"\bhand bags?\b", r"\bhandbags?\b"]),
        ("Tote Bags", [r"\btote[- ]?bags?\b"]),
        ("Shoulder Bags", [r"\bshoulder bags?\b"]),
        ("Vanity Bags", [r"\bvanity bags?\b"]),
        ("Phone Bags", [r"\bphone bags?\b"]),
        ("Scarf", [r"\bscarf\b", r"\bscarves\b"]),
        ("Fabric by Meter", [r"\bfabric by meter\b", r"\bmeter\b"]),
        ("Pack Suit", [r"\bpack suit\b"]),
        ("Ready to Wear", [r"\bready to wear\b", r"\brtw\b", r"\bpret\b"]),
        ("Unstitched", [r"\bunstitched\b", r"\brts\b"]),
    ]
    for label, patterns in rules:
        if any(re.search(p, blob, re.I) for p in patterns):
            return label

    return ptype or None


def detect_pieces(title: str, tags: List[str], body: str) -> Optional[str]:
    blob = " ".join([title or "", " ".join(tags), body or ""])
    m = re.search(r"\b([1234])\s*[- ]?\s*piece\b", blob, re.I)
    if m:
        return f"{m.group(1)} Piece"
    m = re.search(r"\b([1234])\s*pc\b", blob, re.I)
    if m:
        return f"{m.group(1)} Piece"
    return None


def scrape_nishat(base_url: str = BASE_URL) -> dict:
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
            variant = (product.get("variants") or [{}])[0]
            images = product.get("images") or []
            handle = product.get("handle")
            compare = variant.get("compare_at_price")
            if compare in {"0.00", "0", 0}:
                compare = None

            scraped_data.append(
                {
                    "title": title,
                    "color": extract_color(product),
                    "fabric": extract_fabric(product),
                    "price": variant.get("price"),
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
    print("Starting Nishat Linen FULL catalog scrape ...", flush=True)
    print(f"Source: {BASE_URL}/products.json", flush=True)
    result = scrape_nishat()
    print(f"Successfully scraped {len(result['data'])} products.", flush=True)
    save_json(result)
