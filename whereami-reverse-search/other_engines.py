#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import urllib.parse
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "other-engine-summary.json"
RAW = "https://raw.githubusercontent.com/NetKingJ/sum_test2/whereami-reverse-search/whereami-reverse-search/whereami-small.jpg"
ENC = urllib.parse.quote(RAW, safe="")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
BLOCKED = (
    "bing.com", "microsoft.com", "bing.net", "yandex.", "yastatic.net", "ya.ru",
    "tineye.com", "sogou.com", "sogoucdn.com", "baidu.com", "bdstatic.com",
    "google.com", "gstatic.com", "googleusercontent.com", "githubusercontent.com",
    "schema.org", "w3.org", "doubleclick.net",
)

URLS = {
    "bing": f"https://www.bing.com/images/searchbyimage?cbir=sbi&iss=sbi&imgurl={ENC}&cc=us&setlang=en",
    "bing_edges": f"https://edgeservices.bing.com/images/searchbyimage?cbir=sbi&iss=sbi&imgurl={ENC}&cc=us&setlang=en",
    "yandex": f"https://yandex.com/images/search?rpt=imageview&url={ENC}&lang=en",
    "tineye": f"https://tineye.com/search?url={ENC}",
    "sogou": f"https://pic.sogou.com/ris?query={ENC}&flag=1&drag=0",
}


def normalise(value: str, base: str) -> str | None:
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
        for key in ("q", "url", "imgurl", "rurl", "redirect"):
            if key in qs and qs[key] and qs[key][0].startswith("http"):
                value = urllib.parse.unquote(qs[key][0])
                break
    except Exception:
        pass
    return value.rstrip('),.;]')


def external(url: str) -> bool:
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
    except Exception:
        return False
    return bool(host) and not any(x in host for x in BLOCKED)


def parse(text: str, base: str) -> dict:
    soup = BeautifulSoup(text, "html.parser")
    out = []
    seen = set()
    for tag in soup.find_all(True):
        label = " ".join(tag.stripped_strings)[:500]
        for key, val in tag.attrs.items():
            if isinstance(val, list):
                val = " ".join(map(str, val))
            if key in {"href", "src", "data-url", "data-src", "data-href", "data-m", "m", "data-bm"} or "url" in key.lower():
                u = normalise(str(val), base)
                if u and external(u) and u not in seen:
                    seen.add(u)
                    out.append({"url": u, "text": label, "tag": tag.name, "attr": key})
    raw = html.unescape(text).replace("\\u003d", "=").replace("\\u0026", "&").replace("\\/", "/")
    for pattern in [r'https?://[^"\'<>\\\s]+', r'"murl"\s*:\s*"([^"]+)"', r'"purl"\s*:\s*"([^"]+)"']:
        for value in re.findall(pattern, raw):
            u = normalise(value, base)
            if u and external(u) and u not in seen:
                seen.add(u)
                out.append({"url": u, "text": "embedded", "tag": "script", "attr": "regex"})
    visible = []
    for line in soup.get_text("\n").splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line and line not in visible:
            visible.append(line)
    return {"title": soup.title.get_text(" ", strip=True) if soup.title else "", "links": out[:1500], "visible_text": visible[:1200], "length": len(text)}


def dump(chrome: str, stem: str, url: str) -> dict:
    profile = ROOT / f"other-profile-{stem}"
    shutil.rmtree(profile, ignore_errors=True)
    cmd = [chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
           "--disable-blink-features=AutomationControlled", "--ignore-certificate-errors", "--window-size=1600,2400",
           "--virtual-time-budget=30000", f"--user-data-dir={profile}", f"--user-agent={UA}", "--dump-dom", url]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=150)
    dom = p.stdout
    (ROOT / f"other-{stem}.html").write_text(dom, encoding="utf-8", errors="replace")
    result = parse(dom, url)
    result.update({"url": url, "returncode": p.returncode, "stderr_tail": p.stderr[-2000:]})
    shutil.rmtree(profile, ignore_errors=True)
    return result

chrome = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
summary = {"chrome": chrome, "image": RAW, "targets": URLS, "results": {}}
if chrome:
    for stem, url in URLS.items():
        try:
            summary["results"][stem] = dump(chrome, stem, url)
        except Exception as exc:
            summary["results"][stem] = {"url": url, "error": repr(exc)}
else:
    summary["error"] = "Chrome not found"
OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(OUT.read_text(encoding="utf-8")[:250000])
