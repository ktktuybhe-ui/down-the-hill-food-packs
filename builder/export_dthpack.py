"""Self-contained, inspectable single-source .dthpack files for iOS Files import.

Files are NOT ZIP: 7-byte magic + 4-byte BE JSON length + JSON metadata +
raw read-only SQLite. Separate BLS and OFF files preserve provenance/licensing.
"""
import hashlib
import json
import sqlite3
import struct
from pathlib import Path

MAGIC=b'DTHPK1\n'
SOURCES={'bls.sqlite':('BLS-4.0','BLS 4.0 · גרמניה','CC BY 4.0','https://blsdb.de/download'),
         'off_austria.sqlite':('OpenFoodFacts','Open Food Facts · אוסטריה','ODbL 1.0','https://world.openfoodfacts.org/data')}

def export(src, destination, *, version='1'):
    src=Path(src);destination=Path(destination)
    if src.name not in SOURCES:raise ValueError('Unexpected source file name')
    source,title,license_name,source_url=SOURCES[src.name]
    con=sqlite3.connect(f'file:{src}?mode=ro',uri=True)
    try:
        if con.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Invalid SQLite')
        count=con.execute('SELECT COUNT(*) FROM foods').fetchone()[0]
        if not count: raise ValueError('Empty nutrition database not installable')
    finally: con.close()
    sqlite=src.read_bytes()
    meta={'packID':'travel.at','region':'AT','source':source,'version':version,
          'title':title,'license':license_name,'sourceURL':source_url,'schema':1,
          'count':count,'sha256':hashlib.sha256(sqlite).hexdigest()}
    text=json.dumps(meta,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    if len(text)>=8192:raise ValueError('Header too large')
    destination.write_bytes(MAGIC+struct.pack('>I',len(text))+text+sqlite)
    return {'file':str(destination),'source':source,'count':count,'size':destination.stat().st_size,'sha256':meta['sha256']}

def verify(file):
    raw=Path(file).read_bytes()
    if not raw.startswith(MAGIC):raise ValueError('Not a food pack')
    size=struct.unpack('>I',raw[7:11])[0]
    if not 0<size<8192:raise ValueError('Invalid manifest size')
    meta=json.loads(raw[11:11+size]);payload=raw[11+size:]
    if hashlib.sha256(payload).hexdigest()!=meta['sha256']:raise ValueError('Checksum mismatch')
    if meta['source'] not in ('BLS-4.0','OpenFoodFacts'):raise ValueError('Unknown source')
    return meta
