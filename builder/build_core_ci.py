#!/usr/bin/env python3
"""Build a verifiable International Core for Down the Hill from official USDA JSON.
Never synthesizes nutrition data. Translates NAME LABELS ONLY using an Apache-2 model.
"""
import argparse, hashlib, json, math, re, sqlite3, struct, sys, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_pack import insert_records, check, quality

DATASETS = [
    ("sr", "SRLegacyFoods", "USDA-SRLegacy"),
    ("foundation", "FoundationFoods", "USDA-Foundation"),
    ("fndds", "SurveyFoods", "USDA-FNDDS"),
]
NUTRIENTS = {
    "kcal": (1008, 2047, 2048),
    "protein": (1003,), "carbs": (1005,), "fat": (1004,),
    "sugar": (2000,), "fiber": (1079,),
}
HEBREW = re.compile(r"[\u0590-\u05ff]")
MAGIC = b"DTHPK1\n"
ALIAS = {
    "apple, raw": "תפוח עץ טרי",
    "banana, raw": "בננה טרייה",
    "egg, whole, raw": "ביצה שלמה טרייה",
    "chicken, broilers or fryers, breast, meat only, raw": "חזה עוף טרי",
    "rice, white, long-grain, regular, cooked": "אורז לבן מבושל",
}

def load_foods(path, key):
    with zipfile.ZipFile(path) as archive:
        choices = [n for n in archive.namelist()
                   if n.lower().endswith(".json") and not n.startswith("__MACOSX")]
        if len(choices) != 1:
            raise ValueError(f"{path}: expected exactly one USDA JSON, got {choices}")
        with archive.open(choices[0]) as stream:
            data = json.load(stream)
    if not isinstance(data, dict) or not isinstance(data.get(key), list):
        raise ValueError(f"{path}: missing USDA collection {key}")
    return data[key]

def num(value):
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None

def nutrients(food):
    values = {}
    for item in food.get("foodNutrients", []):
        nutrient = item.get("nutrient") or {}
        raw = nutrient.get("id") or item.get("nutrientId")
        if raw is None:
            raw = {"208": 1008, "203": 1003, "205": 1005,
                   "204": 1004, "269": 2000, "291": 1079}.get(str(nutrient.get("number", "")))
        try:
            ident = int(raw)
        except (TypeError, ValueError):
            continue
        value = num(item.get("amount") if item.get("amount") is not None else item.get("value"))
        if value is not None:
            values[ident] = value
    return {kind: next((values[i] for i in ids if i in values), None)
            for kind, ids in NUTRIENTS.items()}

def translate_names(names, batch_size=16):
    from transformers import pipeline
    translator = pipeline("translation", model="Helsinki-NLP/opus-mt-en-he", device=-1)
    result = {}
    unique = sorted(set(names))
    for pos in range(0, len(unique), batch_size):
        batch = unique[pos:pos + batch_size]
        translated = translator(batch, max_length=160, batch_size=batch_size, truncation=True)
        for name, item in zip(batch, translated):
            text = item["translation_text"].strip()
            if HEBREW.search(text) and len(text) <= 180:
                result[name] = text
        if pos % 320 == 0:
            print("Translation progress", pos, "/", len(unique), flush=True)
    for original, he in ALIAS.items():
        for label in unique:
            if original == label.casefold():
                result[label] = he
    return result

