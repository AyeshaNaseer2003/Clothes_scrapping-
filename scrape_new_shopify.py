"""Scrape newly added Shopify brands from the expanded brand list."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from shopify_common import scrape_shopify_catalog, save_json

BRANDS = [
    ("elan", "Elan", "https://elan.pk", "elan_products.json"),
    ("almirah", "Almirah", "https://www.almirah.com.pk", "almirah_products.json"),
    ("zeen", "Zeen", "https://zeenwoman.com", "zeen_products.json"),
    ("mushq", "Mushq", "https://mushq.com", "mushq_products.json"),
    ("zaha", "Zaha", "https://zaha.pk", "zaha_products.json"),
    ("afrozeh", "Afrozeh", "https://www.afrozeh.com", "afrozeh_products.json"),
    ("sania_maskatiya", "Sania Maskatiya", "https://www.saniamaskatiya.com", "sania_maskatiya_products.json"),
    ("amir_adnan", "Amir Adnan", "https://www.amiradnan.com", "amir_adnan_products.json"),
    ("edenrobe", "Edenrobe", "https://www.edenrobe.com", "edenrobe_products.json"),
    ("diners", "Diners", "https://www.diners.com.pk", "diners_products.json"),
    ("royal_tag", "Royal Tag", "https://www.royaltag.com.pk", "royal_tag_products.json"),
    ("breakout", "Breakout", "https://www.breakout.com.pk", "breakout_products.json"),
    ("so_kamal", "So Kamal", "https://www.sokamal.com", "so_kamal_products.json"),
]


def write_brand_script(folder, brand, base_url, output_name):
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

    print("\n\nFINAL SUMMARY NEW BRANDS", flush=True)
    for brand, count, out in summary:
        print(f"{brand:22} {count:6}  {out}", flush=True)


if __name__ == "__main__":
    main()
