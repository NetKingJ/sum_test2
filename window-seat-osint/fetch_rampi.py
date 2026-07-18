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
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': '*/*', 'Referer': BASE})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
        print(url, r.status, len(data), r.geturl(), r.headers.get('content-type'))
        return data

def clean(v):
    if v is None:
        return ''
    s = html.unescape(str(v))
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

raw = get(BASE)
text = raw.decode('utf-8', 'replace')
Path('rampi-page.html').write_text(text, encoding='utf-8')

# Save scripts used by the page, including the pagination endpoint implementation.
scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)', text, re.I)
for num, src in enumerate(scripts):
    url = urllib.parse.urljoin(BASE, html.unescape(src))
    try:
        js = get(url).decode('utf-8', 'replace')
    except Exception as e:
        print('script error', url, repr(e))
        continue
    outname = f'rampi-script-{num}.js'
    if 'profile-flights' in url:
        outname = 'rampi-profile-flights.js'
    elif '/main.js' in url:
        outname = 'rampi-main.js'
    Path(outname).write_text(js, encoding='utf-8')

# Initial page includes rows 0..49. The public JSON endpoint returns subsequent batches.
row_numbers = [int(x) for x in re.findall(r'data-row-number=["\'](\d+)["\']', text)]
last_row = max(row_numbers) if row_numbers else 49
all_api_rows = []
for batch in range(100):
    url = f'https://my.flightradar24.com/public-scripts/flight-list/Rampi/{last_row}/date/asc'
    data = json.loads(get(url).decode('utf-8', 'replace'))
    if not data:
        print('end at batch', batch, 'last row', last_row)
        break
    keys = sorted((int(k) for k in data.keys())) if isinstance(data, dict) else list(range(len(data)))
    for key in keys:
        row = data[str(key)] if isinstance(data, dict) and str(key) in data else data[key]
        # Endpoint schema from profile-flights.js:
        # date, flight, from, to, distance, departure, arrival, airline,
        # aircraft, registration, seat, note, icons
        values = list(row) + [''] * max(0, 13 - len(row))
        all_api_rows.append({
            'row_number': key,
            'date': clean(values[0]),
            'flight': clean(values[1]),
            'from': clean(values[2]),
            'to': clean(values[3]),
            'distance': clean(values[4]),
            'departure': clean(values[5]),
            'arrival': clean(values[6]),
            'airline': clean(values[7]),
            'aircraft': clean(values[8]),
            'registration': clean(values[9]),
            'seat': clean(values[10]),
            'note': clean(values[11]),
            'icons': clean(values[12]),
            'raw': values,
        })
    new_last = max(keys)
    if new_last <= last_row:
        raise RuntimeError(f'pagination did not advance: {last_row} -> {new_last}')
    last_row = new_last

Path('rampi-flights-api.json').write_text(json.dumps(all_api_rows, indent=2, ensure_ascii=False), encoding='utf-8')
target = [r for r in all_api_rows if r['date'] == '2022-03-06']
Path('rampi-target.json').write_text(json.dumps(target, indent=2, ensure_ascii=False), encoding='utf-8')
print('TARGET ROWS')
print(json.dumps(target, indent=2, ensure_ascii=False))
