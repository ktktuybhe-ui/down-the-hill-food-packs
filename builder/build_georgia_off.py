#!/usr/bin/env python3
"""Georgia market pack from real Open Food Facts records; QA candidate, never auto-approved.
Every nutrient value comes from a submitted per-100g/ml field. No calculated food facts.
The iOS Build 34 universal serving engine handles editable contextual portions.
"""
import argparse,hashlib,json,math,sqlite3,struct,time,urllib.request,urllib.parse,urllib.error
from pathlib import Path
from build_pack import insert_records,check,quality
API="https://world.openfoodfacts.org/api/v2/search"
FIELDS="code,product_name,product_name_ka,product_name_en,brands,nutriments,nutrition_data_per,serving_quantity,countries_tags,scans_n,completeness"
ALIASES={"ხინკალი":"חינקלי","khinkali":"חינקלי","ხაჭაპური":"חצ׳פורי","khachapuri":"חצ׳פורי",
"სულგუნი":"גבינת סולוגוני","sulguni":"גבינת סולוגוני","ჩურჩხელა":"צ׳ורצ׳חלה","churchkhela":"צ׳ורצ׳חלה",
"აჯიკა":"אדג׳יקה","adjika":"אדג׳יקה","ტყემალი":"טקמאלי","tkemali":"טקמאלי",
"ლობიო":"לוביו","lobio":"לוביו","ლობიანი":"לוביאני","lobiani":"לוביאני",
"მჭადი":"מצ׳אדי","mchadi":"מצ׳אדי","ფხალი":"פחאלי","pkhali":"פחאלי",
"საცივი":"סציבי","satsivi":"סציבי","მაწონი":"מצוני","matsoni":"מצוני",
"გოზინაყი":"גוזינאקי","gozinaki":"גוזינאקי","კახური":"קאחורי"}
MAGIC=b"DTHPK1\n"
def numeric(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except (TypeError,ValueError):return None
def fetch(page,page_size,agent):
    url=API+"?"+urllib.parse.urlencode({"countries_tags_en":"georgia","page":page,"page_size":page_size,"fields":FIELDS})
    req=urllib.request.Request(url,headers={"User-Agent":agent,"Accept":"application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req,timeout=90) as res: payload=json.load(res)
            if not isinstance(payload.get("products"),list): raise RuntimeError("Malformed OFF page")
            return payload
        except (urllib.error.URLError,TimeoutError,ValueError) as exc:
            if attempt==3: raise
            print("Retry page",page,"error",str(exc),flush=True)
            time.sleep(8+8*attempt)
def nutrition(p):
    n=p.get("nutriments") or {}
    prefer=["100ml","100g"] if p.get("nutrition_data_per")=="100ml" else ["100g","100ml"]
    for unit in prefer:
        kcal=numeric(n.get("energy-kcal_"+unit))
        if kcal is None:
            kj=numeric(n.get("energy-kj_"+unit))
            if kj is not None:kcal=kj/4.184
        val={"kcal":kcal,"protein":numeric(n.get("proteins_"+unit)),
             "carbs":numeric(n.get("carbohydrates_"+unit)),"fat":numeric(n.get("fat_"+unit)),
             "sugar":numeric(n.get("sugars_"+unit)),"fiber":numeric(n.get("fiber_"+unit))}
        if check(val):return val,"ml" if unit=="100ml" else "g"
    return None,None
def row(p):
    code=str(p.get("code") or "")
    if not (code.isdigit() and 8<=len(code)<=14):return None
    countries=p.get("countries_tags") or []
    if not isinstance(countries,list): countries=[countries]
    if not any("georgia" in str(c).lower() or "საქართველო" in str(c) for c in countries): return None
    ka=str(p.get("product_name_ka") or p.get("product_name") or "").strip()
    en=str(p.get("product_name_en") or "").strip()
    if not (ka or en):return None
    numbers,unit=nutrition(p)
    if numbers is None:return None
    label=ka or en
    he=next((ALIASES[x.lower()] for x in [label,en] if x.lower() in ALIASES),"")
    serving=numeric(p.get("serving_quantity"))
    if serving is not None and not 0.1<=serving<=5000: serving=None
    brand=str(p.get("brands") or "").strip()
    search=" ".join(filter(None,[ka,en,brand,he,code]))
    return {"id":"geoff:"+code,"source":"OpenFoodFacts","source_id":code,
       "de":ka,"en":en,"he":he,"brand":brand,"barcode":code,"base_unit":unit,
       "n":numbers,"serving":serving,"search":search,"flags":quality(numbers),
       "url":"https://world.openfoodfacts.org/product/"+code}
def make(args):
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    records=[];seen=set();api_count=None;fetched=0;complete=False
    if args.pages_dir:
        pages_dir=Path(args.pages_dir)
        files=sorted(pages_dir.glob("page-*.json"))
        if not files:raise RuntimeError("No downloaded source pages")
        page_map={}
        for filename in files:
            page=int(filename.stem.split("-")[-1])
            if page in page_map:raise RuntimeError("Duplicate source page "+str(page))
            page_map[page]=json.loads(filename.read_text(encoding="utf-8"))
        api_count=int(page_map.get(1,{}).get("count") or 0)
        if api_count<=0:raise RuntimeError("Source reported zero products")
        # The provider can cap requests at 100 even when 500 is requested.
        # Never mistake a provider cap for the end of the country export.
        reported_size=int(page_map[1].get("page_size") or 100)
        if reported_size<=0 or reported_size>1000:raise RuntimeError("Invalid provider page size")
        first_batch=len(page_map[1].get("products",[]))
        effective_size=min(reported_size,first_batch)
        if effective_size<=0:raise RuntimeError("Invalid empty first page")
        expected_pages=(api_count+effective_size-1)//effective_size
        missing=[i for i in range(1,expected_pages+1) if i not in page_map]
        if missing:raise RuntimeError("Missing pages for complete source: "+str(missing))
        for page in range(1,expected_pages+1):
            response=page_map[page]
            if int(response.get("page") or page)!=page:
                raise RuntimeError("Wrong page metadata")
            batch=response.get("products",[])
            if page<expected_pages and len(batch)!=effective_size:
                raise RuntimeError("Unexpected incomplete source page "+str(page))
            fetched+=len(batch)
            print("Archived Georgia page",page,"rows",len(batch),flush=True)
            for p in batch:
                rec=row(p)
                if rec and rec["id"] not in seen:
                    records.append(rec);seen.add(rec["id"])
        complete=fetched>=api_count
    else:
        for page in range(1,args.max_pages+1):
            response=fetch(page,args.page_size,args.user_agent)
            if api_count is None:api_count=int(response.get("count") or 0)
            batch=response.get("products",[]);fetched+=len(batch)
            print("Georgia products page",page,"fetched",fetched,"of",api_count,flush=True)
            for p in batch:
                rec=row(p)
                if rec and rec["id"] not in seen:
                    records.append(rec);seen.add(rec["id"])
            if api_count>0 and fetched>=api_count:complete=True;break
            if not batch:break
            time.sleep(args.pause)
    if not complete:raise RuntimeError("Incomplete Georgia country export: missing pages or API throttling; no partial pack promoted.")
    records.sort(key=lambda r:r["id"])
    db=out/"georgia.sqlite"
    count=insert_records(db,records)
    if count<20:raise RuntimeError("Insufficient authentic valid Georgian products: "+str(count))
    con=sqlite3.connect(db)
    try:
        assert con.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
        assert con.execute("SELECT count(*) FROM food_fts").fetchone()[0]==count
        he=con.execute("SELECT count(*) FROM foods WHERE name_he GLOB '*[א-ת]*'").fetchone()[0]
        serving_count=con.execute("SELECT count(*) FROM foods WHERE serving_size IS NOT NULL AND serving_size>0").fetchone()[0]
        liquids=con.execute("SELECT count(*) FROM foods WHERE base_unit='ml'").fetchone()[0]
        bad=con.execute("SELECT count(*) FROM foods WHERE kcal_100<0 OR protein_100<0 OR carbs_100<0 OR fat_100<0").fetchone()[0]
        assert bad==0
        samples=con.execute("SELECT id,name_de,name_en,name_he,serving_size,base_unit FROM foods ORDER BY id LIMIT 100").fetchall()
    finally:con.close()
    data=db.read_bytes()
    metadata={"packID":"travel.ge","region":"GE","source":"OpenFoodFacts",
       "version":args.version,"title":"Georgia Open Food Facts · local market",
       "license":"ODbL 1.0","sourceURL":"https://world.openfoodfacts.org/data",
       "schema":1,"count":count,"sha256":hashlib.sha256(data).hexdigest()}
    h=json.dumps(metadata,ensure_ascii=False,separators=(",",":")).encode()
    assert 0<len(h)<8192
    pack=out/"Georgia-OpenFoodFacts.dthpack"
    pack.write_bytes(MAGIC+struct.pack(">I",len(h))+h+data)
    digest=hashlib.sha256(pack.read_bytes()).hexdigest()
    report={"source_records_reported":api_count,"source_records_fetched":fetched,"eligible_records":count,
      "hebrew_name_records":he,"remaining_original_name_records":count-he,
      "packaged_serving_size_records":serving_count,"native_ml_records":liquids,
      "nutrition_provenance":"original OFF labels, no fabricated values",
      "translation_review":"pending manual linguistic review",
      "serving_standard":"Build34 shared serving rules; editable default where missing",
      "scope":"Marketed products, not Georgian historic recipe data",
      "samples":samples}
    (out/"qa-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    (out/"ATTRIBUTION.md").write_text("Based on Open Food Facts, ODbL 1.0; source https://world.openfoodfacts.org/data . Community submitted values must be reviewed. Georgian composition tables (2009) are NOT copied because redistribution licensing has not been confirmed. Original Georgian and English names remain searchable.\n")
    (out/"QA_PENDING_HE.txt").write_text("Georgia CANDIDATE ONLY. Source and nutrition structure validated, but translations and completeness of traditional dishes are unverified. Not an approved food-pack Release for installation in Build 33/34. Do not claim comprehensive Georgian composition coverage.\n")
    index={"region":"GE","schema":1,"status":"candidate-pending-linguistic-QA","release_tag":args.version,
       "files":[{"file":pack.name,"bytes":pack.stat().st_size,"sha256_file":digest,
         "packID":"travel.ge","source":"OpenFoodFacts","records":count}]}
    (out/"pack-index.json").write_text(json.dumps(index,ensure_ascii=False,indent=2)+"\n")
    files=["Georgia-OpenFoodFacts.dthpack","qa-report.json","pack-index.json","ATTRIBUTION.md","QA_PENDING_HE.txt"]
    (out/"SHA256SUMS").write_text("".join(hashlib.sha256((out/f).read_bytes()).hexdigest()+"  "+f+"\n" for f in files))
    import zipfile
    with zipfile.ZipFile(out/"Georgia-Candidate-Offline-Backup.zip","w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for f in files+["SHA256SUMS"]:z.write(out/f,f)
    print("GEORGIA_QA",json.dumps({k:v for k,v in report.items() if k!="samples"},ensure_ascii=False),flush=True)
def main():
    a=argparse.ArgumentParser()
    a.add_argument("--out",default="dist-georgia")
    a.add_argument("--pages-dir",default=None,help="Fully audited source page snapshots, required for sharded collector")
    a.add_argument("--version",default="georgia-he-candidate")
    a.add_argument("--page-size",type=int,default=100)
    a.add_argument("--max-pages",type=int,default=100)
    a.add_argument("--pause",type=float,default=4)
    a.add_argument("--user-agent",default="DownTheHill-FoodPack/0.6.6 (GitHub ktktuybhe-ui/down-the-hill-food-packs)")
    make(a.parse_args())
if __name__=="__main__":main()
