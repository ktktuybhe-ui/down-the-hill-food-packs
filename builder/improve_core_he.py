#!/usr/bin/env python3
"""Conservative USDA Hebrew-label correction, preserving all nutrients and source identities.
This does NOT constitute human review of all machine-translated labels.
"""
import argparse, hashlib, json, re, sqlite3, struct
from pathlib import Path
MAGIC=b'DTHPK1\n'
SOURCE_SHA='f740753c26dd6f977bce7aaad16f0d3ce5f09a337a83752de4b4e2ce39abeed9'
PROTECTED=('id','source','source_id','name_de','name_en','brand','barcode','base_unit',
           'kcal_100','protein_100','carbs_100','fat_100','sugar_100','fiber_100',
           'serving_size','quality_flags','source_url')

def protected_hash(db):
    h=hashlib.sha256()
    for row in db.execute('SELECT '+','.join(PROTECTED)+' FROM foods ORDER BY id'):
        h.update(json.dumps(row,ensure_ascii=False,separators=(',',':')).encode())
        h.update(b'\n')
    return h.hexdigest()

def repair(en,he):
    old=he or ''
    if not old:return old,None
    s=old;reason=[];e=en.lower()
    if re.search(r'\bturkey\b',e) and not re.search(r'\bturkey hill\b',e) and 'טורקיה' in s:
        s=s.replace('טורקיה','הודו');reason.append('turkey-food-not-country')
    if 'buttermilk' in e and 'חלב חמאה' in s:
        s=s.replace('חלב חמאה','רוויון');reason.append('buttermilk')
    if 'unbleached' in e:
        before=s
        for bad in ('ללא בלם','לא מדמם','ללא דימום'):
            s=s.replace(bad,'לא מולבן')
        if 'unenriched' in e:s=s.replace('לא עשיר','לא מועשר')
        if 'enriched' in e and 'unenriched' not in e:s=s.replace('העשיר','מועשר')
        if s!=before:reason.append('unbleached-not-bleeding')
    if 'glutinous' in e and 'עגום' in s:
        s=s.replace('עגום','דביק');reason.append('sticky-rice')
    if 'sweet potato' in e:
        before=s
        s=s.replace('תפוחי אדמה מתוקים','בטטות').replace('תפוח אדמה מתוק','בטטה')
        if s!=before:reason.append('sweet-potato')
    if 'slider' in e and 'מחוון' in s:
        if e.startswith('cheeseburger slider'):s='מיני צ׳יזבורגר'
        elif e.startswith('hamburger slider'):s='מיני המבורגר'
        else:s=en
        if 'from fast food' in e:s+=' ממזון מהיר'
        reason.append('slider-means-mini-burger')
    if 'ice cream' in e and re.search(r'\blight\b',e):
        before=s
        s=re.sub(r'(?<![א-ת])אור(?=[,\.\s]|$)','לייט',s)
        if s!=before:reason.append('light-ice-cream')
    if (e.startswith('ham, turkey') or e.startswith('turkey ham')) and 'חזיר' in s:
        s=en;reason.append('turkey-ham-english-fallback')
    if e.startswith('cracker barrel') and ('חבית' in s or 'קוקר' in s):
        s=en;reason.append('brand-preserve-english')
    if 'Name' in s and 'Name' not in en:
        s=en;reason.append('machine-artifact-english-fallback')
    return s,','.join(reason) if reason and s!=old else None

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',required=True)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    raw=Path(args.input).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCE_SHA:raise ValueError('Source Release digest mismatch')
    if raw[:7]!=MAGIC:raise ValueError('Invalid pack magic')
    l=struct.unpack('>I',raw[7:11])[0]
    if l<=0 or l>=8192:raise ValueError('Invalid metadata size')
    meta=json.loads(raw[11:11+l]);payload=raw[11+l:]
    if meta['packID']!='core.global' or meta['count']!=13535:raise ValueError('Wrong core')
    if hashlib.sha256(payload).hexdigest()!=meta['sha256']:raise ValueError('Payload checksum mismatch')
    db=sqlite3.connect(':memory:');db.deserialize(payload)
    if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Input SQLite integrity failed')
    baseline=protected_hash(db);changes=[]
    for food_id,en,he in db.execute('SELECT id,name_en,name_he FROM foods').fetchall():
        new,reason=repair(en or '',he or '')
        if reason:
            db.execute('UPDATE foods SET name_he=?, search_text=? WHERE id=?',
                       (new,(en or '')+' '+new,food_id))
            changes.append({'id':food_id,'english':en,'original_hebrew':he,
                            'revised_hebrew_or_english':new,'reason':reason})
    db.execute('DELETE FROM food_fts')
    db.execute('INSERT INTO food_fts(id,search_text) SELECT id,search_text FROM foods')
    db.commit()
    if protected_hash(db)!=baseline:raise ValueError('Nutritional/provenance fields modified')
    if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Output SQLite invalid')
    if db.execute('SELECT count(*) FROM food_fts').fetchone()[0]!=13535:raise ValueError('FTS mismatch')
    count=db.execute("SELECT count(*) FROM foods WHERE name_he GLOB '*[א-ת]*'").fetchone()[0]
    if count/13535<.98:raise ValueError('Hebrew search coverage too low')
    if len(changes)<200:raise ValueError('Expected 200+ reviewed rule matches')
    db.execute('VACUUM')
    patched=db.serialize();db.close()
    meta={**meta,'version':'core-usda-2026.1-he-fixes.1','sha256':hashlib.sha256(patched).hexdigest()}
    header=json.dumps(meta,ensure_ascii=False,separators=(',',':')).encode()
    if len(header)>=8192:raise ValueError('Header too large')
    dest=Path(args.out);dest.mkdir(parents=True,exist_ok=True)
    output=dest/'International-Core.dthpack'
    output.write_bytes(MAGIC+struct.pack('>I',len(header))+header+patched)
    check=hashlib.sha256(output.read_bytes()).hexdigest()
    qa={'status':'corrected-machine-translation-candidate-human-QA-pending',
        'source_rows':13535,'hebrew_rows':count,'coverage':round(count/13535,6),
        'changed_rows':len(changes),'original_sha256':SOURCE_SHA,
        'updated_sha256':check,'protected_columns_sha256':baseline,
        'preserved_fields':list(PROTECTED),'human_translation_review_completed':False,
        'changes':changes}
    (dest/'hebrew-quality-review.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (dest/'pack-index.json').write_text(json.dumps({
        'region':'GLOBAL','schema':1,'status':'candidate-pending-human-QA',
        'files':[{'file':'International-Core.dthpack','packID':'core.global',
                  'source':'USDA-FoodDataCentral','records':13535,'bytes':output.stat().st_size,
                  'sha256_file':check,'license':'CC0 1.0'}]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'source_rows':13535,'revised_names':len(changes),
                      'hebrew_names':count,'sha256':check},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
