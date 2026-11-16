#!/usr/bin/env python3
"""Extract country rows from Open Food Facts' official food Parquet snapshot."""
import argparse
import csv
import json
import re
from pathlib import Path

from build_country_market_packs import COUNTRIES, NAMES, nutrients, v

NUTRIENTS = ("energy-kcal", "energy-kj", "proteins", "carbohydrates", "fat", "sugars", "fiber")
COLUMNS = (
    "code", "countries_tags", "product_name", "product_name_en", "brands",
    "serving_quantity", "nutrition_data_per", "scans_n", "completeness",
    *(f"{key}_100g" for key in NUTRIENTS),
)


def export_row(product, language):
    barcode, tags, names, lang, brands, serving, serving_label, scans, completeness, values = product
    names = {name["lang"]: name["text"] for name in names or () if name["text"]}
    row = {
        "code": barcode,
        "countries_tags": ",".join(tags),
        "product_name": names.get(language) or names.get(lang) or names.get("main") or names.get("en"),
        f"product_name_{language}": names.get(language),
        "product_name_en": names.get("en"),
        "brands": brands,
        "nutrition_data_per": "100g",
        "scans_n": scans,
        "completeness": completeness,
    }
    # Legacy OFF's "100g" slot can also mean 100 ml. The query only
    # accepts explicit 100g baselines. Keep servings with an explicit gram unit.
    gram_amounts = re.findall(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*g\b", serving_label or "", re.IGNORECASE)
    other_units = re.search(r"\b(?:ml|cl|dl|l|kg|mg)\b", serving_label or "", re.IGNORECASE)
    if len(gram_amounts) == 1 and not other_units and v(gram_amounts[0]) == v(serving):
        row["serving_quantity"] = serving
    for value in values or ():
        if value["name"] in NUTRIENTS:
            row[f'{value["name"]}_100g'] = value["100g"]
    if row["product_name"] and nutrients(row)[0] is not None:
        return row


def export(source, country, output):
    import duckdb

    tag = "en:" + NAMES[country][0]
    language = COUNTRIES[country]["local"]
    count = 0
    partial = output.with_suffix(".partial")
    try:
        with duckdb.connect(config={"threads": "2", "memory_limit": "2GB"}) as db:
            products = db.execute(
                """
                SELECT code, countries_tags, product_name, lang, brands,
                       serving_quantity, serving_size, scans_n, completeness, nutriments
                FROM read_parquet(?)
                WHERE list_contains(countries_tags, ?)
                  AND nutrition_data_per = '100g'
                  AND obsolete IS DISTINCT FROM TRUE
                  AND no_nutrition_data IS DISTINCT FROM TRUE
                """,
                [str(source), tag],
            )
            with partial.open("w", encoding="utf-8", newline="") as file:
                columns = (*COLUMNS, f"product_name_{language}")
                writer = csv.DictWriter(file, fieldnames=columns)
                writer.writeheader()
                while batch := products.fetchmany(4096):
                    for product in batch:
                        row = export_row(product, language)
                        if row:
                            writer.writerow(row)
                            count += 1
        if count < COUNTRIES[country]["required"]:
            raise RuntimeError(f"Only {count} eligible products in OFF snapshot for {country}")
        partial.replace(output)
    finally:
        partial.unlink(missing_ok=True)
    print(json.dumps({"source": str(source), "country": country, "eligible_rows": count}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--country", choices=sorted(COUNTRIES), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.snapshot, args.country, args.output)
