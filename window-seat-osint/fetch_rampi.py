#!/usr/bin/env python3
from __future__ import annotations

import http.cookiejar
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://my.flightradar24.com/Rampi/flights/date/asc"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def request(url: str, *, ajax: bool = False) -> tuple[int, dict[str, str], bytes]:
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/javascript, */*; q=0.01" if ajax else "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": BASE,
        "Accept-Language": "en-US,en;q=0.9",
    }
    if ajax:
        headers["X-Requested-With"] = "XMLHttpRequest"
    req = urllib.request.Request(url, headers=headers)
    try:
        with opener.open(req, timeout=60) as r:
            body = r.read()
            return r.status, dict(r.headers.items()), body
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read()


def clean(v: object) -> str:
    if v is None:
        return ""
    s = html.unescape(str(v))
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


status, headers, raw = request(BASE)
text = raw.decode("utf-8", "replace")
Path("rampi-page.html").write_text(text, encoding="utf-8")
Path("rampi-page-meta.json").write_text(
    json.dumps({"status": status, "headers": headers, "cookies": [str(c) for c in jar]}, indent=2),
    encoding="utf-8",
)

row_numbers = [int(x) for x in re.findall(r'data-row-number=["\'](\d+)["\']', text)]
max_row = max(row_numbers) if row_numbers else 49
Path("rampi-row-numbers.json").write_text(json.dumps(row_numbers, indent=2), encoding="utf-8")
print("initial status", status, "rows", len(row_numbers), "min/max", min(row_numbers or [-1]), max_row, "cookies", list(jar))

# Probe neighboring cursor values so a subtle off-by-one cannot block the investigation.
probe_report = []
working_cursor = None
working_data = None
for cursor in sorted({max_row - 1, max_row, max_row + 1, 39, 49}):
    if cursor < 0:
        continue
    url = f"https://my.flightradar24.com/public-scripts/flight-list/Rampi/{cursor}/date/asc"
    st, hdr, body = request(url, ajax=True)
    Path(f"rampi-api-probe-{cursor}.bin").write_bytes(body)
    body_text = body.decode("utf-8", "replace")
    entry = {
        "cursor": cursor,
        "url": url,
        "status": st,
        "headers": hdr,
        "length": len(body),
        "preview": body_text[:1000],
    }
    try:
        parsed = json.loads(body_text)
        entry["json_type"] = type(parsed).__name__
        entry["json_length"] = len(parsed) if hasattr(parsed, "__len__") else None
        if parsed and working_data is None:
            working_cursor = cursor
            working_data = parsed
    except Exception as exc:
        entry["json_error"] = repr(exc)
    probe_report.append(entry)
Path("rampi-api-probes.json").write_text(json.dumps(probe_report, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(probe_report, indent=2, ensure_ascii=False)[:15000])

all_rows: list[dict[str, object]] = []
if working_data is not None and working_cursor is not None:
    cursor = working_cursor
    data = working_data
    for batch in range(200):
        if batch > 0:
            url = f"https://my.flightradar24.com/public-scripts/flight-list/Rampi/{cursor}/date/asc"
            st, hdr, body = request(url, ajax=True)
            Path(f"rampi-api-batch-{batch:03d}-{cursor}.bin").write_bytes(body)
            if st != 200:
                print("batch HTTP failure", batch, cursor, st)
                break
            try:
                data = json.loads(body.decode("utf-8", "replace"))
            except Exception as exc:
                print("batch JSON failure", batch, cursor, repr(exc), body[:500])
                break
        if not data:
            print("pagination end", batch, cursor)
            break

        if isinstance(data, dict):
            numeric_keys = sorted(int(k) for k in data.keys())
            pairs = [(k, data[str(k)] if str(k) in data else data[k]) for k in numeric_keys]
        elif isinstance(data, list):
            # Some versions return an array indexed from zero but embed the actual row index in object keys.
            pairs = [(cursor + 1 + i, row) for i, row in enumerate(data)]
            numeric_keys = [p[0] for p in pairs]
        else:
            print("unexpected JSON type", type(data).__name__)
            break

        for key, row in pairs:
            values = list(row) + [""] * max(0, 13 - len(row))
            all_rows.append(
                {
                    "row_number": key,
                    "date": clean(values[0]),
                    "flight": clean(values[1]),
                    "from": clean(values[2]),
                    "to": clean(values[3]),
                    "distance": clean(values[4]),
                    "departure": clean(values[5]),
                    "arrival": clean(values[6]),
                    "airline": clean(values[7]),
                    "aircraft": clean(values[8]),
                    "registration": clean(values[9]),
                    "seat": clean(values[10]),
                    "note": clean(values[11]),
                    "icons": clean(values[12]),
                    "raw": values,
                }
            )
        new_cursor = max(numeric_keys)
        if new_cursor <= cursor:
            print("pagination did not advance", cursor, new_cursor)
            break
        cursor = new_cursor

Path("rampi-flights-api.json").write_text(json.dumps(all_rows, indent=2, ensure_ascii=False), encoding="utf-8")
target = [r for r in all_rows if "2022-03-06" in str(r["date"])]
Path("rampi-target.json").write_text(json.dumps(target, indent=2, ensure_ascii=False), encoding="utf-8")
print("TARGET", json.dumps(target, indent=2, ensure_ascii=False))
