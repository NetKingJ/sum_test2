#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import time
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
REVERSE = ROOT / "reverse-results.json"
OUT = ROOT / "lens-render-summary.json"
RAW_IMAGE = "https://raw.githubusercontent.com/NetKingJ/sum_test2/whereami-reverse-search/whereami-reverse-search/whereami-small.jpg"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

GOOGLE_HOSTS = (
    "google.com", "googleusercontent.com", "gstatic.com", "ggpht.com",
    "youtube.com", "ytimg.com", "doubleclick.net", "googlesyndication.com",
    "googleapis.com", "google-analytics.com",
)


def normalize_url(value: str, base: str) -> str | None:
    value = html.unescape(value).replace("\\u003d", "=").replace("\\u0026", "&").replace("\\/", "/")
    value = value.strip().strip('"\'()[]{};,')
    if value.startswith("//"):
        value = "https:" + value
    elif value.startswith("/"):
        value = urllib.parse.urljoin(base, value)
    if not value.startswith(("http://", "https://")):
        return None
    try:
        p = urllib.parse.urlparse(value)
        qs = urllib.parse.parse_qs(p.query)
        # Google redirect wrappers.
        for key in ("q", "url", "imgurl"):
            if key in qs and qs[key] and qs[key][0].startswith("http"):
                value = urllib.parse.unquote(qs[key][0])
                break
    except Exception:
        pass
    return value.rstrip('),.;]')


def is_external(url: str) -> bool:
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return False
    return bool(host) and not any(host == x or host.endswith("." + x) for x in GOOGLE_HOSTS)


def parse_dom(text: str, base: str) -> dict:
    soup = BeautifulSoup(text, "html.parser")
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for tag in soup.find_all(True):
        text_label = " ".join(tag.stripped_strings)
        attrs = []
        for k, v in tag.attrs.items():
            if isinstance(v, list):
                v = " ".join(str(x) for x in v)
            if k in {"href", "src", "data-url", "data-href", "data-src", "data-original", "data-lpage", "data-ved"} or "url" in k.lower():
                attrs.append(str(v))
        for val in attrs:
            u = normalize_url(val, base)
            if u and is_external(u) and u not in seen:
                seen.add(u)
                links.append({"url": u, "text": text_label[:500], "tag": tag.name})
    # Recover URLs embedded in scripts/JSON.
    unescaped = html.unescape(text).replace("\\u003d", "=").replace("\\u0026", "&").replace("\\/", "/")
    for val in re.findall(r'https?://[^"\'<>\\\s]+', unescaped):
        u = normalize_url(val, base)
        if u and is_external(u) and u not in seen:
            seen.add(u)
            links.append({"url": u, "text": "embedded", "tag": "script"})
    visible = []
    for line in soup.get_text("\n").splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line and line not in visible:
            visible.append(line)
    keywords = [
        "Rashaan", "Rashan", "Khuduu", "Kherlen", "Khentii", "Mongolia", "Mongolian",
        "tamga", "tamgha", "tamag", "petroglyph", "archaeological", "Kazakhstan", "Kyrgyzstan",
        "Uzbekistan", "Tajikistan", "Turkmenistan", "Central Asia", "clan", "tribe",
    ]
    hits = []
    lower = unescaped.lower()
    for kw in keywords:
        if kw.lower() in lower:
            hits.append(kw)
    return {
        "title": soup.title.get_text(" ", strip=True) if soup.title else "",
        "links": links[:1000],
        "visible_text": visible[:1000],
        "keyword_hits": hits,
        "length": len(text),
    }


def chrome_dump(chrome: str, url: str, stem: str) -> dict:
    profile = ROOT / f"chrome-profile-{stem}"
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
    cmd = [
        chrome,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
        "--ignore-certificate-errors",
        "--window-size=1600,2400",
        "--virtual-time-budget=25000",
        f"--user-data-dir={profile}",
        f"--user-agent={UA}",
        "--dump-dom",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    dom = proc.stdout
    (ROOT / f"lens-{stem}.html").write_text(dom, encoding="utf-8", errors="replace")
    # Also save a screenshot for manual inspection if needed.
    shot = ROOT / f"lens-{stem}.png"
    shot_cmd = [x for x in cmd if x != "--dump-dom"]
    shot_cmd.insert(-1, f"--screenshot={shot}")
    try:
        subprocess.run(shot_cmd, capture_output=True, text=True, timeout=120)
    except Exception:
        pass
    parsed = parse_dom(dom, url)
    parsed.update({
        "url": url,
        "returncode": proc.returncode,
        "stderr_tail": proc.stderr[-3000:],
        "screenshot_exists": shot.exists(),
        "screenshot_size": shot.stat().st_size if shot.exists() else 0,
    })
    shutil.rmtree(profile, ignore_errors=True)
    return parsed


data = json.loads(REVERSE.read_text(encoding="utf-8"))
base_url = data.get("google_lens", {}).get("final_url", "")
urls: dict[str, str] = {}
if base_url:
    urls["uploaded_default"] = base_url
    parsed = urllib.parse.urlparse(base_url)
    q = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    for mode, udm in (("visual", "44"), ("exact", "48")):
        q["udm"] = [udm]
        q["hl"] = ["en"]
        urls[f"uploaded_{mode}"] = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(q, doseq=True)))

encoded = urllib.parse.quote(RAW_IMAGE, safe="")
urls["byurl_visual"] = f"https://lens.google.com/uploadbyurl?url={encoded}&brd_lens=visual_matches&hl=en&gl=us"
urls["byurl_exact"] = f"https://lens.google.com/uploadbyurl?url={encoded}&brd_lens=exact_matches&hl=en&gl=us"

chrome = shutil.which("google-chrome") or shutil.which("google-chrome-stable") or shutil.which("chromium") or shutil.which("chromium-browser")
summary: dict[str, object] = {"chrome": chrome, "raw_image": RAW_IMAGE, "targets": urls, "results": {}}
if not chrome:
    summary["error"] = "Chrome/Chromium not found"
else:
    for stem, url in urls.items():
        try:
            summary["results"][stem] = chrome_dump(chrome, url, stem)
        except Exception as exc:
            summary["results"][stem] = {"url": url, "error": repr(exc)}

OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(OUT.read_text(encoding="utf-8")[:200000])
