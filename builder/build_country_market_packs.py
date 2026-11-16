#!/usr/bin/env python3
"""Build authentic OFF market-country dthpack from the official per-country CSV export.
All calories and macros are copied from 100g/100ml source fields. No fabricated facts.
A pack is country-specific, not a claim that all traditional recipes are represented.
"""
import argparse, csv, hashlib, heapq, json, math, re, sqlite3, struct, pathlib
from build_pack import insert_records, check, quality, number

COUNTRIES = {
 "GE":{"title":"Georgia","local":"ka","label":"גאורגיה","required":40,"aliases":{
   "khinkali":"חינקלי","ხინკალი":"חינקלי","khachapuri":"חצ׳פורי","ხაჭაპური":"חצ׳פורי",
   "sulguni":"סולוגוני","სულგუნი":"סולוגוני","churchkhela":"צ׳ורצ׳חלה","ჩურჩხელა":"צ׳ורצ׳חלה",
   "tkemali":"טקמאלי","ტყემალი":"טקמאלי","adjika":"אדג׳יקה","აჯიკა":"אדג׳יקה",
   "matsoni":"מצוני","მაწონი":"מצוני","lobio":"לוביו","ლობიო":"לוביו","lobiani":"לוביאני",
   "mchadi":"מצ׳אדי","მჭადი":"מצ׳אדי","pkhali":"פחאלי","ფხალი":"פחאלי"}},
 "ES":{"title":"Spain","local":"es","label":"ספרד","required":100,"aliases":{
   "gazpacho":"גספצ׳ו","paella":"פאייה","tortilla española":"טורטייה ספרדית",
   "churros":"צ׳ורוס","jamón serrano":"חמון סראנו","salmorejo":"סלמורחו",
   "croquetas":"קרוקטס","horchata":"אורצ׳טה"}},
 "IT":{"title":"Italy","local":"it","label":"איטליה","required":100,"aliases":{
   "mozzarella":"מוצרלה","parmigiano reggiano":"פרמיג׳אנו רג׳אנו",
   "gnocchi":"ניוקי","risotto":"ריזוטו","tiramisu":"טירמיסו",
   "pesto":"פסטו","focaccia":"פוקאצ׳ה","polenta":"פולנטה"}},
 "FR":{"title":"France","local":"fr","label":"צרפת","required":100,"aliases":{
   "baguette":"בגט","croissant":"קרואסון","camembert":"קממבר",
   "brie":"ברי","ratatouille":"רטטוי","quiche lorraine":"קיש לורן",
   "crème brûlée":"קרם ברולה","pain au chocolat":"פן או שוקולה"}},
 "GR":{"title":"Greece","local":"el","label":"יוון","required":80,"aliases":{
   "feta":"פטה","tzatziki":"צזיקי","souvlaki":"סופלאקי",
   "moussaka":"מוסקה","spanakopita":"ספנקופיטה","dolmades":"דולמדס",
   "gyros":"גירוס","horiatiki":"סלט יווני"}}
}
NAMES={"GE":["georgia","საქართველო"],"ES":["spain","españa"],"IT":["italy","italia"],"FR":["france"],"GR":["greece","ελλάδα","ellada"]}
MAGIC=b"DTHPK1\n"
def v(x):
 try:
  n=float(str(x).strip().replace(",","."))
  return n if math.isfinite(n) else None
 except (ValueError,TypeError):return None

def nutrients(p):
 # OFF 2026 flattened CSV exports expose provenance-specific nested label fields
 # rather than the older nutriments.energy-kcal_100g columns. Do NOT combine
 # nutrients across different label origins or per-100g vs per-100ml baselines.
 preferred=["100ml","100g"] if str(p.get("nutrition_data_per","")).lower()=="100ml" else ["100g","100ml"]
 sources=("manufacturer","packaging")
 for unit in preferred:
  for src in sources:
   prefix=f"nutrition.input_sets.{src}.as_sold.{unit}.nutrients."
   def field(key):
    return v(p.get(prefix+key+".value"))
   kcal=field("energy-kcal")
   if kcal is None:
    kj=field("energy-kj")
    if kj is not None:kcal=kj/4.184
   n={"kcal":kcal,"protein":field("proteins"),"carbs":field("carbohydrates"),
      "fat":field("fat"),"sugar":field("sugars"),"fiber":field("fiber")}
   if check(n):return n,("ml" if unit=="100ml" else "g"),src
 # Compatible with legacy OFF exports where nutrients appear as flat fields.
 for unit in preferred:
  for prefix in ("","nutriments."):
   def field(key): return v(p.get(prefix+key+"_"+unit))
   kcal=field("energy-kcal")
   if kcal is None:
    kj=field("energy-kj")
    if kj is not None:kcal=kj/4.184
   n={"kcal":kcal,"protein":field("proteins"),"carbs":field("carbohydrates"),
      "fat":field("fat"),"sugar":field("sugars"),"fiber":field("fiber")}
   if check(n):return n,("ml" if unit=="100ml" else "g"),"legacy"
 return None,None,None

