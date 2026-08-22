from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
SYMBOLS = ("00642U", "1721", "2312", "3607", "3706")
START_YEAR = 2023
END_YEAR = 2025
OUT = Path("twse_priority_universe_output")
PKG = OUT / "twse_priority_universe_2023_2025_raw"
ZIP_PATH = OUT / "twse_priority_universe_2023_2025_raw.zip"
SUMMARY_PATH = OUT / "fetch_summary.json"
USER_AGENT = "TWSE-priority-universe-historical-fetch/1.0"


def expected_months() -> list[str]:
    return [f"{year}{month:02d}" for year in range(START_YEAR, END_YEAR + 1) for month in range(1, 13)]


def row_month(value: str) -> str:
    parts = str(value).strip().split("/")
    if len(parts) != 3:
        raise ValueError(f"bad ROC date {value!r}")
    return f"{int(parts[0]) + 1911}{int(parts[1]):02d}"


def validate(raw: bytes, symbol: str, month: str) -> tuple[int, int]:
    payload = json.loads(raw.decode("utf-8-sig"))
    if str(payload.get("stat", "")).upper() != "OK":
        raise ValueError(f"stat not OK for {symbol} {month}: {payload.get('stat')!r}")
    fields = payload.get("fields") or []
    rows = payload.get("data") or []
    if len(fields) < 8:
        raise ValueError(f"unexpected STOCK_DAY field count for {symbol} {month}: {len(fields)}")
    if not rows:
        raise ValueError(f"empty STOCK_DAY data for {symbol} {month}")
    for row in rows:
        if not isinstance(row, list) or len(row) != len(fields):
            raise ValueError(f"row width mismatch for {symbol} {month}")
        if row_month(row[0]) != month:
            raise ValueError(f"out-of-month row for {symbol} {month}: {row[0]!r}")
    return len(rows), len(fields)


def fetch(symbol: str, month: str) -> tuple[bytes, int, int, str]:
    params = urllib.parse.urlencode({"response": "json", "date": f"{month}01", "stockNo": symbol})
    url = f"{BASE_URL}?{params}"
    last: Exception | None = None
    for attempt, delay in enumerate((0, 2, 5, 10), start=1):
        if delay:
            time.sleep(delay)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*", "Cache-Control": "no-cache"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read()
                status = getattr(response, "status", 200)
            if status != 200:
                raise RuntimeError(f"HTTP {status}")
            rows, field_count = validate(raw, symbol, month)
            return raw, rows, field_count, url
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, RuntimeError) as exc:
            last = exc
            print(f"[{symbol} {month}] attempt {attempt}/4 failed: {type(exc).__name__}: {exc}", flush=True)
    raise RuntimeError(f"fetch failed for {symbol} {month}: {last}")


def deterministic_zip() -> None:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(p for p in PKG.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(PKG).as_posix(), (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())


def main() -> int:
    months = expected_months()
    if len(months) != 36 or months[0] != "202301" or months[-1] != "202512":
        raise RuntimeError("bounded month list invariant failed")

    manifest: list[dict] = []
    per_symbol_rows: dict[str, int] = {symbol: 0 for symbol in SYMBOLS}
    total_requests = len(SYMBOLS) * len(months)
    position = 0

    for symbol in SYMBOLS:
        raw_dir = PKG / "data" / "raw" / "twse" / symbol
        raw_dir.mkdir(parents=True, exist_ok=True)
        for month in months:
            position += 1
            print(f"[{position:03d}/{total_requests}] fetching TWSE STOCK_DAY {symbol} {month}", flush=True)
            raw, rows, field_count, url = fetch(symbol, month)
            digest = hashlib.sha256(raw).hexdigest()
            (raw_dir / f"{month}.json").write_bytes(raw)
            manifest.append(
                {
                    "symbol": symbol,
                    "month": month,
                    "rows": rows,
                    "field_count": field_count,
                    "bytes": len(raw),
                    "sha256": digest,
                    "source": url,
                }
            )
            per_symbol_rows[symbol] += rows
            print(f"[{position:03d}/{total_requests}] OK {symbol} {month} rows={rows} sha256={digest}", flush=True)
            time.sleep(0.7)

    for symbol in SYMBOLS:
        raw_dir = PKG / "data" / "raw" / "twse" / symbol
        actual = sorted(path.stem for path in raw_dir.glob("*.json"))
        if actual != months:
            raise RuntimeError(f"exact month set mismatch for {symbol}: {actual}")

    manifest_path = PKG / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (PKG / "summary.txt").write_text(
        "TWSE STOCK_DAY priority universe\n"
        f"Symbols: {', '.join(SYMBOLS)}\n"
        "Months: 2023-01..2025-12 (36 per symbol)\n"
        f"Requests/files: {total_requests}\n"
        f"Rows per symbol: {json.dumps(per_symbol_rows, sort_keys=True)}\n"
        "Bounded: no 2026 data fetched.\n",
        encoding="utf-8",
    )
    deterministic_zip()
    summary = {
        "schema_version": 1,
        "status": "SUCCESS",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": BASE_URL,
        "symbols": list(SYMBOLS),
        "months_per_symbol": len(months),
        "month_start": months[0],
        "month_end": months[-1],
        "raw_file_count": len(manifest),
        "rows_per_symbol": per_symbol_rows,
        "includes_2026": False,
        "zip_sha256": hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
