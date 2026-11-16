#!/usr/bin/env python3
"""Apply machine-generated Hebrew NAME labels to authentic country .dthpacks.
Preserves all nutrient data, source IDs, originals, serving sizes, source metadata.
Reports exactly which labels are machine-translated. Not human linguistic QA.
"""
import argparse,hashlib,json,re,sqlite3,struct,tempfile,random
from pathlib import Path

MAGIC=b"DTHPK1\n"
HE=re.compile("[א-ת]")
KA=re.compile("[\u10a0-\u10ff]")
EL=re.compile("[\u0370-\u03ff\u1f00-\u1fff]")
CYRILLIC=re.compile("[\u0400-\u052f]")
UKRAINIAN=re.compile("[іїєґ]",re.IGNORECASE)
LANG={"GE":"ka","GR":"el","ES":"es","IT":"it","FR":"fr"}
BRIDGE={"ka":"Helsinki-NLP/opus-mt-ka-en","el":"Helsinki-NLP/opus-mt-grk-en",
        "ru":"Helsinki-NLP/opus-mt-ru-en","uk":"Helsinki-NLP/opus-mt-uk-en",
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
HEBREW_FALLBACK = "facebook/m2m100_418M"
HEBREW_FALLBACK_REVISION = "55c2e61bbf05dfb8d7abccdc3fae6fc8512fd636"


def direct_hebrew(by_language):
 from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
 import torch

 model = M2M100ForConditionalGeneration.from_pretrained(HEBREW_FALLBACK, revision=HEBREW_FALLBACK_REVISION)
 tokenizer = M2M100Tokenizer.from_pretrained(HEBREW_FALLBACK, revision=HEBREW_FALLBACK_REVISION)
 result = {}
 with torch.inference_mode():
  for language, terms in by_language.items():
   tokenizer.src_lang = language
   unique = sorted(set(terms.values()))
   translated = {}
   for start in range(0, len(unique), 16):
    chunk = unique[start:start+16]
    inputs = tokenizer(chunk, return_tensors="pt", padding=True, truncation=True, max_length=160)
    outputs = model.generate(**inputs, forced_bos_token_id=tokenizer.get_lang_id("he"), max_new_tokens=100)
    translated.update(zip(chunk, tokenizer.batch_decode(outputs, skip_special_tokens=True), strict=True))
   result.update({id: translated[name].strip() for id, name in terms.items()})
 return result


def valid_hebrew(label):
 return bool(HE.search(label)) and len(label) <= 160


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
    name=source or original
    if not name:continue
    if KA.search(name):
     language="ka"
    elif EL.search(name):
     language="el"
    elif CYRILLIC.search(name):
     language="uk" if UKRAINIAN.search(name) else "ru"
    elif LANG[code] in ("es","it","fr") and not source:
     language=LANG[code]
    else:
     english[id]=name
     continue
    bridge_terms.setdefault(language,{})[id]=name
   for language,terms in bridge_terms.items():
    translated=translated_map(sorted(set(terms.values())),BRIDGE[language])
    for id,name in terms.items():
     bridged=translated.get(name)
     if bridged:english[id]=bridged
   unique=sorted(set(english.values()))
   labels=translated_map(unique,"Helsinki-NLP/opus-mt-en-he")
   labels_by_id={id:labels.get(name,"").strip() for id,name in english.items()}
   fallback={}
   bridged_ids=set()
   for language,terms in bridge_terms.items():
    bridged_ids.update(terms)
    missing={id:name for id,name in terms.items() if not valid_hebrew(labels_by_id.get(id,""))}
    if missing:fallback[language]=missing
   missing={id:name for id,name in english.items()
            if id not in bridged_ids and not valid_hebrew(labels_by_id.get(id,""))}
   if missing:fallback["en"]=missing
   if fallback:labels_by_id.update(direct_hebrew(fallback))
   changes=0
   for id,local,en,he,search,brand in rows:
    label=labels_by_id.get(id,"")
    if not valid_hebrew(label):continue
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
   if not count or count!=meta["count"] or fts!=count:raise RuntimeError("FTS/record mismatch")
   samples=db.execute("SELECT name_de,name_en,name_he FROM foods ORDER BY id LIMIT 100").fetchall()
   original_100=db.execute("SELECT name_de,name_en,name_he FROM foods WHERE name_he IS NOT NULL AND name_he!='' ORDER BY id LIMIT 20").fetchall()
   db.execute("VACUUM");db.close();db=None
   sql=dbfile.read_bytes()
   updated={**meta,"version":args.version,"sha256":hashlib.sha256(sql).hexdigest()}
   header=json.dumps(updated,ensure_ascii=False,separators=(",",":")).encode()
   if len(header)>8192:raise RuntimeError("Header too long")
   qa={"region":code,"records":count,"hebrew_name_records":covered,"coverage":round(covered/count,5),
      "changed_labels":changes,"untranslated":count-covered,"source_rows_sha256_before":before,
      "source_rows_sha256_after":after,"translation_method":"Helsinki-NLP models (Apache-2.0)" +
      ("; facebook/m2m100_418M (MIT) for missing labels" if fallback else ""),
      "human_linguistic_qa_completed":False,"sample_first_100":samples,
      "sample_20_translated":original_100}
   qa["sample_untranslated"] = [row[:3] for row in rows if not valid_hebrew(str(row[3] or ""))
                               and not valid_hebrew(labels_by_id.get(row[0], ""))][:100]
   (out/"hebrew-translation-report.json").write_text(json.dumps(qa,ensure_ascii=False,indent=2)+"\n")
   print("COUNTRY_HEBREW_QA",json.dumps({k:v for k,v in qa.items() if not k.startswith("sample_")},ensure_ascii=False),flush=True)
   if covered/count<args.min_coverage:raise RuntimeError("Hebrew coverage under threshold; no production release")
   pack=out/Path(args.source).name
   pack.write_bytes(MAGIC+struct.pack(">I",len(header))+header+sql)
  finally:
   if db is not None: db.close()
if __name__=="__main__":
 p=argparse.ArgumentParser()
 p.add_argument("--source",required=True)
 p.add_argument("--out",required=True)
 p.add_argument("--version",default="1.0")
 p.add_argument("--min-coverage",type=float,default=.90)
 run(p.parse_args())