def main():
    parser = argparse.ArgumentParser()
    for name, _, _ in DATASETS:
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    seen, rows, counts = set(), [], {}
    archives = {}
    for arg, collection, source in DATASETS:
        archive = Path(getattr(args, arg))
        archives[source] = hashlib.sha256(archive.read_bytes()).hexdigest()
        foods = load_foods(archive, collection)
        count = 0
        for food in foods:
            code = food.get("fdcId") or food.get("fdc_id")
            desc = food.get("description")
            if code is None or not isinstance(desc, str) or not desc.strip():
                continue
            ident = "usda:" + str(code)
            if ident in seen:
                continue
            n = nutrients(food)
            if not check(n):
                continue
            seen.add(ident)
            serving = None
            for portion in food.get("foodPortions", []):
                grams = num(portion.get("gramWeight"))
                if grams is not None and 0 < grams <= 2000:
                    serving = grams
                    break
            rows.append({
                "id": ident, "source": source, "source_id": str(code), "de": "",
                "en": desc.strip(), "he": "", "brand": None, "barcode": None,
                "n": n, "search": desc.strip(), "flags": quality(n),
                "url": f"https://fdc.nal.usda.gov/food-details/{code}/nutrients",
                "serving": serving,
            })
            count += 1
        counts[source] = count
        print(source, "accepted", count, flush=True)
        if count == 0:
            raise ValueError("No valid rows from " + source)
    if len(rows) < 10000:
        raise ValueError(f"Only {len(rows)} real USDA records; expected 10000+")
    db_path = out / "core.sqlite"
    if db_path.exists():
        db_path.unlink()
    insert_records(db_path, iter(rows))
    db = sqlite3.connect(db_path)
    try:
        before = db.execute("SELECT COUNT(*), SUM(kcal_100), SUM(protein_100), SUM(carbs_100), SUM(fat_100) FROM foods").fetchone()
        translations = translate_names([r["en"] for r in rows])
        translated = 0
        for rec in rows:
            he = translations.get(rec["en"])
            if he:
                db.execute("UPDATE foods SET name_he=?, search_text=search_text || ' ' || ? WHERE id=?",
                           (he, he, rec["id"]))
                translated += 1
        db.execute("DELETE FROM food_fts")
        db.execute("INSERT INTO food_fts(id, search_text) SELECT id, search_text FROM foods")
        db.commit()
        after = db.execute("SELECT COUNT(*), SUM(kcal_100), SUM(protein_100), SUM(carbs_100), SUM(fat_100) FROM foods").fetchone()
        if before != after:
            raise ValueError("Translation changed nutrition values or record count")
        count = before[0]
        hebrew = db.execute("SELECT COUNT(*) FROM foods WHERE name_he IS NOT NULL AND name_he != ''").fetchone()[0]
        fts = db.execute("SELECT COUNT(*) FROM food_fts").fetchone()[0]
        if fts != count or hebrew / count < .95:
            raise ValueError(f"FTS or Hebrew coverage too low: {fts}/{count}, {hebrew}/{count}")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite corrupted")
        samples = db.execute("SELECT id, name_en, name_he, kcal_100 FROM foods ORDER BY id LIMIT 120").fetchall()
        db.execute("VACUUM")
    finally:
        db.close()
    payload = db_path.read_bytes()
    meta = {
        "packID": "core.global", "region": "GLOBAL", "source": "USDA-FoodDataCentral",
        "version": args.version, "title": "International Core · USDA", "license": "CC0 1.0",
        "sourceURL": "https://fdc.nal.usda.gov/download-datasets/",
        "schema": 1, "count": count, "sha256": hashlib.sha256(payload).hexdigest()
    }
    header = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(header) >= 8192:
        raise ValueError("Oversized DTHPK header")
    result = out / "International-Core.dthpack"
    result.write_bytes(MAGIC + struct.pack(">I", len(header)) + header + payload)
    file_digest = hashlib.sha256(result.read_bytes()).hexdigest()
    item = {
        "file": result.name, "packID": "core.global", "source": meta["source"],
        "sourceURL": meta["sourceURL"], "license": meta["license"],
        "records": count, "bytes": result.stat().st_size, "sha256_file": file_digest
    }
    (out / "pack-index.json").write_text(json.dumps({
        "region": "GLOBAL", "schema": 1, "status": "candidate-for-human-translation-review",
        "files": [item]
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "SHA256SUMS").write_text(file_digest + "  " + result.name + "\n", encoding="utf-8")
    (out / "translation-report.json").write_text(json.dumps({
        "status": "machine-translated-requires-human-sample-review",
        "rows": count, "hebrew_rows": hebrew, "hebrew_coverage": hebrew / count,
        "source_counts": counts, "source_sha256": archives,
        "translation_model": "Helsinki-NLP/opus-mt-en-he", "translation_license": "Apache-2.0",
        "sample": samples
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": count, "hebrew": hebrew, "size": result.stat().st_size}, ensure_ascii=False))

if __name__ == "__main__":
    main()
