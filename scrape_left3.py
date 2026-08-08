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


if __name__ == "__main__":
    print(f"Starting {{BRAND}} FULL catalog scrape ...", flush=True)
    print(f"Source: {{BASE_URL}}/products.json", flush=True)
    result = scrape_shopify_catalog(BASE_URL, BRAND)
    print(f"Successfully scraped {{len(result['data'])}} products.", flush=True)
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
