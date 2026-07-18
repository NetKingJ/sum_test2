#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures
import hashlib
import html
import io
import json
import math
import re
import shutil
import urllib.parse
from pathlib import Path

import cv2
import numpy as np
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
QUERY_IMAGE = ROOT / "whereami-small.jpg"
OUT = ROOT / "harvest-match-results.json"
TOPDIR = ROOT / "harvest-top"
TOPDIR.mkdir(exist_ok=True)
for p in TOPDIR.glob("*"):
    p.unlink()

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
QUERIES = [
    "Rashaan Khad tamga Mongolia",
    "Rashaan Khad clan stamps",
    "Рашаан хад тамга",
    "Рашаан хад овгийн тамга",
    "Монгол тамга чулуун хана",
    "Монгол овгийн тамга хөшөө",
    "Mongolia clan tamga stone wall monument",
    "Mongolian petroglyph tamga monument",
    "археологийн дурсгал тамга хана Монгол",
    "Khentii tamga monument wall",
    "Tamgaly tamga stone wall monument Kazakhstan",
    "Тамгалы тас памятник тамги стена",
    "Казахстан каменная стена тамги памятник",
    "Қазақ ру таңбалары тас қабырға ескерткіш",
    "Таңбалы тас тамға ескерткіш қабырға",
    "Central Asia petroglyph visitor center stone wall",
    "ancient tamga symbols granite wall Central Asia",
    "Chinggis Khan clan stamps stone wall",
    "Mongol clan symbols wall grass trees",
    "Rashaan Khad museum cast tamga",
    "Eshkiolmes petroglyph museum wall",
    "Ak Baur petroglyph monument wall",
    "Tamga Tash archaeological site monument",
    "Тамга-Таш памятник стена",
]
DIRECT_URLS = [
    "https://tourmongolia.com/wp-content/uploads/2018/03/Rashaan-khad-ancestors-wall-Tour-Mongolia-4.jpg",
    "https://travel.khentii.gov.mn/uploads/img/2019/09/13/c1d3874cb9b1c5a4b31871733e5d5278.jpg",
    "https://travel.khentii.gov.mn/uploads/300x0/2020/04/14/0c76fb2e27c768288a1f352a57aba604.jpg",
]
PAGES = [
    "https://tourmongolia.com/portfolio/rashaan-khad-ancestors-wall/",
    "https://www.toursofmongolia.com/pages/oglogch-kherem-ancestors-wall",
    "https://www.travel.khentii.gov.mn/en/place/detail/7?mid=9",
    "https://kerekinfo.kz/2018/11/08/tabaly-tas-tarih-mrasy.html",
    "https://visitalmaty.kz/activity/tamgaly-tas/",
]

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})


def unescape_url(v: str) -> str:
    return html.unescape(v).replace("\\/", "/").replace("\\u0026", "&").replace("\\u003d", "=")


def collect_bing(query: str) -> list[dict]:
    url = "https://www.bing.com/images/search?" + urllib.parse.urlencode({"q": query, "form": "HDRSC2", "first": 1, "tsc": "ImageBasicHover"})
    try:
        r = session.get(url, timeout=45)
        text = r.text
    except Exception as exc:
        return [{"query": query, "error": repr(exc)}]
    found: list[dict] = []
    soup = BeautifulSoup(text, "html.parser")
    for a in soup.select("a.iusc"):
        raw = a.get("m")
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        murl = obj.get("murl") or obj.get("turl")
        purl = obj.get("purl") or obj.get("surl")
        if murl:
            found.append({"query": query, "image_url": unescape_url(murl), "page_url": unescape_url(purl or ""), "title": obj.get("t", "")})
    if not found:
        # Regex fallback for embedded JSON.
        for m in re.finditer(r'"murl"\s*:\s*"([^"]+)".*?"purl"\s*:\s*"([^"]*)"', text, re.S):
            found.append({"query": query, "image_url": unescape_url(m.group(1)), "page_url": unescape_url(m.group(2)), "title": ""})
    return found[:120]


def collect_page(url: str) -> list[dict]:
    try:
        r = session.get(url, timeout=45)
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as exc:
        return [{"query": "page", "page_url": url, "error": repr(exc)}]
    out = []
    for img in soup.find_all("img"):
        for key in ("src", "data-src", "data-lazy-src", "data-original"):
            src = img.get(key)
            if src:
                src = urllib.parse.urljoin(url, unescape_url(src))
                if src.startswith("http"):
                    out.append({"query": "page:" + url, "image_url": src, "page_url": url, "title": img.get("alt", "")})
    # OpenGraph and CSS background images.
    for meta in soup.find_all("meta"):
        if meta.get("property") in {"og:image", "twitter:image"} and meta.get("content"):
            out.append({"query": "page:" + url, "image_url": urllib.parse.urljoin(url, meta["content"]), "page_url": url, "title": "og:image"})
    for src in re.findall(r'https?://[^"\'<>\s]+\.(?:jpg|jpeg|png|webp)(?:\?[^"\'<>\s]*)?', r.text, re.I):
        out.append({"query": "page:" + url, "image_url": unescape_url(src), "page_url": url, "title": "embedded"})
    return out


def download_item(item: dict) -> tuple[dict, bytes | None, str | None]:
    url = item.get("image_url")
    if not url:
        return item, None, "no image URL"
    try:
        r = session.get(url, timeout=20, headers={"Referer": item.get("page_url") or "https://www.bing.com/"})
        if r.status_code != 200:
            return item, None, f"HTTP {r.status_code}"
        data = r.content
        if len(data) < 1000 or len(data) > 20_000_000:
            return item, None, f"bad size {len(data)}"
        im = Image.open(io.BytesIO(data))
        if im.width < 150 or im.height < 80:
            return item, None, f"small {im.size}"
        im.verify()
        return item, data, None
    except Exception as exc:
        return item, None, repr(exc)


