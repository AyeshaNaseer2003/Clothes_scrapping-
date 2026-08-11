"""Scrape remaining left brands: Ethnic (Ethnc PK) + Bareeze Man."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from shopify_common import scrape_shopify_catalog, save_json


def write_script(folder, brand, base_url, output_name):
    path = os.path.join(ROOT, folder, f"{folder}_test.py")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    content = f'''import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from shopify_common import scrape_shopify_catalog, save_json

BASE_URL = "{base_url}"
OUTPUT_NAME = "{output_name}"
BRAND = "{brand}"


def report(result: dict) -> None:
    """Validate the new data structure and print coverage stats."""
    products = result.get("data") or []
    print(f"[{{BRAND}}] Total products: {{len(products)}}", flush=True)
    if not products:
        return
    with_images = sum(1 for p in products if p.get("images_list"))
    with_sizes = sum(1 for p in products if p.get("size_details"))
    with_color = sum(1 for p in products if p.get("color"))
    with_fabric = sum(1 for p in products if p.get("fabric"))
    print(f"[{{BRAND}}] products with images_list: {{with_images}}", flush=True)
    print(f"[{{BRAND}}] products with size_details: {{with_sizes}}", flush=True)
    print(f"[{{BRAND}}] products with color:        {{with_color}}", flush=True)
    print(f"[{{BRAND}}] products with fabric:       {{with_fabric}}", flush=True)
    sample = products[0]
    print(f"[{{BRAND}}] sample images count: {{len(sample.get('images_list') or [])}}", flush=True)
    print(f"[{{BRAND}}] sample size_details: {{sample.get('size_details')}}", flush=True)
    print(f"[{{BRAND}}] sample color: {{sample.get('color')}} | fabric: {{sample.get('fabric')}}", flush=True)


if __name__ == "__main__":
    print(f"Starting {{BRAND}} FULL catalog scrape ...", flush=True)
    print(f"Source: {{BASE_URL}}/products.json", flush=True)
    result = scrape_shopify_catalog(BASE_URL, BRAND)
    report(result)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), OUTPUT_NAME)
    save_json(result, out)
'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    jobs = [
        ("ethnic", "Ethnic", "https://pk.ethnc.com", "ethnic_products.json"),
        ("bareeze", "Bareeze Man", "https://bareezeman.com", "bareeze_man_products.json"),
    ]
    for folder, brand, base, out_name in jobs:
        write_script(folder, brand, base, out_name)
        print("\n" + "=" * 70, flush=True)
        print(f"SCRAPING {brand}", flush=True)
        print("=" * 70, flush=True)
        result = scrape_shopify_catalog(base, brand)
        out = os.path.join(ROOT, folder, out_name)
        save_json(result, out)
        print(f"{brand}: {len(result['data'])} products", flush=True)


if __name__ == "__main__":
    main()
