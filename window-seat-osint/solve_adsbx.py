#!/usr/bin/env python3
"""Parse ADS-B Exchange globe-history heatmap chunks near the EXIF point/time."""
from __future__ import annotations

import json
import math
import struct
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

TARGET_LAT = 50.13673138888889
TARGET_LON = 11.838363611111111
TARGET_TIMES = [
    datetime(2022, 3, 6, 14, 4, tzinfo=timezone.utc).timestamp(),  # EXIF local CET
    datetime(2022, 3, 6, 15, 4, tzinfo=timezone.utc).timestamp(),  # EXIF interpreted UTC
]
BASE = "https://globe.adsbexchange.com/globe_history/2022/03/06/heatmap/{:02d}.bin.ttf"
MAGIC = 0x0E7F7C9D
OUT = Path("window-seat-result.json")


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def signed16(v: int) -> int:
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def decode_callsign(raw: bytes) -> str:
    return raw.decode("ascii", errors="ignore").replace("\x00", "").strip()


def download(index: int) -> bytes:
    url = BASE.format(index)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Accept": "*/*",
            "Referer": "https://globe.adsbexchange.com/",
        },
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read()
            print(index, len(data), data[:16].hex())
            return data
        except Exception as exc:
            print("download failed", index, attempt, repr(exc))
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


def parse_chunk(index: int, data: bytes):
    # Int32Array in tar1090 is native little-endian on browser platforms.
    n = len(data) // 16
    callsigns: dict[str, str] = {}
    positions: list[dict] = []
    now = None
    interval = None
    marker_count = 0
    malformed = 0

    for recno in range(n):
        off = recno * 16
        a_s, b_s, c_s, d_s = struct.unpack_from("<4i", data, off)
        a_u, b_u, c_u, d_u = struct.unpack_from("<4I", data, off)

        if a_u == MAGIC:
            # Exact reconstruction used by tar1090 replay parser.
            now = c_u / 1000.0 + b_u * 4294967.296
            interval = (d_u & 0xFFFF) / 1000.0
            marker_count += 1
            continue

        if now is None:
            continue

        hexid = f"{a_u & 0xFFFFFF:06x}"

        # tar1090 metadata record: second int >= 2^30, callsign occupies final 8 bytes.
        if b_s >= 1073741824:
            cs = decode_callsign(data[off + 8 : off + 16])
            if cs:
                callsigns[hexid] = cs
            continue

        lat = b_s / 1_000_000.0
        lon = c_s / 1_000_000.0
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            malformed += 1
            continue

        alt_code = signed16(a_u)
        if alt_code == -123:
            altitude_ft = "ground"
        elif alt_code == -124:
            altitude_ft = None
        else:
            altitude_ft = alt_code * 25
        speed_kt = signed16(d_u >> 16) / 10.0
        dist = haversine(TARGET_LAT, TARGET_LON, lat, lon)
        positions.append(
            {
                "index": index,
                "timestamp": now,
                "time_utc": datetime.fromtimestamp(now, timezone.utc).isoformat(),
                "hex": hexid,
                "lat": lat,
                "lon": lon,
                "distance_km": dist,
                "altitude_ft": altitude_ft,
                "speed_kt": speed_kt,
                "type_bits": (a_u >> 27) & 0x1F,
                "interval_s": interval,
            }
        )

    for p in positions:
        p["callsign"] = callsigns.get(p["hex"], "")
    return positions, callsigns, {"records": n, "markers": marker_count, "malformed": malformed}


def main() -> None:
    all_positions: list[dict] = []
    all_callsigns: dict[str, str] = {}
    chunk_stats = {}
    errors = {}

    # Cover 13:30 through 16:00 UTC, safely bracketing both timestamp interpretations.
    for idx in range(27, 32):
        try:
            data = download(idx)
            positions, callsigns, stats = parse_chunk(idx, data)
            all_positions.extend(positions)
            all_callsigns.update(callsigns)
            chunk_stats[str(idx)] = {**stats, "bytes": len(data), "positions": len(positions), "callsigns": len(callsigns)}
        except Exception as exc:
            errors[str(idx)] = repr(exc)

    # Fill callsigns learned in an adjacent chunk.
    for p in all_positions:
        if not p["callsign"]:
            p["callsign"] = all_callsigns.get(p["hex"], "")

    results = []
    for target in TARGET_TIMES:
        candidates = []
        for p in all_positions:
            td = abs(p["timestamp"] - target)
            if td <= 15 * 60 and p["distance_km"] <= 250:
                q = dict(p)
                q["time_delta_s"] = p["timestamp"] - target
                # Prefer spatiotemporal closeness; 1 minute roughly 14 km at cruise.
                q["score"] = p["distance_km"] + td * 0.20
                candidates.append(q)
        candidates.sort(key=lambda x: (x["score"], x["distance_km"], abs(x["time_delta_s"])))

        # Deduplicate repeated samples by aircraft, retaining best sample.
        best = {}
        for c in candidates:
            best.setdefault(c["hex"], c)
        deduped = sorted(best.values(), key=lambda x: x["score"])[:100]
        results.append(
            {
                "target_epoch": target,
                "target_utc": datetime.fromtimestamp(target, timezone.utc).isoformat(),
                "nearest_aircraft": deduped,
            }
        )

    payload = {
        "target": {"lat": TARGET_LAT, "lon": TARGET_LON},
        "chunk_stats": chunk_stats,
        "errors": errors,
        "results": results,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(OUT.read_text(encoding="utf-8")[:30000])


if __name__ == "__main__":
    main()
