#!/usr/bin/env python3
from __future__ import annotations
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

BASE = 'https://my.flightradar24.com/Rampi/flights/date/asc'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'

def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': '*/*'})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
        print(url, r.status, len(data), r.geturl(), r.headers.get('content-type'))
        return data

raw = get(BASE)
text = raw.decode('utf-8', 'replace')
Path('rampi-page.html').write_text(text, encoding='utf-8')

lines=[]
lines.append(f'PAGE LENGTH {len(text)}')
for pat in ['fetch more','fetch-more','load more','load-more','ajax','offset','page','flights']:
    lines.append(f'\n=== {pat} ===')
    for m in list(re.finditer(pat, text, re.I))[:30]:
        lines.append(text[max(0,m.start()-400):m.end()+700])

scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)', text, re.I)
lines.append('\nSCRIPTS\n'+json.dumps(scripts, indent=2))
for src in scripts:
    url=urllib.parse.urljoin(BASE, html.unescape(src))
    try:
        js=get(url).decode('utf-8','replace')
    except Exception as e:
        lines.append(f'ERROR {url}: {e!r}')
        continue
    if any(x in js.lower() for x in ['fetch more','fetch-more','loadmore','load-more','/flights']):
        lines.append(f'\n=== JS {url} length={len(js)} ===')
        for pat in ['fetch more','fetch-more','loadmore','load-more','/flights','offset','pagination']:
            for m in list(re.finditer(pat,js,re.I))[:20]:
                lines.append(js[max(0,m.start()-500):m.end()+1000])

Path('rampi-inspect.txt').write_text('\n'.join(lines), encoding='utf-8')
print('\n'.join(lines)[:50000])
