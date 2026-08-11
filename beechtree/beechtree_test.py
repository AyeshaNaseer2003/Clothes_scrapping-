import os
import re
import json
import requests
import time
import random
from typing import Optional, List, Dict, Any
from fastapi import FastAPI

app = FastAPI()


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


def detect_category(title: str, tags: List[str], product_type: str, body: str) -> Optional[str]:
    blob = " ".join([title or "", " ".join(tags), product_type or "", body or ""]).lower()
    ptype = (product_type or "").upper()

    if "unstitched" in blob or "UNSTITCHED" in ptype or re.search(r"\bunstitched\b", title or "", re.I):
        return "Unstitched"
    if "pret" in blob or ptype in {"PRET", "LUXURY PRET", "LUXURY-PRET", "PRET LOWERS", "PRET-LOWER", "HIGH CASUAL", "FUSION", "WESTERN", "FLOW"}:
        return "Stitched"
    return None


def detect_department(tags: List[str], product_type: str) -> Optional[str]:
    tags_lower = {t.lower() for t in tags}
    ptype = (product_type or "").upper()

    if any(t in tags_lower for t in {"kids", "child", "children"}) or ptype.startswith("BTK"):
        return "Kids"
    if any(t in tags_lower for t in {"perfume", "perfumes"}) or "PERFUME" in ptype:
        return "Fragrances"
    if any(t in tags_lower for t in {"jewellery", "jewelry"}) or "JEWELLERY" in ptype:
        return "Jewellery"
    if "SCARF" in ptype or "SCARVES" in ptype:
        return "Accessories"
    if any(t in tags_lower for t in {"women", "woman", "bew-in", "ba-pret", "r-pret", "r-unstitched"}):
        return "Women"
    # Beechtree is primarily womenswear
    if ptype and ptype not in {"OTHER-ACC"}:
        return "Women"
    return None


def detect_pieces(title: str, tags: List[str], product_type: str, size_opt: Optional[str], body: str) -> Optional[str]:
    if size_opt:
        m = re.search(r"\b([123])\s*p(?:c|iece)?s?\b", size_opt, re.I)
        if m:
            return f"{m.group(1)} Piece"

    blob = " ".join([title or "", " ".join(tags), product_type or "", body or ""])
    m = re.search(r"\b([123])\s*[- ]?\s*piece\b", blob, re.I)
    if m:
        return f"{m.group(1)} Piece"
    m = re.search(r"\b([123])\s*p(?:c|iece)?s?\b", blob, re.I)
    if m:
        return f"{m.group(1)} Piece"
    return None


@app.get("/scrape-beechtree")
@app.get("/scrpe-beechtree")
def extract_size_details(product: dict) -> List[Dict[str, Any]]:
    """Build per-size availability from the variants array.

    Each entry is {"size": <name>, "available": bool}. Sizes declared in the
    Size option but missing from the variants (or with available=False) are
    included as unavailable so out-of-stock sizes are still visible.
    """
    variants = product.get("variants") or []
    options = product.get("options") or []
    invalid = {"", "default title", "default", "select", "one size"}

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


def Beechtree_scraping_Module(base_url: Optional[str] = None):
    if not base_url:
        base_url = "https://beechtree.pk"

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
        print(f"Fetching URL: {url}")

        try:
            response = requests.get(url, headers=headers, timeout=30)
        except Exception as e:
            print(f"Request error: {e}")
            break

        if response.status_code != 200:
            print(f"Blocked or failed with status code {response.status_code}")
            break

        try:
            json_response = response.json()
        except Exception as e:
            print(f"Failed to parse JSON response: {e}")
            break

        products = json_response.get("products")
        if not products:
            print("No more products found.")
            break

        print(f"Page {page}: Scraped {len(products)} products")

        for product in products:
            title = product.get("title")
            tags = normalize_tags(product.get("tags"))
            body = product.get("body_html") or ""
            product_type = product.get("product_type")
            variant = (product.get("variants") or [{}])[0]
            images = product.get("images") or []
            handle = product.get("handle")
            size_opt = option_value(product, "Size")

            item = {
                "title": title,
                "color": option_value(product, "Color") or option_value(product, "Colour"),
                "fabric": option_value(product, "Fabric"),
                "price": variant.get("price"),
                "compare_at_price": variant.get("compare_at_price"),
                "images_list": [img.get("src") for img in images if img.get("src")],
                "product_url": f"{base_url.rstrip('/')}/products/{handle}" if handle else None,
                "department": detect_department(tags, product_type),
                "category": detect_category(title, tags, product_type, body),
                "product_type": product_type,
                "pieces": detect_pieces(title, tags, product_type, size_opt, body),
                "size_details": extract_size_details(product),
                "sku": variant.get("sku"),
                "available": any_variant_available(product),
            }
            scraped_data.append(item)

        page += 1
        time.sleep(random.uniform(1.0, 2.0))

    return {"data": scraped_data}


if __name__ == "__main__":
    print("Starting direct scraping of BeechTree...")
    result = Beechtree_scraping_Module()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_filename = os.path.join(script_dir, "beechtree_products.json")
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)

    print(f"Successfully scraped {len(result['data'])} products.")
    print(f"Data saved to {output_filename}")
