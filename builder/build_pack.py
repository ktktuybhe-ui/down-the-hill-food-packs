#!/usr/bin/env python3
"""Build separate, auditable offline food databases for an Austrian travel pack.

Input: BLS 4.0 Excel (.xlsx or official .zip); Open Food Facts JSONL(.gz) or TSV/CSV(.gz).
Output: isolated SQLite FTS5 databases, aliases report, manifest, checksums and pack ZIP.
No nutrition values are synthesized. Sources must be supplied by the operator.
"""
import argparse
import csv
import gzip
import hashlib
import heapq
import io
import json
import re
import shutil
import sqlite3
import sys
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

FIELDS = ('kcal','protein','carbs','fat','sugar','fiber')
CREATE = """
CREATE TABLE foods (
 id TEXT PRIMARY KEY, source TEXT NOT NULL, source_id TEXT NOT NULL,
 name_de TEXT, name_en TEXT, name_he TEXT, brand TEXT, barcode TEXT,
 base_unit TEXT NOT NULL DEFAULT 'g',
 kcal_100 REAL, protein_100 REAL, carbs_100 REAL, fat_100 REAL,
 sugar_100 REAL, fiber_100 REAL, serving_size REAL,
 search_text TEXT NOT NULL, quality_flags TEXT NOT NULL DEFAULT '[]',
 source_url TEXT NOT NULL
);
CREATE VIRTUAL TABLE food_fts USING fts5(
 id UNINDEXED, search_text, tokenize='unicode61 remove_diacritics 2'
);
CREATE INDEX idx_food_barcode ON foods(barcode);
CREATE INDEX idx_food_source ON foods(source);
"""

def norm(v):
    t=unicodedata.normalize('NFKC',str(v or '')).casefold().strip()
    t=t.replace('ß','ss').replace('ä','ae').replace('ö','oe').replace('ü','ue')
    return re.sub(r'[^\w\u0590-\u05ff]+',' ',t).strip()

def number(x):
    try:
        if x is None or str(x).strip() in ('','-','—','n.a.','nan'):return None
        f=float(str(x).strip().replace(',','.'))
        return f if abs(f)<1e9 and f==f else None
    except (ValueError,TypeError):return None

def check(n):
    for f in ('kcal','protein','carbs','fat'):
        if n.get(f) is None:return False
    return (0<=n['kcal']<=950 and 0<=n['protein']<=100 and
            0<=n['carbs']<=100 and 0<=n['fat']<=100)

def quality(n):
    flags=[]
    for k in ('sugar','fiber'):
        if n.get(k) is None:flags.append('missing_'+k)
    calc=4*n['protein']+4*n['carbs']+9*n['fat']
    # Alcohol/fibre and European labeling can legitimately affect this relationship.
    if n['kcal']>25 and abs(calc-n['kcal'])/n['kcal']>0.35:
        flags.append('energy_macro_gap_review')
    return flags

def alias_for(name, aliases):
    name=norm(name)
    found=[]
    for a in aliases:
        de=norm(a['de'])
        # The identity is tied to matching source food/product names, never fabricated.
        if de and (de==name or len(de)>=6 and re.search(r'(?<!\w)'+re.escape(de)+r'(?!\w)',name)):
            found.append(a)
    return found

def aliases_for_name(name, aliases):
    found=alias_for(name,aliases)
    he=' · '.join(dict.fromkeys(a['he'] for a in found)) if found else ''
    extra=[]
    for a in found:
        extra.extend([a['de'],a['en'],a['he']]+a.get('aliases_he',[]))
    return he,extra,[a['de'] for a in found]

def insert_records(path, rows):
    con=sqlite3.connect(str(path))
    try:
        con.executescript(CREATE)
        count=0
        with con:
            for rec in rows:
                n=rec['n']
                vals=(rec['id'],rec['source'],rec['source_id'],rec.get('de'),
                    rec.get('en'),rec.get('he'),rec.get('brand'),rec.get('barcode'),
                    rec.get('base_unit','g'),*[n.get(k) for k in FIELDS],
                    rec.get('serving'),rec['search'],json.dumps(rec['flags'],ensure_ascii=False),rec['url'])
                con.execute('INSERT OR IGNORE INTO foods VALUES ('+','.join('?'*len(vals))+')',vals)
                if con.execute('SELECT changes()').fetchone()[0]:
                    con.execute('INSERT INTO food_fts(id,search_text) VALUES (?,?)',(rec['id'],rec['search']))
                    count+=1
        con.execute('PRAGMA optimize')
        con.commit()
        return count
    finally: con.close()

