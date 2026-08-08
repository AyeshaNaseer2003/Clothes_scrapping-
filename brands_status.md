# Brand scraping status
# Updated: 2026-08-07
# Status values: done | left

| Brand | Folder | Status | Products | Output file | Scraper / notes |
|-------|--------|--------|----------|-------------|-----------------|
| Khaadi | khaadi | done | 2512 | khaadi_products.json | khaadi_test.py (SFCC) |
| Gul Ahmed | gulahmad | done | 7110 | gulahmed_products.json | gulahmad.py |
| Sana Safinaz | sana_safinaz | done | 4852 | sana_safinaz_products.json | sana_safinaz_test.py |
| Sapphire | saphire | done | 3138 | saphire_products.json | saphire_test.py (SFCC) |
| Maria B | maria_b | done | 8246 | maria_b_products.json | maria_b_test.py |
| Junaid Jamshed | junaid_jamshed | done | 22580 | junaid_jamshed_products.json | junaid_jamshed_test.py |
| Alkaram Studio | alkaram | done | 1989 | alkaram_products.json | alkaram_scraping_module_api.py |
| Nishat Linen | nishat | done | 4575 | nishat_products.json | nishat_test.py |
| Bonanza Satrangi | bonanza_satrangi | done | 9555 | bonanza_satrangi_products.json | bonanza_satrangi_test.py |
| Limelight | limelight | done | 5841 | limelight_products.json | limelight_test.py |
| Generation | generation | done | 7121 | generation_products.json | generation_test.py |
| Ethnic | ethnic | left | — | — | Shopify store password-protected; `/products.json` returns empty |
| Outfitters | outfitters | done | 4363 | outfitters_products.json | outfitters_test.py |
| Bareeze | — | left | — | — | Custom JS storefront (not Shopify/public API); needs dedicated scraper |
| Zellbury | zellbury | done | 13999 | zellbury_products.json | zellbury_test.py |
| Beechtree | beechtree | done | 1308 | beechtree_products.json | beechtree_test.py |
| Cross Stitch | crossstitch | done | 2063 | shopify_products.json | crossstitch_test.py |
| Charizma | charizma | done | 1273 | charizma_products.json | charizma_test.py (`houseofcharizma.com`) |
| Asim Jofa | asim_jofa | done | 7150 | asim_jofa_products.json | asim_jofa_test.py |
| Baroque | baroque | done | 871 | baroque_products.json | baroque_test.py |
| Zara Shahjahan | zara_shahjahan | done | 943 | zara_shahjahan_products.json | zara_shahjahan_test.py |
| Sobia Nazir | sobia_nazir | done | 405 | sobia_nazir_products.json | sobia_nazir_test.py (`sobianazir.net`) |
| Zainab Chottani | zainab_chottani | done | 1106 | zainab_chottani_products.json | zainab_chottani_test.py |
| Faiza Saqlain | faiza_saqlain | done | 971 | faiza_saqlain_products.json | faiza_saqlain_test.py |
| Farah Talib Aziz | farah_talib_aziz | done | 2940 | farah_talib_aziz_products.json | farah_talib_aziz_test.py (`farahtalibaziz1.myshopify.com`) |
| Hussain Rehar | hussain_rehar | done | 2115 | hussain_rehar_products.json | hussain_rehar_test.py |
| MTJ (Tariq Jamil) | mtj | done | 5649 | mtj_products.json | mtj_test.py (`mtjonline.com`) |
| Agha Noor | agha_noor | done | 371 | agha_noor_products.json | agha_noor_test.py |
| Ansab Jahangir | — | left | — | — | Site returns 403 / Apparelverse (not public Shopify JSON) |
| Suffuse | suffuse | done | 545 | suffuse_products.json | suffuse_test.py |
| Kayseria | kayseria_test | done | 134 | kayseria_products.json | kayseria_test.py |

## Summary
- Done: 28
- Left: 3 (Ethnic, Bareeze, Ansab Jahangir)
- Total brands listed: 31
- New Shopify scrapes this run: ~87,000+ products across 18 brands

## Left (blocked / needs custom work)
1. **Ethnic** — password-protected Shopify; no public catalog JSON
2. **Bareeze** — custom Next.js/CDN storefront; no public products.json
3. **Ansab Jahangir** — storefront blocked (403) / Apparelverse; needs custom approach

## Shared tooling
- `shopify_common.py` — shared enriched Shopify scraper
- `scrape_left_shopify.py` / `scrape_left_shopify2.py` — batch runners
- Root `requirements.txt`

## Notes
- Cross Stitch latest file: `shopify_products.json` (2063).
- Farah Talib Aziz PK marketing site is separate; catalog scraped from Shopify myshopify domain.
- Re-run scrapers periodically to catch new / dropped / updated products.
