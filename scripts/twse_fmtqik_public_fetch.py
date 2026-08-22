from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://www.twse.com.tw/exchangeReport/FMTQIK"
OUT = Path("twse_fmtqik_output")
PKG = OUT / "twse_fmtqik_2023_2025_raw"
RAW = PKG / "data/raw/twse/fmtqik"
ZIP = OUT / "twse_fmtqik_2023_2025_raw.zip"
SUMMARY = OUT / "fetch_summary.json"
USER_AGENT = "TWSE-public-historical-fetch/1.0"
TRIGGER_VERSION = 1


def expected_months() -> list[str]:
    return [f"{y}{m:02d}" for y in range(2023, 2026) for m in range(1, 13)]


def row_month(value: str) -> str:
    parts = str(value).strip().split("/")
    if len(parts) != 3:
        raise ValueError(f"bad ROC date {value!r}")
    return f"{int(parts[0]) + 1911}{int(parts[1]):02d}"


def validate(raw: bytes, month: str) -> int:
    payload = json.loads(raw.decode("utf-8-sig"))
    if str(payload.get("stat", "")).upper() != "OK":
        raise ValueError(f"stat not OK for {month}: {payload.get('stat')!r}")
    fields = payload.get("fields") or []
    rows = payload.get("data") or []
    if len(fields) != 6 or not rows:
        raise ValueError(f"invalid FMTQIK shape for {month}")
    for row in rows:
        if not isinstance(row, list) or len(row) != 6:
            raise ValueError(f"invalid row shape for {month}")
        if row_month(row[0]) != month:
            raise ValueError(f"out-of-month row for {month}: {row[0]!r}")
    return len(rows)


def fetch(month: str) -> tuple[bytes, int, str]:
    url = f"{BASE_URL}?response=json&date={month}01"
    last = None
    for attempt, delay in enumerate((0, 2, 5, 10), start=1):
        if delay:
            time.sleep(delay)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read()
            rows = validate(raw, month)
            return raw, rows, url
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
            last = exc
            print(f"{month} attempt {attempt}/4 failed: {type(exc).__name__}: {exc}", flush=True)
    raise RuntimeError(f"fetch failed for {month}: {last}")


def make_zip() -> None:
    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(p for p in PKG.rglob("*") if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(PKG).as_posix(), (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())


def main() -> int:
    months = expected_months()
    assert TRIGGER_VERSION == 1
    assert len(months) == 36 and months[0] == "202301" and months[-1] == "202512"
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = []
    total_rows = 0
    for i, month in enumerate(months, start=1):
        print(f"[{i:02d}/36] {month}", flush=True)
        raw, rows, url = fetch(month)
        digest = hashlib.sha256(raw).hexdigest()
        (RAW / f"{month}.json").write_bytes(raw)
        manifest.append({"month": month, "rows": rows, "bytes": len(raw), "sha256": digest, "source": url})
        total_rows += rows
        time.sleep(0.4)
    (PKG / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (PKG / "summary.txt").write_text(
        f"TWSE FMTQIK 2023-01..2025-12\nMonths: 36\nRows: {total_rows}\nNo 2026 data fetched.\n",
        encoding="utf-8",
    )
    make_zip()
    payload = {
        "status": "SUCCESS",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "months": 36,
        "rows": total_rows,
        "month_start": "202301",
        "month_end": "202512",
        "includes_2026": False,
        "zip_sha256": hashlib.sha256(ZIP.read_bytes()).hexdigest(),
        "trigger_version": TRIGGER_VERSION,
    }
    SUMMARY.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