def iter_bls(path, aliases, mode):
    try:from openpyxl import load_workbook
    except ImportError:raise RuntimeError('Missing dependency: pip install openpyxl')
    path=Path(path)
    if path.suffix.lower()=='.zip':
        with zipfile.ZipFile(path) as z:
            names=[n for n in z.namelist() if n.lower().endswith('.xlsx') and not n.split('/')[-1].startswith('~$')]
            names=[n for n in names if not any(t in n.lower() for t in ('mapping','code_map','_info','errata'))]
            if not names:raise RuntimeError('No BLS main XLSX inside ZIP')
            # Official archives can rename the workbook. Prefer the largest spreadsheet.
            selected=max(names,key=lambda n:z.getinfo(n).file_size)
            print('Selected BLS workbook:',selected)
            excel=io.BytesIO(z.read(selected))
            yield from iter_bls_workbook(load_workbook(excel,read_only=True,data_only=True),aliases,mode)
    else:yield from iter_bls_workbook(load_workbook(path,read_only=True,data_only=True),aliases,mode)

def iter_bls_workbook(wb,aliases,mode):
    ws=wb.active
    rows=ws.iter_rows(values_only=True)
    header=None
    for row in rows:
        if len(row)>3 and str(row[0] or '').strip().casefold().replace('_',' ').replace('-',' ') in ('bls code','blscode'):
            header=row
            break
    if header is None:raise RuntimeError('BLS header not found: expected BLS Code in column A')
    cols={}
    for i,h in enumerate(header):
        h=str(h or '').strip()
        m=re.match(r'^([A-Z][A-Z0-9]+)\s+',h)
        if m and ('[g/100g]' in h or '[kcal/100g]' in h or '[kj/100g]' in h.lower()):
            cols.setdefault(m.group(1),i)
    required={'ENERCC','PROT625','CHO','FAT'}
    if not required.issubset(cols):raise RuntimeError('BLS nutrient column discovery failed. Found '+','.join(sorted(cols)))
    for row in rows:
        if len(row)<3 or not row[0] or not row[1]:continue
        code=str(row[0]).strip();de=str(row[1]).strip();en=str(row[2] or '').strip()
        he,extra,_=aliases_for_name(de,aliases)
        if mode=='austria-only' and not extra:continue
        def v(key):return number(row[cols[key]]) if key in cols and len(row)>cols[key] else None
        n={'kcal':v('ENERCC'),'protein':v('PROT625'),'carbs':v('CHO'),
           'fat':v('FAT'),'sugar':v('SUGAR'),'fiber':v('FIBT')}
        if not check(n):continue
        search=' '.join(x for x in [de,en,he,*extra] if x)
        yield {'id':'bls:'+code,'source':'BLS-4.0','source_id':code,'de':de,
            'en':en,'he':he,'n':n,'search':search,'flags':quality(n),
            'url':'https://blsdb.de/'}

def open_text(path):
    p=Path(path)
    return gzip.open(p,'rt',encoding='utf-8-sig',errors='replace',newline='') if p.suffix=='.gz' else open(p,encoding='utf-8-sig',errors='replace',newline='')

def iter_off_raw(path):
    with open_text(path) as f:
        base=Path(path).name.lower()
        if '.jsonl' in base or '.ndjson' in base:
            for line in f:
                try:yield json.loads(line)
                except json.JSONDecodeError:continue
        else:
            first=f.readline()
            delim='\t' if first.count('\t')>first.count(',') else ','
            f.seek(0)
            for row in csv.DictReader(f,delimiter=delim):yield row

def off_record(p,aliases):
    country=p.get('countries_tags') or p.get('countries_tags_en') or p.get('countries') or ''
    if isinstance(country,list):country=' '.join(map(str,country))
    if not re.search(r'(?i)(?:\b|:)austria\b|(?:\b|:)osterreich\b|österreich',str(country)):return None
    code=str(p.get('code') or '').strip()
    if not code or not re.fullmatch(r'\d{8,14}',code):return None
    de=str(p.get('product_name_de') or '').strip()
    en=str(p.get('product_name_en') or '').strip()
    primary=str(p.get('product_name') or '').strip()
    if not (primary or de or en):return None
    if not de:de=primary
    ns=p.get('nutriments') if isinstance(p.get('nutriments'),dict) else p
    def field(*names):
        for s in names:
            v=number(ns.get(s))
            if v is not None:return v
        return None
    # Never combine kcal per 100 ml with proteins per 100 g: different bases.
    suggested=str(p.get('nutrition_data_per') or '').lower()
    prefer=['100ml','100g'] if 'ml' in suggested else ['100g','100ml']
    n=None;base_unit='g'
    for suffix in prefer:
        kcal=field('energy-kcal_'+suffix,'energy-kcal_'+suffix+'_value')
        if kcal is None:
            kj=field('energy-kj_'+suffix)
            kcal=kj/4.184 if kj is not None else None
        proposed={'kcal':kcal,'protein':field('proteins_'+suffix),
                  'carbs':field('carbohydrates_'+suffix),
                  'fat':field('fat_'+suffix),
                  'sugar':field('sugars_'+suffix),
                  'fiber':field('fiber_'+suffix)}
        if check(proposed):
            n=proposed;base_unit='ml' if suffix=='100ml' else 'g'
            break
    if n is None:return None
    if not check(n):return None
    he,extra,_=aliases_for_name(' '.join([de,en,primary]),aliases)
    brand=str(p.get('brands') or '').strip()
    search=' '.join(x for x in [primary,de,en,he,brand,*extra] if x)
    serving=number(p.get('serving_quantity'))
    scans=number(p.get('scans_n')) or 0
    completeness=number(p.get('completeness')) or 0
    score=scans+100*completeness+(10 if he else 0)
    rec={'id':'off:'+code,'source':'OpenFoodFacts','source_id':code,
        'de':de,'en':en,'he':he,'brand':brand,'barcode':code,'base_unit':base_unit,
        'n':n,'serving':serving,'search':search,'flags':quality(n),
        'url':'https://world.openfoodfacts.org/product/'+code}
    return score,rec

