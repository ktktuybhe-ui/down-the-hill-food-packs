#!/usr/bin/env python3
"""Validate checksums, SQLite integrity, record counts and metadata of an AT ZIP."""
import argparse
import hashlib
import io
import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path


def validate(path):
    with zipfile.ZipFile(path) as z:
        members=set(z.namelist())
        if any('/' in n or '\\' in n or n.startswith('.') for n in members):
            raise ValueError('Unexpected archive paths')
        m=json.loads(z.read('manifest.json'))
        if m.get('pack_id')!='travel.at' or m.get('schema')!=1:raise ValueError('Unexpected pack identity/schema')
        for f in m['files']:
            name=f['file']
            if name not in members:raise ValueError('Missing '+name)
            payload=z.read(name)
            if hashlib.sha256(payload).hexdigest()!=f['sha256']:raise ValueError('SHA256 mismatch '+name)
            with tempfile.TemporaryDirectory() as t:
                p=Path(t)/name
                p.write_bytes(payload)
                con=sqlite3.connect(f'file:{p}?mode=ro',uri=True)
                try:
                    if con.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Broken SQLite '+name)
                    count=con.execute('SELECT count(*) FROM foods').fetchone()[0]
                    if count!=f['records']:raise ValueError('Wrong record count '+name)
                    bad=con.execute('''SELECT count(*) FROM foods WHERE kcal_100 IS NULL OR
                         fat_100 IS NULL OR carbs_100 IS NULL OR protein_100 IS NULL''').fetchone()[0]
                    if bad:raise ValueError('Missing core nutrition '+name)
                finally: con.close()
    return {'pack_id':m['pack_id'],'files':[(f['file'],f['records']) for f in m['files']],'valid':True}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('pack');a=p.parse_args()
    print(json.dumps(validate(a.pack),ensure_ascii=False,indent=2))