def make_row(p,code):
 cfg=COUNTRIES[code]
 barcode=str(p.get("code") or "").strip()
 if not re.fullmatch(r"\d{8,14}",barcode):return None
 countries=str(p.get("countries_tags") or p.get("countries_tags_en") or p.get("countries") or "").lower()
 # Enforce exact comma/space/semicolon-separated country tags, avoiding substrings of other countries.
 tags=re.split(r"[,;|]+",countries)
 if not any(any(tag.strip() in (name,"en:"+name) for name in NAMES[code]) for tag in tags):
  return None
 local=str(p.get("product_name_"+cfg["local"]) or "").strip()
 original=str(p.get("product_name") or "").strip()
 english=str(p.get("product_name_en") or "").strip()
 if not (local or original or english):
  lc=str(p.get("lc") or "").strip().lower()
  original=str(p.get("product_name_"+lc) or "").strip() if lc else ""
 if not (local or original or english):
  original=next((str(value).strip() for key,value in p.items() if key.startswith("product_name_") and value and str(value).strip()),"")
 if not (local or original or english):return None
 n,unit,provenance=nutrients(p)
 if n is None:return None
 name=local or original or english
 # Only exact dish label matches get the curated Hebrew alias; never replace arbitrary product names.
 he=cfg["aliases"].get(name.casefold(),cfg["aliases"].get(english.casefold(),""))
 brand=str(p.get("brands") or "").strip()
 serving=v(p.get("serving_quantity"))
 if serving is None and provenance in ("manufacturer","packaging"):
  prefix=f"nutrition.input_sets.{provenance}.as_sold.serving."
  source_unit=str(p.get(prefix+"per_unit") or "").lower()
  if source_unit in (unit,unit+"s"):serving=v(p.get(prefix+"per_quantity"))
 if serving is not None and not 0.1<=serving<=5000:serving=None
 scans=v(p.get("scans_n")) or 0
 completeness=v(p.get("completeness")) or 0
 score=scans+30*completeness+3*bool(local)+3*bool(english)+2*bool(serving)
 return score,{"id":"off:"+barcode,"source":"OpenFoodFacts","source_id":barcode,
  "de":name,"en":english,"he":he,"brand":brand,"barcode":barcode,"base_unit":unit,
  "n":n,"serving":serving,
  "search":" ".join(filter(None,[name,local,original,english,brand,he,barcode])),
  "flags":quality(n),"url":"https://world.openfoodfacts.org/product/"+barcode}