def decode_cv(data: bytes) -> np.ndarray | None:
    arr = np.frombuffer(data, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

qimg = cv2.imread(str(QUERY_IMAGE), cv2.IMREAD_COLOR)
if qimg is None:
    raise RuntimeError("query image unavailable")
qgray = cv2.cvtColor(qimg, cv2.COLOR_BGR2GRAY)
sift = cv2.SIFT_create(nfeatures=4000, contrastThreshold=0.02, edgeThreshold=15)
qkp, qdes = sift.detectAndCompute(qgray, None)
orb = cv2.ORB_create(nfeatures=5000, fastThreshold=5)
qokp, qodes = orb.detectAndCompute(qgray, None)


def compare(item: dict, data: bytes) -> dict:
    img = decode_cv(data)
    if img is None:
        return {**item, "error": "decode failed"}
    h, w = img.shape[:2]
    scale = min(1.0, 1800.0 / max(h, w))
    if scale < 1:
        img2 = cv2.resize(img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_AREA)
    else:
        img2 = img
    gray = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    kp, des = sift.detectAndCompute(gray, None)
    good = []
    inliers = 0
    if des is not None and qdes is not None and len(des) >= 2:
        matcher = cv2.BFMatcher(cv2.NORM_L2)
        try:
            pairs = matcher.knnMatch(qdes, des, k=2)
            good = [m for m,n in pairs if m.distance < 0.72*n.distance]
            if len(good) >= 4:
                src = np.float32([qkp[m.queryIdx].pt for m in good]).reshape(-1,1,2)
                dst = np.float32([kp[m.trainIdx].pt for m in good]).reshape(-1,1,2)
                H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
                if mask is not None:
                    inliers = int(mask.sum())
        except Exception:
            pass
    # ORB corroboration.
    okp, odes = orb.detectAndCompute(gray, None)
    orb_good = 0
    if odes is not None and qodes is not None and len(odes) >= 2:
        try:
            pairs = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(qodes, odes, k=2)
            orb_good = sum(1 for m,n in pairs if m.distance < 0.75*n.distance)
        except Exception:
            pass
    # Whole-image perceptual comparison after fitting aspect ratio (weak signal only).
    try:
        target = cv2.resize(gray, (qgray.shape[1], qgray.shape[0]), interpolation=cv2.INTER_AREA)
        edge_q = cv2.Canny(qgray, 50, 150)
        edge_t = cv2.Canny(target, 50, 150)
        corr = float(cv2.matchTemplate(edge_t, edge_q, cv2.TM_CCOEFF_NORMED)[0,0])
    except Exception:
        corr = 0.0
    score = inliers * 100 + len(good) * 5 + orb_good * 2 + max(0.0, corr) * 10
    return {**item, "width": w, "height": h, "bytes": len(data), "sift_good": len(good), "sift_inliers": inliers, "orb_good": orb_good, "edge_corr": corr, "score": score, "sha256": hashlib.sha256(data).hexdigest(), "_data": data}

items = []
for u in DIRECT_URLS:
    items.append({"query": "direct", "image_url": u, "page_url": u, "title": "direct candidate"})
for page in PAGES:
    items.extend(collect_page(page))
for q in QUERIES:
    items.extend(collect_bing(q))

# Deduplicate image URLs.
unique = []
seen = set()
for item in items:
    u = item.get("image_url")
    if not u or u in seen:
        continue
    seen.add(u)
    unique.append(item)

results = []
errors = []
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
    futures = [ex.submit(download_item, item) for item in unique]
    for fut in concurrent.futures.as_completed(futures):
        item, data, err = fut.result()
        if data is None:
            if len(errors) < 500:
                errors.append({**item, "error": err})
            continue
        results.append(compare(item, data))

results.sort(key=lambda x: (x.get("sift_inliers",0), x.get("sift_good",0), x.get("score",0)), reverse=True)
# Save top images and remove byte payloads.
public_results=[]
thumbs=[]
for i, row in enumerate(results):
    data=row.pop("_data",None)
    if i < 40 and data:
        ext="jpg"
        try:
            im=Image.open(io.BytesIO(data)).convert("RGB")
            path=TOPDIR/f"match-{i:02d}.jpg"
            im.thumbnail((1200,900))
            im.save(path,quality=88)
            row["saved_path"]=str(path.relative_to(ROOT))
            thumb=im.copy(); thumb.thumbnail((320,220)); thumbs.append((thumb,i,row))
        except Exception as exc:
            row["save_error"]=repr(exc)
    public_results.append(row)

# Contact sheet of the top candidates for rapid manual inspection.
if thumbs:
    cellw,cellh=360,280
    sheet=Image.new("RGB",(cellw*4,cellh*math.ceil(len(thumbs)/4)),"white")
    draw=ImageDraw.Draw(sheet)
    for n,(im,i,row) in enumerate(thumbs):
        x=(n%4)*cellw; y=(n//4)*cellh
        sheet.paste(im,(x+(cellw-im.width)//2,y+25))
        label=f"#{i} inl={row.get('sift_inliers')} good={row.get('sift_good')} {urllib.parse.urlparse(row.get('page_url','')).netloc}"
        draw.text((x+5,y+5),label[:55],fill="black")
    sheet.save(ROOT/"harvest-contact-sheet.jpg",quality=88)

payload={
    "query_keypoints":len(qkp),
    "queries":QUERIES,
    "collected_unique_urls":len(unique),
    "downloaded_images":len(results),
    "top_results":public_results[:200],
    "errors_sample":errors[:200],
}
OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
print(OUT.read_text(encoding="utf-8")[:250000])