def select_off(path,aliases,max_off):
    # High-scanned products win, not arbitrary first rows from a bulk dump.
    heap=[];seen=set();idx=0
    for raw in iter_off_raw(path):
        parsed=off_record(raw,aliases)
        if not parsed:continue
        score,rec=parsed
        if rec['id'] in seen:continue
        seen.add(rec['id']);idx+=1
        item=(score,idx,rec)
        if max_off<=0:heap.append(item)
        elif len(heap)<max_off:heapq.heappush(heap,item)
        elif score>heap[0][0]:heapq.heapreplace(heap,item)
    return (rec for _,__,rec in sorted(heap,reverse=True))

def write_manifest(out,entries,mode,aliases_count):
    files=[]
    for name,count,license_name,source_url in entries:
        p=out/name
        files.append({'file':name,'records':count,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
            'license':license_name,'source_url':source_url})
    manifest={'pack_id':'travel.at','schema':1,'region':'AT','title':'Austria Offline Food Pack',
        'created_utc':datetime.now(timezone.utc).isoformat(),
        'type':'offline_search_provider_not_user_history','bls_mode':mode,
        'localization':'BLS provides German+English; Hebrew names only when safely curated',
        'alias_terms':aliases_count,'files':files,
        'terms':'BLS: CC BY 4.0 (credit Max Rubner-Institut). OFF: ODbL 1.0 (attribution/share-alike obligations). Source datasets remain separated.',
        'safety':'Removing this pack must never delete saved food entries or historical meals; meals snapshot nutrition and display text.'}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--bls',help='Official BLS 4.0 ZIP/XLSX file')
    parser.add_argument('--off',help='Open Food Facts product CSV/TSV/JSONL, optionally .gz')
    parser.add_argument('--max-off',type=int,default=3000)
    parser.add_argument('--bls-mode',choices=['all','austria-only'],default='all',help='all (default): DACH reference foods; austria-only: alias-matched dishes only')
    parser.add_argument('--version',default='1',help='Pack version visible in Down the Hill')
    parser.add_argument('--out',default='dist')
    args=parser.parse_args()
    if not args.bls and not args.off:parser.error('Provide at least one source file with --bls and/or --off; no nutrition facts are fabricated')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    aliases=json.loads((Path(__file__).parent/'austria_aliases.json').read_text('utf-8'))
    entries=[]
    if args.bls:
        dest='bls.sqlite';count=insert_records(out/dest,iter_bls(args.bls,aliases,args.bls_mode))
        entries.append((dest,count,'CC BY 4.0','https://blsdb.de/download'))
    if args.off:
        dest='off_austria.sqlite';count=insert_records(out/dest,select_off(args.off,aliases,args.max_off))
        entries.append((dest,count,'ODbL 1.0','https://world.openfoodfacts.org/data'))
    manifest=write_manifest(out,entries,args.bls_mode,len(aliases))
    from export_dthpack import export
    import_files=[]
    for file_name,_,_,_ in entries:
        imported = out/("Austria-BLS-4.0.dthpack" if file_name == "bls.sqlite" else "Austria-OpenFoodFacts.dthpack")
        import_files.append(export(out/file_name,imported,version=args.version))
    (out/"installable_packs.json").write_text(json.dumps(import_files,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'austria_aliases.json').write_text(json.dumps(aliases,ensure_ascii=False,indent=2),encoding='utf-8')
    zip_name=out/'DownTheHill-Austria-offline-pack-v1.zip'
    with zipfile.ZipFile(zip_name,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as z:
        for f in ('manifest.json','austria_aliases.json',*(e[0] for e in entries)):
            z.write(out/f,arcname=f)
    print(json.dumps({'pack':str(zip_name),'installable':import_files,'sources':manifest['files'],'size_bytes':zip_name.stat().st_size},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