def run(args):
 cfg=COUNTRIES[args.country]
 out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True)
 src=pathlib.Path(args.csv)
 if not src.exists() or src.stat().st_size<1000:raise RuntimeError("Country export missing or suspiciously short")
 # Authenticated source CSV, not HTML "200" response.
 with src.open("r",encoding="utf-8-sig",errors="replace",newline="") as handle:
  first=handle.readline()
  if "<html" in first.lower() or "<!doctype" in first.lower():raise RuntimeError("Received HTML, not CSV")
  delimiter="\t" if first.count("\t")>first.count(",") else ","
  handle.seek(0)
  csv.field_size_limit(20_000_000)
  reader=csv.DictReader(handle,delimiter=delimiter)
  headers=set(reader.fieldnames or [])
  necessary={"code","countries_tags"}
  if not necessary.issubset(headers):
   raise RuntimeError("Unrecognized or incomplete country export header: missing "+repr(necessary-headers))
  heap=[];source_rows=valid_rows=0
  for p in reader:
   source_rows+=1
   result=make_row(p,args.country)
   if result is None:continue
   valid_rows+=1
   score,record=result
   item=(score,source_rows,record)
   if len(heap)<args.max_records:heapq.heappush(heap,item)
   elif (score,source_rows)>heap[0][:2]:heapq.heapreplace(heap,item)
   if source_rows%20000==0:print("PARSED",args.country,source_rows,"valid",valid_rows,flush=True)
 if source_rows<cfg["required"] or valid_rows<cfg["required"]:
  raise RuntimeError("Insufficient complete/valid country source: "+repr((source_rows,valid_rows,cfg["required"])))
 selected=[item[2] for item in sorted(heap,key=lambda x:x[1])]
 # Deduplicate identical barcodes, retaining source-selected ranking.
 unique={}
 for r in selected: unique[r["source_id"]]=r
 records=sorted(unique.values(),key=lambda x:x["id"])
 database=out/"country.sqlite"
 count=insert_records(database,records)
 if count<cfg["required"]:raise RuntimeError("Insufficient unique records after dedup")
 conn=sqlite3.connect(database)
 try:
  if conn.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise RuntimeError("SQLite failed integrity_check")
  if conn.execute("SELECT count(*) FROM food_fts").fetchone()[0]!=count:raise RuntimeError("Broken food FTS")
  serving=conn.execute("SELECT count(*) FROM foods WHERE serving_size IS NOT NULL").fetchone()[0]
  native_ml=conn.execute("SELECT count(*) FROM foods WHERE base_unit='ml'").fetchone()[0]
  hebrew=conn.execute("SELECT count(*) FROM foods WHERE name_he GLOB '*[א-ת]*'").fetchone()[0]
  negative=conn.execute("SELECT count(*) FROM foods WHERE kcal_100<0 OR protein_100<0 OR carbs_100<0 OR fat_100<0").fetchone()[0]
  bad_unit=conn.execute("SELECT count(*) FROM foods WHERE base_unit NOT IN ('g','ml')").fetchone()[0]
  bad_serving=conn.execute("SELECT count(*) FROM foods WHERE serving_size<=0 OR serving_size>5000").fetchone()[0]
  if negative or bad_unit or bad_serving:raise RuntimeError("Invalid source nutrition or serving units")
 finally:conn.close()
 data=database.read_bytes()
 meta={"packID":"travel."+args.country.lower(),"region":args.country,"source":"OpenFoodFacts",
       "version":args.version,"title":cfg["title"]+" · food products",
       "license":"ODbL 1.0","sourceURL":"https://world.openfoodfacts.org/data","schema":1,"count":count,
       "sha256":hashlib.sha256(data).hexdigest()}
 header=json.dumps(meta,ensure_ascii=False,separators=(",",":")).encode()
 if not 0<len(header)<8192:raise RuntimeError("Invalid metadata length")
 file=out/(cfg["title"]+"-OpenFoodFacts.dthpack")
 file.write_bytes(MAGIC+struct.pack(">I",len(header))+header+data)
 digest=hashlib.sha256(file.read_bytes()).hexdigest()
 qa={"country":args.country,"country_source_records":source_rows,"country_eligible_complete_nutrition":valid_rows,
     "selected_unique_rows":count,"hebrew_name_rows":hebrew,"original_language_rows":count-hebrew,
     "rows_with_source_serving":serving,"native_ml_rows":native_ml,"capped":valid_rows>args.max_records,
     "data_provenance":"Open Food Facts per-100g/ml; no numeric synthesis",
     "coverage_limitation":"marketed packaged products, NOT a complete traditional-dishes table",
     "language_qa":"Hebrew aliases are curated but untranslated product names remain in original language",
     "serving_qa":"Source servings when present; editable natural serving via app Build 34"}
 (out/"qa-report.json").write_text(json.dumps(qa,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 (out/"ATTRIBUTION.md").write_text("Open Food Facts ODbL 1.0 https://world.openfoodfacts.org/data\\nCountry-tagged products selected. This pack is a separate, share-alike licensed dataset. Nutrition reflects labels, which may contain user errors.\\n",encoding="utf-8")
 (out/"LIMITATIONS_HE.txt").write_text("חבילת מוצרים המשווקים במדינה, אינה מאגר מלא של כל המאכלים המסורתיים. רוב שמות המוצרים לא תורגמו לעברית. הערכים ל-100 גרם/מ״ל הועתקו מ-Open Food Facts, ונתוני מנות שאינם במקור הם אומדן ניתן לעריכה באפליקציה.\\n",encoding="utf-8")
 index={"region":args.country,"schema":1,"status":"verified","release_tag":args.release_tag,
        "source_scope":"country-marketed-packaged-products-only",
        "translation_review":"original-language-names; curated-aliases-only",
        "files":[{"file":file.name,"records":count,"bytes":file.stat().st_size,"sha256_file":digest,
                  "packID":meta["packID"],"source":"OpenFoodFacts","license":"ODbL 1.0",
                  "sourceURL":meta["sourceURL"],"version":meta["version"]}]}
 (out/"pack-index.json").write_text(json.dumps(index,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 names=[file.name,"pack-index.json","qa-report.json","ATTRIBUTION.md","LIMITATIONS_HE.txt"]
 (out/"SHA256SUMS").write_text("".join(hashlib.sha256((out/name).read_bytes()).hexdigest()+"  "+name+"\n" for name in names))
 import zipfile
 backup=out/(cfg["title"]+"-Food-Pack-Offline-Backup.zip")
 with zipfile.ZipFile(backup,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for name in names+["SHA256SUMS"]:z.write(out/name,arcname=name)
 print("COUNTRY_QA",json.dumps(qa,ensure_ascii=False),flush=True)

if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("--country",choices=sorted(COUNTRIES),required=True)
 p.add_argument("--csv",required=True)
 p.add_argument("--out",required=True)
 p.add_argument("--version",required=True)
 p.add_argument("--release-tag",required=True)
 p.add_argument("--max-records",type=int,default=4000)
 run(p.parse_args())
