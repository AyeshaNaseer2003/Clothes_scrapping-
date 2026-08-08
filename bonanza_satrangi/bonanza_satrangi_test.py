import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from shopify_common import scrape_shopify_catalog, save_json

BASE_URL = "https://bonanzasatrangi.com"
OUTPUT_NAME = "bonanza_satrangi_products.json"
BRAND = "Bonanza Satrangi"


if __name__ == "__main__":
    print(f"Starting {BRAND} FULL catalog scrape ...", flush=True)
    print(f"Source: {BASE_URL}/products.json", flush=True)
    result = scrape_shopify_catalog(BASE_URL, BRAND)
    print(f"Successfully scraped {len(result['data'])} products.", flush=True)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), OUTPUT_NAME)
    save_json(result, out)
