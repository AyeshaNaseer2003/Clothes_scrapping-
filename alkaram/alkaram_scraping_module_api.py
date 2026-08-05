import os
import re
import json
import requests
import time
import random
from typing import Optional, List
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
            if values and values[0] != "Default Title":
                return values[0]
    return None


def detect_category(title: str, tags: List[str], body: str) -> Optional[str]:
    """Stitched vs Unstitched (RTS / RTW)."""
    blob = " ".join([title or "", " ".join(tags), body or ""]).lower()
    title_upper = (title or "").upper()

    if "unstitched" in blob or re.search(r"\brts\b", title_upper) or "ready to stitch" in blob:
        return "Unstitched"
    if "ready to wear" in blob or re.search(r"\brtw\b", title_upper) or re.search(r"\bpret\b", blob):
        return "Stitched"
    return None


def detect_department(title: str, tags: List[str], product_type: str) -> Optional[str]:
    """Top nav style section: Women, Men, Home, Bags, Fragrances, Kids."""
    tags_lower = {t.lower() for t in tags}
    ptype = (product_type or "").upper()
    title_l = (title or "").lower()
    blob = " ".join([title_l, " ".join(tags_lower), ptype.lower()])

    if any(t in tags_lower for t in {"bags", "handbags", "hand bags"}) or any(
        x in ptype for x in ["BAG", "TOTE", "CROSS BODY", "SHOULDER"]
    ):
        return "Bags"

    if any(t in tags_lower for t in {"fragrance", "fragrances"}) or "FRAGRANCE" in ptype:
        return "Fragrances"

    if any(t in tags_lower for t in {"home", "bathroom", "bedroom home", "bath linen"}) or any(
        x in ptype
        for x in [
            "BEDSHEET",
            "DUVET",
            "TOWEL",
            "CUSHION",
            "COVER",
            "TABLE MAT",
            "TABLE RUNNER",
            "FILLING",
            "FITTED SHEET",
        ]
    ) or any(x in blob for x in ["table mat", "table runner", "bath towel", "hand towel", "duvet"]):
        return "Home"

    if any(t in tags_lower for t in {"kids", "kid", "children"}):
        return "Kids"

    has_women = any(
        t in {"woman", "women"} or t.startswith("women-") or t.startswith("woman-")
        for t in tags_lower
    )
    has_men = any(
        t in {"man", "men"} or t.startswith("men-") or t.startswith("man-")
        for t in tags_lower
    )

    if has_women and not has_men:
        return "Women"
    if has_men and not has_women:
        return "Men"
    if has_women and has_men:
        return "Women"

    return None


def detect_subcategory(title: str, tags: List[str], product_type: str) -> Optional[str]:
    """Finer HOME / BAGS labels from nav (mats, towels, bedsheets, etc.)."""
    ptype = (product_type or "").upper()
    tags_l = " ".join(tags).lower()
    title_l = (title or "").lower()
    blob = f"{title_l} {tags_l} {ptype.lower()}"

    rules = [
        ("Duvet Cover Set", [r"\bduvet\b"]),
        ("Basic Bedsheet Set", [r"\bbasic bedsheet\b", r"\bbedsheet\b", r"\bbed sheet\b"]),
        ("Fitted Sheet", [r"\bfitted sheet\b"]),
        ("Fillings", [r"\bfilling\b", r"\bfillings\b"]),
        ("Cushion Covers", [r"\bcushion\b"]),
        ("Table Mats", [r"\btable mat\b", r"\bplacemat\b", r"\btable mats\b"]),
        ("Table Runners", [r"\btable runner\b", r"\brunners?\b"]),
        ("Bath Towel", [r"\bbath towel\b"]),
        ("Hand Towel", [r"\bhand towel\b"]),
        ("Shoulder Bag", [r"\bshoulder bag\b"]),
        ("Tote Bag", [r"\btote bag\b", r"\btote\b"]),
        ("Cross Body", [r"\bcross body\b", r"\bcrossbody\b"]),
    ]

    for label, patterns in rules:
        if any(re.search(p, blob, re.I) for p in patterns):
            return label

    # Fall back to product_type for home/bag items
    if any(x in ptype for x in ["BAG", "TOWEL", "BEDSHEET", "DUVET", "CUSHION", "MAT", "RUNNER", "COVER"]):
        return product_type.title() if product_type else None

    return None


def detect_pieces(title: str, tags: List[str], product_type: str, body: str) -> Optional[str]:
    blob = " ".join([title or "", " ".join(tags), product_type or "", body or ""])

    for tag in tags:
        m = re.search(r"\b([123])\s*piece\b", tag, re.I)
        if m:
            return f"{m.group(1)} Piece"
        m = re.search(r"\b([123])\s*pc\b", tag, re.I)
        if m:
            return f"{m.group(1)} Piece"

    m = re.search(r"\b([123])\s*[- ]?\s*piece\b", blob, re.I)
    if m:
        return f"{m.group(1)} Piece"

    m = re.search(r"\b([123])\s*pc\b", blob, re.I)
    if m:
        return f"{m.group(1)} Piece"

    ptype = (product_type or "").upper()
    parts = [p.strip() for p in re.split(r"[,&]| AND ", ptype) if p.strip()]
    if len(parts) >= 2:
        return f"{len(parts)} Piece"

    return None


@app.get("/scrape-alkaram")
@app.get("/scrpe-alkaram")
def Alkaram_scraping_Module(base_url: Optional[str] = None):
    if not base_url:
        base_url = "https://www.alkaramstudio.com"

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
            product_url = (
                f"{base_url.rstrip('/')}/products/{handle}" if handle else None
            )

            item = {
                "title": title,
                "color": option_value(product, "Color") or option_value(product, "Colour"),
                "fabric": option_value(product, "Fabric"),
                "price": variant.get("price"),
                "compare_at_price": variant.get("compare_at_price"),
                "image": images[0].get("src") if images else None,
                "product_url": product_url,
                "department": detect_department(title, tags, product_type),
                "subcategory": detect_subcategory(title, tags, product_type),
                "category": detect_category(title, tags, body),
                "product_type": product_type,
                "pieces": detect_pieces(title, tags, product_type, body),
                "size": option_value(product, "Size"),
                "fit": option_value(product, "Fit"),
                "sku": variant.get("sku"),
                "available": variant.get("available"),
            }
            scraped_data.append(item)

        page += 1
        time.sleep(random.uniform(1.0, 2.0))

    return {"data": scraped_data}


if __name__ == "__main__":
    print("Starting direct scraping of Alkaram Studio...")
    result = Alkaram_scraping_Module()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(r"D:\My work\alkaram", "alkaram_products.json"),
        os.path.join(script_dir, "alkaram_products.json"),
        os.path.join(os.path.expanduser("~"), "alkaram_products.json"),
        os.path.join(os.environ.get("TEMP", "."), "alkaram_products.json"),
    ]

    saved = None
    for output_filename in candidates:
        folder = os.path.dirname(output_filename)
        if folder and not os.path.isdir(folder):
            continue
        try:
            with open(output_filename, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=4, ensure_ascii=False)
            saved = output_filename
            print(f"Successfully scraped {len(result['data'])} products.")
            print(f"Data saved to {output_filename}")
            break
        except Exception as err:
            print(f"Could not save to {output_filename}: {err}")

    if not saved:
        print("ERROR: Could not save alkaram_products.json anywhere.")
