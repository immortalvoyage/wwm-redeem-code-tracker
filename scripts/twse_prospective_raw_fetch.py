from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

SYMBOLS = ("00642U", "1721", "2312", "3607", "3706")
STOCK_DAY = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
TWT49U = "https://www.twse.com.tw/rwd/zh/exRight/TWT49U"
USER_AGENT = "TWStock-prospective-raw-fetch/1.0"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def month_keys(as_of: date, count: int = 3) -> list[str]:
    idx = as_of.year * 12 + (as_of.month - 1)
    out = []
    for delta in range(count - 1, -1, -1):
        value = idx - delta
        y, m0 = divmod(value, 12)
        out.append(f"{y}{m0 + 1:02d}")
    return out


def roc_to_iso(value: str) -> str:
    y, m, d = [int(x) for x in str(value).split("/")]
    return f"{y + 1911:04d}-{m:02d}-{d:02d}"


def fetch(url: str) -> bytes:
    last = None
    for delay in (0, 1, 3, 6):
        if delay:
            time.sleep(delay)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*", "Cache-Control": "no-cache"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read()
                if getattr(response, "status", 200) != 200:
                    raise RuntimeError(f"HTTP {getattr(response, 'status', None)}")
            json.loads(raw.decode("utf-8-sig"))
            return raw
        except Exception as exc:
            last = exc
    raise RuntimeError(f"fetch failed: {url}: {type(last).__name__}: {last}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", required=True, help="Asia/Taipei feature date YYYY-MM-DD")
    parser.add_argument("--output", default="prospective_raw_bundle")
    args = parser.parse_args()
    as_of = date.fromisoformat(args.as_of)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    months = month_keys(as_of, 3)
    manifest: list[dict[str, object]] = []

    for symbol in SYMBOLS:
        for month in months:
            url = f"{STOCK_DAY}?{urllib.parse.urlencode({'response': 'json', 'date': month + '01', 'stockNo': symbol})}"
            raw = fetch(url)
            payload = json.loads(raw.decode("utf-8-sig"))
            if str(payload.get("stat", "")).upper() != "OK":
                raise RuntimeError(f"STOCK_DAY stat not OK: {symbol} {month}: {payload.get('stat')}")
            rows = payload.get("data") or []
            if not rows:
                raise RuntimeError(f"STOCK_DAY empty: {symbol} {month}")
            dates = [date.fromisoformat(roc_to_iso(row[0])) for row in rows]
            if any(d > as_of for d in dates):
                raise RuntimeError(f"future STOCK_DAY row detected for {symbol} {month}")
            path = out / "stock_day" / symbol / f"{month}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            manifest.append({"kind": "STOCK_DAY", "symbol": symbol, "month": month, "rows": len(rows), "sha256": sha256_bytes(raw), "source": url})
            time.sleep(0.2)

    start = f"{months[0]}01"
    end = as_of.strftime("%Y%m%d")
    url = f"{TWT49U}?{urllib.parse.urlencode({'startDate': start, 'endDate': end, 'response': 'json'})}"
    raw = fetch(url)
    payload = json.loads(raw.decode("utf-8-sig"))
    if str(payload.get("stat", "")).upper() != "OK":
        raise RuntimeError(f"TWT49U stat not OK: {payload.get('stat')}")
    corp_path = out / "corporate_actions.json"
    corp_path.write_bytes(raw)
    manifest.append({"kind": "TWT49U", "date_start": start, "date_end": end, "rows": len(payload.get("data") or []), "sha256": sha256_bytes(raw), "source": url})

    metadata = {
        "schema_version": 1,
        "status": "SUCCESS",
        "as_of": as_of.isoformat(),
        "symbols": list(SYMBOLS),
        "months": months,
        "includes_data_after_as_of": False,
        "manifest": manifest,
    }
    (out / "manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "SUCCESS", "as_of": as_of.isoformat(), "files": len(manifest), "months": months}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
