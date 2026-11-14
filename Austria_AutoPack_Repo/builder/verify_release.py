#!/usr/bin/env python3
"""Verify real source pack counts and integrity before publishing.
Print a machine-readable report; failure prevents GitHub release.
"""
import argparse
import hashlib
import json
import sqlite3
import struct
from pathlib import Path
from export_dthpack import verify, MAGIC

def check_pack(path, minimum, expected_source):
    path=Path(path)
    meta=verify(path)
    if meta['source']!=expected_source:raise ValueError(f'Bad source in {path.name}')
    if meta['count']<minimum:raise ValueError(f'{path.name}: {meta["count"]} foods < minimum {minimum}')
    raw=path.read_bytes();mlen=struct.unpack('>I',raw[len(MAGIC):len(MAGIC)+4])[0];payload=raw[len(MAGIC)+4+mlen:]
    conn=sqlite3.connect(':memory:')
    try:
        conn.deserialize(payload)
        if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Invalid SQLite integrity')
        count=conn.execute('SELECT COUNT(*) FROM foods').fetchone()[0]
        empty=conn.execute("SELECT COUNT(*) FROM foods WHERE search_text='' OR name_de IS NULL OR kcal_100 IS NULL OR protein_100 IS NULL OR carbs_100 IS NULL OR fat_100 IS NULL").fetchone()[0]
        bad=conn.execute('SELECT COUNT(*) FROM foods WHERE kcal_100<0 OR kcal_100>950 OR protein_100<0 OR fat_100<0 OR carbs_100<0').fetchone()[0]
        if count!=meta['count'] or empty or bad:raise ValueError('Missing/invalid fields or count mismatch')
        # Verify source separation and proper FTS index.
        if conn.execute('SELECT COUNT(*) FROM food_fts').fetchone()[0]!=count:raise ValueError('FTS count mismatch')
        baddies=conn.execute('SELECT COUNT(*) FROM foods WHERE source!=?',(expected_source,)).fetchone()[0]
        if baddies:raise ValueError('Pack contains mixed-source records')
    finally:conn.close()
    return {'file':path.name,'records':count,'bytes':path.stat().st_size,'sha256_file':hashlib.sha256(path.read_bytes()).hexdigest(),
            'source':expected_source,'license':meta['license'],'sourceURL':meta['sourceURL'],'version':meta['version']}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--folder',default='dist');ap.add_argument('--bls-min',type=int,default=6000);ap.add_argument('--off-min',type=int,default=3000);args=ap.parse_args()
    folder=Path(args.folder)
    files=[check_pack(folder/'Austria-BLS-4.0.dthpack',args.bls_min,'BLS-4.0'),
           check_pack(folder/'Austria-OpenFoodFacts.dthpack',args.off_min,'OpenFoodFacts')]
    output={'region':'AT','schema':1,'status':'verified','files':files,
            'licenses':{'BLS-4.0':'CC BY 4.0','OpenFoodFacts':'ODbL 1.0'}}
    (folder/'pack-index.json').write_text(json.dumps(output,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(output,indent=2,ensure_ascii=False))
