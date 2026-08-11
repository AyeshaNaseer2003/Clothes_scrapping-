import os
import re
import json
import time
import random
import requests
from typing import Optional, List, Dict, Any

BASE_URL = "https://www.mariab.pk"
OUTPUT_NAME = "maria_b_products.json"

FABRIC_KEYWORDS = [
    "Lawn", "Cotton", "Chiffon", "Karandi", "Khaddar", "Cambric", "Linen",
    "Organza", "Silk", "Net", "Velvet", "Dobby", "Slub", "Swiss", "Voile",
    "Jacquard", "Tissue", "Georgette", "Sateen", "Mbroidered", "Viscose",
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

    if "unstitched" in blob or ptype.startswith("unstitched") or "loose fabrics" in ptype:
        return "Unstitched"
    if (
        "stitched" in blob
        or "ready to wear" in blob
        or "pret" in blob
        or "rtw" in blob
        or ptype.startswith("stitched")
        or "luxury pret" in ptype
        or "luxury formals" in ptype
        or "wedding wear" in ptype
        or "couture" in ptype
        or "menswear" in ptype
        or "kidswear" in ptype
        or "kidsclothes" in ptype
    ):
        return "Stitched"
    return None


def detect_department(tags: List[str], product_type: str, title: str) -> Optional[str]:
    tags_lower = {t.lower() for t in tags}
    ptype = (product_type or "").lower()
    title_l = (title or "").lower()
    blob = " ".join(list(tags_lower) + [ptype, title_l])

    if "jewelry" in ptype or "jewellery" in blob or "earrings" in blob:
        return "Jewellery"
    if "perfume" in ptype or "perfume" in blob:
        return "Fragrances"
    if "accessories" in ptype and "jewelry" not in blob:
        return "Accessories"
    if "kids" in ptype or "kidswear" in ptype or "kidsclothes" in ptype or "kids" in tags_lower:
        return "Kids"
    if "menswear" in ptype or "menswear" in blob or re.search(r"\bmen\b", blob):
        return "Men"
    if any(
        x in ptype
        for x in [
            "luxury pret",
            "luxury formals",
            "unstitched",
            "stitched",
            "wedding",
            "couture",
            "womensclothing",
            "loose fabrics",
        ]
    ) or "ready to wear" in blob:
        return "Women"
    if "payment link" in ptype:
        return None
    return "Women"


def detect_subcategory(tags: List[str], product_type: str, title: str) -> Optional[str]:
    ptype = product_type or ""
    if ptype and ptype.lower() not in {"payment link", "womensclothing"}:
        return ptype

    blob = " ".join([title or "", " ".join(tags)]).lower()
    rules = [
        ("Earrings", [r"\bearrings?\b"]),
        ("Luxury Pret", [r"\bluxury pret\b"]),
        ("Luxury Formals", [r"\bluxury formals?\b"]),
        ("Kids", [r"\bkids\b"]),
        ("Unstitched", [r"\bunstitched\b"]),
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
    m = re.search(r"\b([1234])\s*pc\b", blob, re.I)
    if m:
        return f"{m.group(1)} Piece"
    return None


def extract_size_details(product: dict) -> List[Dict[str, Any]]:
    """Build per-size availability from the variants array.

    Each entry is {"size": <name>, "available": bool}. Sizes declared in the
    Size option but missing from the variants (or with available=False) are
    included as unavailable so out-of-stock sizes are still visible.
    """
    variants = product.get("variants") or []
    options = product.get("options") or []
    invalid = {"", "default title", "default", "select", "one size", "onesize"}

    size_idx = -1
    declared_sizes: List[str] = []
    for idx, opt in enumerate(options):
        opt_name = (opt.get("name") or "").strip().lower()
        if opt_name and "size" in opt_name:
            size_idx = idx
            declared_sizes = [
                str(v).strip()
                for v in (opt.get("values") or [])
                if str(v).strip().lower() not in invalid
            ]
            break

    availability: Dict[str, bool] = {}
    if size_idx >= 0:
        for v in variants:
            opt_fields = [v.get("option1"), v.get("option2"), v.get("option3")]
            if size_idx < len(opt_fields) and opt_fields[size_idx]:
                size_name = str(opt_fields[size_idx]).strip()
                if size_name and size_name.lower() not in invalid:
                    if size_name not in availability:
                        availability[size_name] = False
                    if v.get("available"):
                        availability[size_name] = True
        for size_name in declared_sizes:
            availability.setdefault(size_name, False)
        return [
            {"size": size_name, "available": status}
            for size_name, status in availability.items()
        ]

    # No explicit size option: fall back to per-variant titles.
    titles: Dict[str, bool] = {}
    for v in variants:
        t = str((v.get("title") or "")).strip()
        if not t or t.lower() in invalid:
            t = "One Size"
        titles.setdefault(t, False)
        if v.get("available"):
            titles[t] = True
    return [{"size": t, "available": status} for t, status in titles.items()]


def any_variant_available(product: dict) -> bool:
    return any(bool(v.get("available")) for v in (product.get("variants") or []))


def scrape_mariab(base_url: str = BASE_URL) -> dict:
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
                    "color": option_value(product, "Color") or option_value(product, "Colour"),
                    "fabric": extract_fabric(product),
                    "price": variant.get("price"),
                    "compare_at_price": compare,
                    "images_list": [img.get("src") for img in images if img.get("src")],
                    "product_url": f"{base_url.rstrip('/')}/products/{handle}" if handle else None,
                    "department": detect_department(tags, product_type or "", title or ""),
                    "subcategory": detect_subcategory(tags, product_type or "", title or ""),
                    "category": detect_category(title or "", tags, product_type or ""),
                    "product_type": product_type,
                    "pieces": detect_pieces(title or "", tags, body),
                    "size_details": extract_size_details(product),
                    "sku": variant.get("sku"),
                    "available": any_variant_available(product),
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
    print("Starting Maria B FULL catalog scrape ...", flush=True)
    print(f"Source: {BASE_URL}/products.json", flush=True)
    result = scrape_mariab()
    print(f"Successfully scraped {len(result['data'])} products.", flush=True)
    save_json(result)
