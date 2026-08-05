import os
import re
import stat
import json
import time
import random
import requests
from typing import Optional, List

BASE_URL = "https://www.kayseria.com.pk"
OUTPUT_NAME = "kayseria_products.json"

FABRIC_KEYWORDS = [
    "Marina", "Mareena", "Lawn", "Cotton", "Chiffon", "Karandi", "Khaddar",
    "Cambric", "Linen", "Organza", "Silk", "Net", "Velvet", "Dobby", "Slub",
    "Swiss", "Voile", "Jacquard", "Tissue", "Georgette", "Wool", "Viscose",
]


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


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
    value = option_value(product, "Color") or option_value(product, "Colour")
    if value:
        return value

    body = clean_html(product.get("body_html") or "")
    match = re.search(
        r"Colou?r:\s*([A-Za-z][A-Za-z ]*?)(?=\s*(?:Fabric|Dupatta|Trouser|Shirt|Includes|Detail|$))",
        body,
        re.I,
    )
    if match:
        value = match.group(1).strip(" -").upper()
        if value and value.lower() not in {"fabric"}:
            return value

    return None


def extract_fabric(product: dict) -> Optional[str]:
    value = option_value(product, "Fabric")
    if value:
        return value

    body = clean_html(product.get("body_html") or "")
    match = re.search(
        r"Fabric:\s*([A-Za-z][A-Za-z ]*?)(?=\s*(?:Dupatta|Trouser|Shirt|Colou?r|Includes|Detail|Fabric|$))",
        body,
        re.I,
    )
    if match:
        return match.group(1).strip(" -").upper()

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


def detect_category(title: str, body: str, product_type: str) -> Optional[str]:
    blob = " ".join([title or "", body or "", product_type or ""]).lower()
    if "unstitched" in blob:
        return "Unstitched"
    if "ready to wear" in blob or re.search(r"\bstitched\b", blob):
        return "Stitched"
    # Fabric suits with meterage details are typically unstitched
    if re.search(r"\b(shirt detail|dupatta detail|trouser detail)\b", blob) and re.search(
        r"\bmeters?\b|\bmtrs?\b", blob
    ):
        return "Unstitched"
    if option_value({"options": []}, "Size"):
        return "Stitched"
    return None


def detect_pieces(title: str, body: str) -> Optional[str]:
    blob = " ".join([title or "", body or ""])
    m = re.search(r"\b([123])\s*[- ]?\s*piece\b", blob, re.I)
    if m:
        return f"{m.group(1)} Piece"

    has_shirt = bool(re.search(r"\bshirt detail\b", blob, re.I))
    has_dupatta = bool(re.search(r"\bdupatta detail\b", blob, re.I))
    has_trouser = bool(re.search(r"\btrouser detail\b", blob, re.I))
    count = sum([has_shirt, has_dupatta, has_trouser])
    if count >= 2:
        return f"{count} Piece"
    return None


def detect_department(product_type: str, title: str, body: str) -> Optional[str]:
    blob = " ".join([product_type or "", title or "", body or ""]).lower()
    if any(x in blob for x in ["men", "gents", "gent "]):
        return "Men"
    if any(x in blob for x in ["kids", "child"]):
        return "Kids"
    if any(x in blob for x in ["home", "bedsheet", "towel"]):
        return "Home"
    # Kayseria catalog is primarily women's apparel
    return "Women"


def scrape_kayseria(base_url: str = BASE_URL) -> dict:
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
            response = requests.get(url, headers=headers, timeout=30)
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
            body = product.get("body_html") or ""
            product_type = product.get("product_type") or None
            variant = (product.get("variants") or [{}])[0]
            images = product.get("images") or []
            handle = product.get("handle")
            size = option_value(product, "Size")

            category = detect_category(title, body, product_type or "")
            if size and not category:
                category = "Stitched"
            elif not category and re.search(r"shirt detail|dupatta detail|trouser detail", body or "", re.I):
                category = "Unstitched"

            scraped_data.append(
                {
                    "title": title,
                    "color": extract_color(product),
                    "fabric": extract_fabric(product),
                    "price": variant.get("price"),
                    "compare_at_price": variant.get("compare_at_price"),
                    "image": images[0].get("src") if images else None,
                    "product_url": f"{base_url.rstrip('/')}/products/{handle}" if handle else None,
                    "department": detect_department(product_type or "", title or "", body),
                    "category": category,
                    "product_type": product_type,
                    "pieces": detect_pieces(title or "", body),
                    "size": size,
                    "sku": variant.get("sku"),
                    "available": variant.get("available"),
                }
            )

        page += 1
        time.sleep(random.uniform(1.0, 2.0))

    return {"data": scraped_data}


def save_json(payload: dict) -> Optional[str]:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, OUTPUT_NAME)

    if os.path.exists(output_file):
        try:
            os.chmod(output_file, stat.S_IWRITE | stat.S_IREAD)
        except Exception:
            pass

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4, ensure_ascii=False)

    print(f"Data successfully saved to {output_file}", flush=True)
    return output_file


if __name__ == "__main__":
    print("Starting Kayseria FULL catalog scrape ...", flush=True)
    print(f"Source: {BASE_URL}/products.json", flush=True)
    result = scrape_kayseria()
    print(f"Successfully scraped {len(result['data'])} products.", flush=True)
    save_json(result)
