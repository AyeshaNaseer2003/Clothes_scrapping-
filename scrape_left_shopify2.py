"""Second batch: left brands found on alternate Shopify domains."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from shopify_common import scrape_shopify_catalog, save_json

BRANDS = [
    ("charizma", "Charizma", "https://houseofcharizma.com", "charizma_products.json"),
    ("sobia_nazir", "Sobia Nazir", "https://sobianazir.net", "sobia_nazir_products.json"),
    ("farah_talib_aziz", "Farah Talib Aziz", "https://farahtalibaziz1.myshopify.com", "farah_talib_aziz_products.json"),
    ("mtj", "MTJ (Tariq Jamil)", "https://mtjonline.com", "mtj_products.json"),
    ("agha_noor", "Agha Noor", "https://pk.aghanoorofficial.com", "agha_noor_products.json"),
]


def write_brand_script(folder, brand, base_url, output_name):
    path = os.path.join(ROOT, folder, f"{folder}_test.py")
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
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    summary = []
    for folder, brand, base_url, output_name in BRANDS:
        write_brand_script(folder, brand, base_url, output_name)
        print("\n" + "=" * 70, flush=True)
        print(f"SCRAPING {brand}", flush=True)
        print("=" * 70, flush=True)
        result = scrape_shopify_catalog(base_url, brand)
        out = os.path.join(ROOT, folder, output_name)
        save_json(result, out)
        summary.append((brand, len(result["data"]), out))

    print("\n\nFINAL SUMMARY BATCH 2", flush=True)
    for brand, count, out in summary:
        print(f"{brand:22} {count:6}  {out}", flush=True)


if __name__ == "__main__":
    main()
