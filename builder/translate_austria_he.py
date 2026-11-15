#!/usr/bin/env python3
"""Extend authentic Austrian .dthpack files with searchable Hebrew names ONLY.

Translation is automatically generated. Never changes nutritional values, provenance,
source IDs, original German/English names or serving sizes.
"""
import argparse, hashlib, json, re, sqlite3, struct, tempfile
from pathlib import Path

MAGIC=b'DTHPK1\n'
HE=re.compile('[\u0590-\u05ff]')
MODELS={'de':'Helsinki-NLP/opus-mt-de-he','en':'Helsinki-NLP/opus-mt-en-he'}
PROTECTED=('id','source','source_id','name_de','name_en','brand','barcode','base_unit',
 'kcal_100','protein_100','carbs_100','fat_100','sugar_100','fiber_100',
 'serving_size','quality_flags','source_url')

def read_pack(path):
    data=Path(path).read_bytes()
    if not data.startswith(MAGIC): raise ValueError('Bad magic')
    n=struct.unpack('>I',data[7:11])[0]
    if not 0<n<8192: raise ValueError('Bad header size')
    meta=json.loads(data[11:11+n]); payload=data[11+n:]
    if hashlib.sha256(payload).hexdigest()!=meta['sha256']:raise ValueError('Bad source SHA256')
    return meta,payload

def save_pack(path,meta,payload):
    meta={**meta,'sha256':hashlib.sha256(payload).hexdigest()}
    header=json.dumps(meta,ensure_ascii=False,separators=(',',':')).encode()
    if len(header)>=8192:raise ValueError('Header too large')
    Path(path).write_bytes(MAGIC+struct.pack('>I',len(header))+header+payload)

def protected_hash(conn):
    q='SELECT '+','.join(PROTECTED)+' FROM foods ORDER BY id'
    result=hashlib.sha256()
    for row in conn.execute(q):
        result.update(json.dumps(row,ensure_ascii=False,separators=(',',':')).encode())
        result.update(b'\n')
    return result.hexdigest()

def load_aliases(path):
    aliases={}
    for entry in json.loads(Path(path).read_text(encoding='utf-8')):
        de=entry.get('de','').strip().casefold()
        he=entry.get('he','').strip()
        if de and HE.search(he):aliases[de]=he
    return aliases

def translate_terms(terms,lang):
    from transformers import pipeline
    pipeline_obj=pipeline('translation',model=MODELS[lang],device=-1)
    output={}
    terms=sorted(terms)
    for pos in range(0,len(terms),16):
        subset=terms[pos:pos+16]
        candidates=pipeline_obj(subset,batch_size=16,max_length=160,truncation=True)
        for src,dst in zip(subset,candidates):
            name=dst.get('translation_text','').strip()
            if HE.search(name) and 0<len(name)<=180:output[src]=name
        if pos%640==0:print(f'{lang}: {pos}/{len(terms)} translated, valid {len(output)}',flush=True)
    return output

def build(src,dst,aliases,version,min_coverage):
    meta,sql=read_pack(src)
    if meta['source'] not in ('BLS-4.0','OpenFoodFacts'):raise ValueError('Not an Austria source')
    with tempfile.TemporaryDirectory() as temp:
        file=Path(temp)/'food.sqlite';file.write_bytes(sql)
        conn=sqlite3.connect(str(file))
        try:
            if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Corrupt source DB')
            original=protected_hash(conn)
            rows=conn.execute('SELECT id,name_de,name_en,name_he,search_text FROM foods').fetchall()
            count=len(rows)
            if count!=meta['count']:raise ValueError('Count mismatch')
            names={}; needed={'de':set(),'en':set()}
            for uid,de,en,he,search in rows:
                if he and HE.search(he):continue
                term=(de or en or '').strip()
                if not term:continue
                if term.casefold() in aliases: names[uid]=('alias',term)
                else:
                    lang='de' if de else 'en'
                    names[uid]=(lang,term); needed[lang].add(term)
            translations={k:translate_terms(v,k) if v else {} for k,v in needed.items()}
            added=0
            for uid,de,en,he,search in rows:
                choice=names.get(uid)
                if not choice:continue
                lang,term=choice
                value=aliases.get(term.casefold()) if lang=='alias' else translations[lang].get(term)
                if not value:continue
                conn.execute('UPDATE foods SET name_he=?,search_text=? WHERE id=?',
                             (value,search+' '+value,uid))
                added+=1
            conn.execute('DELETE FROM food_fts')
            conn.execute('INSERT INTO food_fts(id,search_text) SELECT id,search_text FROM foods')
            conn.commit()
            if protected_hash(conn)!=original:raise ValueError('Protected nutrition/provenance fields CHANGED')
            if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('New DB corrupt')
            if conn.execute('SELECT count(*) FROM food_fts').fetchone()[0]!=count:raise ValueError('FTS count mismatch')
            covered=conn.execute("SELECT count(*) FROM foods WHERE name_he GLOB '*[א-ת]*'").fetchone()[0]
            coverage=covered/count
            if coverage<min_coverage:raise ValueError(f'Hebrew coverage {coverage:.2%} below {min_coverage:.2%}')
            samples=conn.execute("SELECT name_de,name_en,name_he FROM foods WHERE name_he GLOB '*[א-ת]*' ORDER BY id LIMIT 100").fetchall()
            conn.execute('VACUUM');conn.close();conn=None
            output_sql=file.read_bytes()
            save_pack(dst,{**meta,'version':version},output_sql)
            read_pack(dst)
            return {'file':Path(dst).name,'source':meta['source'],'source_file_sha256':hashlib.sha256(Path(src).read_bytes()).hexdigest(),
                    'output_file_sha256':hashlib.sha256(Path(dst).read_bytes()).hexdigest(),
                    'rows':count,'hebrew_names':covered,'coverage':round(coverage,5),'new_names':added,
                    'models':MODELS,'model_license':'Apache-2.0','protected_rows_sha256':original,
                    'sample_first_100':samples}
        finally:
            if conn is not None:conn.close()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-dir',required=True)
    parser.add_argument('--out',required=True)
    parser.add_argument('--aliases',required=True)
    parser.add_argument('--version',required=True)
    parser.add_argument('--min-coverage',type=float,default=.95)
    args=parser.parse_args()
    dest=Path(args.out);dest.mkdir(parents=True,exist_ok=True)
    aliases=load_aliases(args.aliases)
    results=[]
    for name in ('Austria-BLS-4.0.dthpack','Austria-OpenFoodFacts.dthpack'):
        results.append(build(Path(args.source_dir)/name,dest/name,aliases,args.version,args.min_coverage))
    report={'status':'machine-translation-pending-human-review','summary':{'records':sum(i['rows'] for i in results),'hebrew_names':sum(i['hebrew_names'] for i in results)},'packs':results}
    (dest/'hebrew-translation-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report['summary'],ensure_ascii=False),flush=True)

if __name__=='__main__':main()
