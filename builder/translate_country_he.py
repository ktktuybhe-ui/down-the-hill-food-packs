#!/usr/bin/env python3
"""Apply machine-generated Hebrew NAME labels to authentic country .dthpacks.
Preserves all nutrient data, source IDs, originals, serving sizes, source metadata.
Reports exactly which labels are machine-translated. Not human linguistic QA.
"""
import argparse,hashlib,json,re,sqlite3,struct,tempfile,random
from pathlib import Path

MAGIC=b"DTHPK1\n"
HE=re.compile("[\u0590-\u05ff]")
KA=re.compile("[\u10a0-\u10ff]")
EL=re.compile("[\u0370-\u03ff]")
LANG={"GE":"ka","GR":"el","ES":"es","IT":"it","FR":"fr"}
BRIDGE={"ka":"Helsinki-NLP/opus-mt-ka-en","el":"Helsinki-NLP/opus-mt-el-en",
        "es":"Helsinki-NLP/opus-mt-es-en","it":"Helsinki-NLP/opus-mt-it-en",
        "fr":"Helsinki-NLP/opus-mt-fr-en"}
PROTECTED=["id","source","source_id","name_de","name_en","brand","barcode","base_unit",
   "kcal_100","protein_100","carbs_100","fat_100","sugar_100","fiber_100",
   "serving_size","quality_flags","source_url"]
def unpack(path):
 raw=Path(path).read_bytes()
 if not raw.startswith(MAGIC):raise RuntimeError("Invalid .dthpack")
 n=struct.unpack(">I",raw[7:11])[0]
 if not 0<n<8192:raise RuntimeError("Invalid header")
 meta=json.loads(raw[11:11+n]);data=raw[11+n:]
 if hashlib.sha256(data).hexdigest()!=meta["sha256"]:raise RuntimeError("Invalid source hash")
 return meta,data
def stable_hash(db):
 h=hashlib.sha256()
 for row in db.execute("SELECT "+",".join(PROTECTED)+" FROM foods ORDER BY id"):
  h.update(json.dumps(row,ensure_ascii=False,separators=(",",":"),default=str).encode())
  h.update(b"\n")
 return h.hexdigest()
def translated_map(names, model, batch_size=16):
 from transformers import pipeline
 print("Loading model",model,"unique_terms",len(names),flush=True)
 if not names:return {}
 pipe=pipeline("translation",model=model,device=-1)
 result={}
 for at in range(0,len(names),batch_size):
  chunk=names[at:at+batch_size]
  translated=pipe(chunk,max_length=160,truncation=True,batch_size=batch_size)
  for name,item in zip(chunk,translated):
   value=str(item["translation_text"]).strip()
   if value and len(value)<=200:result[name]=value
  if at%(16*50)==0:print("NAMES_PROGRESS",model,at,len(names),flush=True)
 del pipe
 return result
def run(args):
 meta,payload=unpack(args.source)
 code=meta["region"]
 if code not in LANG or meta["packID"]!="travel."+code.lower() or meta["source"]!="OpenFoodFacts":
  raise RuntimeError("Not a supported authentic country source pack")
 out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory() as folder:
  dbfile=Path(folder)/"working.sqlite";dbfile.write_bytes(payload)
  db=sqlite3.connect(dbfile)
  try:
   assert db.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
   before=stable_hash(db)
   rows=db.execute("SELECT id,name_de,name_en,name_he,search_text,brand FROM foods ORDER BY id").fetchall()
   english={}
   bridge_terms={}
   for id,local,en,he,search,brand in rows:
    if he and HE.search(he):continue
    source=str(en or "").strip()
    original=str(local or "").strip()
    if source and not (KA.search(source) or EL.search(source)):
     english[id]=source
    elif original:
     lang=LANG[code]
     # Georgian/Greek script is translated by native-language model.
     needs_bridge=(lang=="ka" and KA.search(original)) or (lang=="el" and EL.search(original)) or lang in ("es","it","fr")
     if needs_bridge:
      bridge_terms[id]=original
     else:english[id]=original
   if bridge_terms:
    model=BRIDGE[LANG[code]]
    translated=translated_map(sorted(set(bridge_terms.values())),model)
    for id,name in bridge_terms.items():
     bridged=translated.get(name)
     if bridged:english[id]=bridged
   unique=sorted(set(english.values()))
   labels=translated_map(unique,"Helsinki-NLP/opus-mt-en-he")
   changes=0
   for id,local,en,he,search,brand in rows:
    if id not in english:continue
    label=labels.get(english[id],"").strip()
    if not HE.search(label) or len(label)>160:continue
    # Keep English/original and brand words in FTS; only ADD Hebrew.
    db.execute("UPDATE foods SET name_he=?,search_text=? WHERE id=?",
               (label,str(search or "")+" "+label,id))
    changes+=1
   db.execute("DELETE FROM food_fts")
   db.execute("INSERT INTO food_fts(id,search_text) SELECT id,search_text FROM foods")
   db.commit()
   after=stable_hash(db)
   if before!=after:raise RuntimeError("Protected source rows changed during translation")
   count=db.execute("SELECT COUNT(*) FROM foods").fetchone()[0]
   fts=db.execute("SELECT COUNT(*) FROM food_fts").fetchone()[0]
   covered=db.execute("SELECT COUNT(*) FROM foods WHERE name_he GLOB '*[א-ת]*'").fetchone()[0]
   if count!=meta["count"] or fts!=count:raise RuntimeError("FTS/record mismatch")
   samples=db.execute("SELECT name_de,name_en,name_he FROM foods ORDER BY id LIMIT 100").fetchall()
   original_100=db.execute("SELECT name_de,name_en,name_he FROM foods WHERE name_he IS NOT NULL AND name_he!='' ORDER BY id LIMIT 20").fetchall()
   db.execute("VACUUM");db.close();db=None
   sql=dbfile.read_bytes()
   updated={**meta,"version":args.version,"sha256":hashlib.sha256(sql).hexdigest()}
   header=json.dumps(updated,ensure_ascii=False,separators=(",",":")).encode()
   if len(header)>8192:raise RuntimeError("Header too long")
   pack=out/Path(args.source).name
   pack.write_bytes(MAGIC+struct.pack(">I",len(header))+header+sql)
   qa={"region":code,"records":count,"hebrew_name_records":covered,"coverage":round(covered/count,5),
      "changed_labels":changes,"untranslated":count-covered,"source_rows_sha256_before":before,
      "source_rows_sha256_after":after,"translation_method":"Helsinki-NLP models (Apache-2.0)",
      "human_linguistic_qa_completed":False,"sample_first_100":samples,
      "sample_20_translated":original_100}
   (out/"hebrew-translation-report.json").write_text(json.dumps(qa,ensure_ascii=False,indent=2)+"\n")
   print("COUNTRY_HEBREW_QA",json.dumps({k:v for k,v in qa.items() if not k.startswith("sample_")},ensure_ascii=False),flush=True)
   if qa["coverage"]<args.min_coverage:raise RuntimeError("Hebrew coverage under threshold; no production release")
  finally:
   if db is not None: db.close()
if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("--source",required=True)
 p.add_argument("--out",required=True)
 p.add_argument("--version",default="1.0")
 p.add_argument("--min-coverage",type=float,default=.90)
 run(p.parse_args())
