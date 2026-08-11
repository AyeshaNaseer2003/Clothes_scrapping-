"""Scrape all left brands that expose Shopify /products.json."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from shopify_common import scrape_shopify_catalog, save_json

# folder_name, display name, base_url, output json
BRANDS = [
    ("junaid_jamshed", "Junaid Jamshed", "https://www.junaidjamshed.com", "junaid_jamshed_products.json"),
    ("bonanza_satrangi", "Bonanza Satrangi", "https://bonanzasatrangi.com", "bonanza_satrangi_products.json"),
    ("limelight", "Limelight", "https://www.limelight.pk", "limelight_products.json"),
    ("generation", "Generation", "https://www.generation.com.pk", "generation_products.json"),
    ("ethnic", "Ethnic", "https://www.ethnic.pk", "ethnic_products.json"),
    ("outfitters", "Outfitters", "https://outfitters.com.pk", "outfitters_products.json"),
    ("zellbury", "Zellbury", "https://www.zellbury.com", "zellbury_products.json"),
    ("asim_jofa", "Asim Jofa", "https://asimjofa.com", "asim_jofa_products.json"),
    ("baroque", "Baroque", "https://baroque.pk", "baroque_products.json"),
    ("zara_shahjahan", "Zara Shahjahan", "https://zarashahjahan.com", "zara_shahjahan_products.json"),
    ("zainab_chottani", "Zainab Chottani", "https://zainabchottani.com", "zainab_chottani_products.json"),
    ("faiza_saqlain", "Faiza Saqlain", "https://faizasaqlain.pk", "faiza_saqlain_products.json"),
    ("hussain_rehar", "Hussain Rehar", "https://hussainrehar.com", "hussain_rehar_products.json"),
    ("suffuse", "Suffuse", "https://suffuse.pk", "suffuse_products.json"),
]


def write_brand_script(folder: str, brand: str, base_url: str, output_name: str) -> None:
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
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main(only=None):
    summary = []
    for folder, brand, base_url, output_name in BRANDS:
        if only and only not in {folder, brand.lower().replace(" ", "_")}:
            continue
        write_brand_script(folder, brand, base_url, output_name)
        print("\n" + "=" * 70, flush=True)
        print(f"SCRAPING {brand}", flush=True)
        print("=" * 70, flush=True)
        result = scrape_shopify_catalog(base_url, brand)
        out = os.path.join(ROOT, folder, output_name)
        save_json(result, out)
        summary.append((brand, len(result["data"]), out))

    print("\n\nFINAL SUMMARY", flush=True)
    for brand, count, out in summary:
        print(f"{brand:22} {count:6}  {out}", flush=True)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(arg)
