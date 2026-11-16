#!/usr/bin/env python3
"""Append sourced Georgian *recipe estimates* to authentic Georgia 1.0 OFF foods.

Never change an existing food row, calorie/macro source, ID or historic asset.
All added values are labelled estimates; each has a URL, method and editable serving.
No network needed: caller supplies authenticated original Georgia 1.0 pack.
"""
import argparse
import hashlib
import json
import math
import sqlite3
import struct
import zipfile
from pathlib import Path

MAGIC = b"DTHPK1\n"
MUST_HAVE = ("kcal", "protein", "carbs", "fat")

def open_pack(path):
    blob = Path(path).read_bytes()
    if not blob.startswith(MAGIC) or len(blob) < 12:
        raise ValueError("Invalid original dthpack envelope")
    hlen = struct.unpack(">I", blob[7:11])[0]
    if not 0 < hlen < 8192:
        raise ValueError("Invalid header size")
    meta = json.loads(blob[11:11 + hlen])
    data = blob[11 + hlen:]
    if hashlib.sha256(data).hexdigest() != meta.get("sha256"):
        raise ValueError("Original SQLite SHA256 mismatch")
    if (meta.get("packID"),meta.get("region"),meta.get("version"),meta.get("schema")) != ("travel.ge","GE","1.0",1):
        raise ValueError("Not the original Georgia 1.0 source pack")
    db = sqlite3.connect(":memory:")
    db.deserialize(data)
    if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("Original SQLite corrupt")
    if db.execute("SELECT COUNT(*) FROM foods").fetchone()[0] != meta["count"]:
        raise ValueError("Original count mismatch")
    return db, meta

def food_values(item):
    if item["nutritionBasis"] == "published_estimate_per_100g":
        values = item["nutrients"]
    elif item["nutritionBasis"] == "estimated_per_serving_divided_by_weight":
        grams = item["sourceServingGrams"]
        if not 1 <= grams <= 3000:
            raise ValueError("Invalid source serving weight")
        values = {k: float(v) * 100.0 / grams for k,v in item["sourceServingNutrients"].items()}
    else:
        raise ValueError("Unknown estimate basis")
    for key in MUST_HAVE:
        val = values.get(key)
        if not isinstance(val, (int,float)) or not math.isfinite(val) or val < 0:
            raise ValueError(f"Missing or invalid {key} for {item['id']}")
    if not (0 <= values["kcal"] <= 950 and all(values[k] <= 100 for k in ("protein", "carbs", "fat"))):
        raise ValueError(f"Out of range nutrition in {item['id']}")
    return values

