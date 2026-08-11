import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from shopify_common import scrape_shopify_catalog, save_json

BASE_URL = "https://asimjofa.com"
OUTPUT_NAME = "asim_jofa_products.json"
BRAND = "Asim Jofa"


def report(result: dict) -> None:
    """Validate the new data structure and print coverage stats."""
    products = result.get("data") or []
    print(f"[{BRAND}] Total products: {len(products)}", flush=True)
    if not products:
        return
    with_images = sum(1 for p in products if p.get("images_list"))
    with_sizes = sum(1 for p in products if p.get("size_details"))
    with_color = sum(1 for p in products if p.get("color"))
    with_fabric = sum(1 for p in products if p.get("fabric"))
    print(f"[{BRAND}] products with images_list: {with_images}", flush=True)
    print(f"[{BRAND}] products with size_details: {with_sizes}", flush=True)
    print(f"[{BRAND}] products with color:        {with_color}", flush=True)
    print(f"[{BRAND}] products with fabric:       {with_fabric}", flush=True)
    sample = products[0]
    print(f"[{BRAND}] sample images count: {len(sample.get('images_list') or [])}", flush=True)
    print(f"[{BRAND}] sample size_details: {sample.get('size_details')}", flush=True)
    print(f"[{BRAND}] sample color: {sample.get('color')} | fabric: {sample.get('fabric')}", flush=True)


if __name__ == "__main__":
    print(f"Starting {BRAND} FULL catalog scrape ...", flush=True)
    print(f"Source: {BASE_URL}/products.json", flush=True)
    result = scrape_shopify_catalog(BASE_URL, BRAND)
    report(result)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), OUTPUT_NAME)
    save_json(result, out)
