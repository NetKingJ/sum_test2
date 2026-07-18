#!/usr/bin/env python3
from __future__ import annotations

import base64
import html
import json
import re
import time
import urllib.parse
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
IMAGE = ROOT / "whereami-small.jpg"
B64 = ROOT / "whereami-small.b64"
OUT = ROOT / "reverse-results.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

IMAGE.write_bytes(base64.b64decode(B64.read_text().strip()))


def extract_urls(text: str) -> list[str]:
    text = html.unescape(text).replace("\\u003d", "=").replace("\\u0026", "&").replace("\\/", "/")
    found: list[str] = []
    patterns = [
        r'https?://[^"\'<>\\ ]+',
        r'url=([^&"\'<> ]+)',
    ]
    for pat in patterns:
        for val in re.findall(pat, text):
            try:
                val = urllib.parse.unquote(val)
            except Exception:
                pass
            val = val.rstrip('),.;]')
            if val.startswith('http') and val not in found:
                found.append(val)
    return found


def useful(url: str) -> bool:
    bad = (
        'google.com', 'gstatic.com', 'googleusercontent.com', 'ggpht.com',
        'yandex.', 'yastatic.net', 'ya.ru', 'bing.com', 'microsoft.com',
        'schema.org', 'w3.org', 'doubleclick.net', 'googlesyndication.com',
    )
    return not any(x in url.lower() for x in bad)


session = requests.Session()
session.headers.update({'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9'})
results: dict[str, object] = {}

# Google Lens multipart upload.
try:
    with IMAGE.open('rb') as f:
        r = session.post(
            f'https://lens.google.com/v3/upload?ep=ccm&s=&st={int(time.time()*1000)}&hl=en',
            files={'encoded_image': ('whereami.jpg', f, 'image/jpeg')},
            data={'processed_image_dimensions': '600,113'},
            allow_redirects=True,
            timeout=90,
        )
    (ROOT / 'google-lens.html').write_text(r.text, encoding='utf-8', errors='replace')
    urls = [u for u in extract_urls(r.text) if useful(u)]
    results['google_lens'] = {
        'status': r.status_code,
        'final_url': r.url,
        'length': len(r.content),
        'urls': urls[:300],
        'title_matches': re.findall(r'<title[^>]*>(.*?)</title>', r.text, flags=re.I|re.S)[:5],
    }
except Exception as exc:
    results['google_lens'] = {'error': repr(exc)}

# Yandex reverse-image upload.
try:
    params = {
        'rpt': 'imageview',
        'format': 'json',
        'request': '{"blocks":[{"block":"b-page_type_search-by-image__link"}]}',
    }
    with IMAGE.open('rb') as f:
        up = session.post(
            'https://yandex.com/images/search',
            params=params,
            files={'upfile': ('blob', f, 'image/jpeg')},
            headers={'Referer': 'https://yandex.com/images/'},
            timeout=90,
        )
    entry: dict[str, object] = {'upload_status': up.status_code, 'upload_length': len(up.content), 'upload_preview': up.text[:1000]}
    try:
        obj = up.json()
        query = obj['blocks'][0]['params']['url']
        result_url = 'https://yandex.com/images/search?' + query
        rr = session.get(result_url, headers={'Referer': 'https://yandex.com/images/'}, timeout=90)
        (ROOT / 'yandex.html').write_text(rr.text, encoding='utf-8', errors='replace')
        urls = [u for u in extract_urls(rr.text) if useful(u)]
        entry.update({'result_url': result_url, 'result_status': rr.status_code, 'result_length': len(rr.content), 'urls': urls[:300]})
    except Exception as exc:
        entry['parse_error'] = repr(exc)
    results['yandex'] = entry
except Exception as exc:
    results['yandex'] = {'error': repr(exc)}

# TinEye upload, useful mainly for redirect/result URL.
try:
    with IMAGE.open('rb') as f:
        tr = session.post(
            'https://tineye.com/api/v1/result_json/',
            files={'image': ('whereami.jpg', f, 'image/jpeg')},
            timeout=90,
            allow_redirects=True,
        )
    results['tineye'] = {'status': tr.status_code, 'url': tr.url, 'length': len(tr.content), 'preview': tr.text[:2000]}
except Exception as exc:
    results['tineye'] = {'error': repr(exc)}

OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
print(OUT.read_text(encoding='utf-8'))