def build(base, recipe_json, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    db, old = open_pack(base)
    try:
        source_rows = db.execute("SELECT * FROM foods ORDER BY id").fetchall()
        source_count = len(source_rows)
        old_fts = db.execute("SELECT count(*) FROM food_fts").fetchone()[0]
        if old_fts != source_count:
            raise ValueError("Original FTS mismatch")
        spec = json.loads(Path(recipe_json).read_text(encoding="utf-8"))
        if (spec.get("packID"),spec.get("version")) != ("travel.ge","1.1"):
            raise ValueError("Wrong recipe file version")
        added = 0
        seen = set()
        for item in spec["records"]:
            slug = item["id"]
            source_id = "recipe-ge:" + slug
            fid = "recipe:" + source_id
            if slug in seen or db.execute("SELECT 1 FROM foods WHERE id=?", (fid,)).fetchone():
                raise ValueError(f"Duplicate recipe {slug}")
            seen.add(slug)
            names = [item.get("he","").strip(), item.get("en","").strip(), item.get("ka","").strip()]
            if not names[0] or not names[1] or not item.get("sourceURL","").startswith("https://"):
                raise ValueError("Missing multilingual searchable names or authentic source link")
            nutrients = food_values(item)
            serving = item.get("unitWeightGrams") or item.get("servingGrams") or 100
            if not isinstance(serving,(int,float)) or not 0 < serving <= 5000:
                raise ValueError("Invalid serving size")
            # Common English/Georgian labels alongside Hebrew. Product search uses
            # the same Unicode FTS5 index as existing imported country products.
            search = " ".join(s for s in (names + [names[0].replace("׳","'"),slug.replace("-"," ")]) if s)
            flags = json.dumps(["recipe_estimate", "not_manufacturer_label",
                                "source_link_available", "editable_serving"], ensure_ascii=False)
            db.execute("""
              INSERT INTO foods (
                id,source,source_id,name_de,name_en,name_he,brand,barcode,
                base_unit,kcal_100,protein_100,carbs_100,fat_100,sugar_100,
                fiber_100,serving_size,search_text,quality_flags,source_url)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (fid,"GeorgianRecipeEstimate",source_id,names[2] or names[1],names[1],
                  names[0] + " · אומדן מתכון",None,None,"g",
                  round(nutrients["kcal"],4),round(nutrients["protein"],4),
                  round(nutrients["carbs"],4),round(nutrients["fat"],4),
                  None,round(nutrients["fiber"],4) if "fiber" in nutrients else None,
                  serving,search + " אומדן מתכון",flags,item["sourceURL"]))
            db.execute("INSERT INTO food_fts(id,search_text) VALUES (?,?)", (fid,search + " אומדן מתכון"))
            added += 1
        db.commit()
        after_rows = db.execute("SELECT * FROM foods WHERE id NOT LIKE 'recipe:recipe-ge:%' ORDER BY id").fetchall()
        if source_rows != after_rows:
            raise ValueError("An original OFF source record was modified")
        count = db.execute("SELECT COUNT(*) FROM foods").fetchone()[0]
        if count != source_count + added or db.execute("SELECT COUNT(*) FROM food_fts").fetchone()[0] != count:
            raise ValueError("Food/FTS counts wrong")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite damaged")
        for query in ("חינקלי","חצ׳פורי","Khinkali","Khachapuri","ხინკალი",
                      "სალათა","פחאלי","Spinach","סלט"):
            # Some Georgian salad names omit სალათა, but the recorded Georgian
            # cucumber/tomato salad must include it.
            found = db.execute("SELECT count(*) FROM food_fts WHERE food_fts MATCH ?", ('"' + query.replace('"','""') + '"',)).fetchone()[0]
            if not found:
                raise ValueError("Missing offline FTS test term: " + query)
        original_nutrients = hashlib.sha256(json.dumps(source_rows,ensure_ascii=False,default=str).encode()).hexdigest()
        db.execute("VACUUM")
        data = db.serialize()
        header = dict(old)
        header.update(version="1.1",count=count,
                      title="Georgia · products and Georgian recipe estimates",
                      sha256=hashlib.sha256(data).hexdigest(),
                      originalSourceFoodCount=source_count,
                      supplementalRecipeEstimateCount=added,
                      supplementalSource="GeorgianRecipeEstimate",
                      recipeEstimateNotice="Based on cited typical recipes, editable estimates, not lab measurements.")
        encoded = json.dumps(header,ensure_ascii=False,separators=(",",":")).encode()
        if len(encoded) >= 8192:
            raise ValueError("Pack header too large")
        pack = out/"Georgia-OpenFoodFacts.dthpack"
        pack.write_bytes(MAGIC + struct.pack(">I",len(encoded)) + encoded + data)
        digest = hashlib.sha256(pack.read_bytes()).hexdigest()
        idx = {"schema":1,"region":"GE","status":"verified","release_tag":"georgia-1.1",
            "source_scope":"574 original OFF marketplace products plus traceable, explicitly labelled Georgian recipe estimates",
            "translation_review":"names for additional recipes curated; existing 1.0 names untouched",
            "files":[{"file":pack.name,"bytes":pack.stat().st_size,"sha256_file":digest,
                      "records":count,"packID":"travel.ge","source":"OpenFoodFacts",
                      "version":"1.1","license":"ODbL 1.0","sourceURL":"https://world.openfoodfacts.org/data"}]}
        (out/"pack-index.json").write_text(json.dumps(idx,ensure_ascii=False,indent=2)+"\n")
        qa = {"release_tag":"georgia-1.1","original_1_0_products_unchanged":True,
              "original_source_rows":source_count,"new_recipe_estimates":added,"total":count,
              "salads_added":sum(r["group"]=="salad" for r in spec["records"]),
              "original_rows_sha256":original_nutrients,
              "source_recipes_have_individual_urls":True,
              "recipe_estimates_not_lab_data":True,
              "status":"automated structural QA only; on-device QA pending"}
        (out/"qa-report.json").write_text(json.dumps(qa,ensure_ascii=False,indent=2)+"\n")
        (out/"SOURCES_AND_LIMITATIONS.md").write_text(
           "# Georgia 1.1 data sources and limitations\n\n"
           "The original Open Food Facts 1.0 records are retained intact (ODbL 1.0). "
           "Additional factual numeric nutritional estimates are attributed to the "
           "recipe pages linked in builder/georgia_1_1_recipes.json, including "
           "gulianigeorgia.ge and foodlab.ge. No source recipes or protected wording "
           "are copied into the data package. Estimates depend on ingredients and "
           "cooked weight, and are not measured official nutrition or product labels. "
           "Original sugar and missing fiber values are not invented. "
           "Serving weights are user-editable and may vary widely by restaurant. "
           "The source 1.0 tag remains immutable.\n"
        )
        (out/"RECIPE_NOTES_HE.txt").write_text(
           "כולל אומדני מתכון למטבח הגאורגי. הערכים התזונתיים אינם נתוני יצרן או מדידה; "
           "שמנים, גבינות, אגוזים וגודל מנות משתנים. יש לערוך משקל לפי האכילה בפועל. "
           "מוצרי Open Food Facts המקוריים לא השתנו.\n"
        )
        files = [pack.name,"pack-index.json","qa-report.json","SOURCES_AND_LIMITATIONS.md","RECIPE_NOTES_HE.txt"]
        (out/"SHA256SUMS").write_text(
            "".join(hashlib.sha256((out/name).read_bytes()).hexdigest()+"  "+name+"\n" for name in files))
        with zipfile.ZipFile(out/"Georgia-1.1-Offline-Backup.zip","w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for name in files+["SHA256SUMS"]:
                z.write(out/name,arcname=name)
        print("GEORGIA_1_1_QA",json.dumps(qa,ensure_ascii=False),flush=True)
    finally:
        db.close()

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--base-pack",required=True)
    p.add_argument("--recipes",default="builder/georgia_1_1_recipes.json")
    p.add_argument("--out",default="dist")
    args=p.parse_args()
    build(args.base_pack,args.recipes,args.out)
