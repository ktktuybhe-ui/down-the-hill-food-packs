#!/usr/bin/env python3
"""Download the public official BLS 4.0 archive using the download page's current URL.
Use persistent cookies for the BLS session-token links. Do not fake a source on error.
"""
import argparse
import http.cookiejar
import re
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
import zipfile

HOME = 'https://blsdb.de/download'
UA = 'DownTheHill-AustriaPack/0.2 (research; source: blsdb.de)'

class LinkParser(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            h=dict(attrs).get('href')
            if h:self.links.append(h)

def fetch_bls(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def fetch(url):
        last=None
        for attempt in range(3):
            try:
                r=opener.open(urllib.request.Request(url,headers={'User-Agent':UA,'Referer':HOME}),timeout=120)
                return r.read()
            except Exception as e:
                last=e
                if attempt<2:time.sleep(2**attempt)
        raise RuntimeError(f'Unable to retrieve official BLS data: {last}')
    p=LinkParser();p.feed(fetch(HOME).decode('utf-8','replace'))
    links=[urllib.parse.urljoin(HOME,x) for x in p.links if re.search(r'BLS_4_0_2025_DE\.zip',x,re.I)]
    if not links:raise RuntimeError('Official BLS 4.0 ZIP was not listed at '+HOME)
    data=fetch(links[0]);dest=out/'BLS_4_0_2025_DE.zip'
    if len(data)<10_000:raise RuntimeError('Official download unexpectedly small')
    dest.write_bytes(data)
    if not zipfile.is_zipfile(dest):
        dest.unlink();raise RuntimeError('Official download is not a ZIP. Do not produce synthetic pack.')
    print('Downloaded official source:',dest,round(len(data)/1024/1024,2),'MiB')
    return dest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',default='sources');args=parser.parse_args();fetch_bls(args.out)
