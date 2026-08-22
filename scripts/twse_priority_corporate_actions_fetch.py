from __future__ import annotations

import calendar
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://www.twse.com.tw/exchangeReport/TWT49U"
SYMBOLS = {"00642U", "1721", "2312", "3607", "3706"}
OUT = Path("twse_priority_universe_output") / "corporate_actions"
RAW = OUT / "raw_twt49u"
SUMMARY = OUT / "corporate_action_summary.json"
EVENTS = OUT / "filtered_events.json"
USER_AGENT = "TWSE-priority-universe-corporate-action-audit/1.0"


def months():
    for year in range(2023, 2026):
        for month in range(1, 13):
            yield year, month


def fetch_month(year: int, month: int) -> tuple[bytes, str]:
    start = f"{year}{month:02d}01"
    end = f"{year}{month:02d}{calendar.monthrange(year, month)[1]:02d}"
    params = urllib.parse.urlencode({"response": "json", "strDate": start, "endDate": end})
    url = f"{BASE_URL}?{params}"
    last = None
    for attempt, delay in enumerate((0, 2, 5, 10), start=1):
        if delay:
            time.sleep(delay)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read()
            json.loads(raw.decode("utf-8-sig"))
            return raw, url
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            print(f"{start} attempt {attempt}/4 failed: {type(exc).__name__}: {exc}", flush=True)
    raise RuntimeError(f"failed TWT49U {start}: {last}")


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    monthly = []
    filtered = []
    for idx, (year, month) in enumerate(months(), start=1):
        key = f"{year}{month:02d}"
        print(f"[{idx:02d}/36] fetching TWT49U {key}", flush=True)
        raw, url = fetch_month(year, month)
        digest = hashlib.sha256(raw).hexdigest()
        (RAW / f"{key}.json").write_bytes(raw)
        payload = json.loads(raw.decode("utf-8-sig"))
        fields = payload.get("fields") or []
        rows = payload.get("data") or []
        monthly.append({"month": key, "rows": len(rows), "sha256": digest, "source": url})
        for row in rows:
            if not isinstance(row, list) or len(row) < 7:
                continue
            symbol = str(row[1]).strip()
            if symbol not in SYMBOLS:
                continue
            record = {str(field): value for field, value in zip(fields, row)} if fields else {f"col_{i}": v for i, v in enumerate(row)}
            filtered.append({"month": key, "symbol": symbol, "row": row, "record": record})
        time.sleep(0.5)

    EVENTS.write_text(json.dumps(filtered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    per_symbol = {symbol: 0 for symbol in sorted(SYMBOLS)}
    for event in filtered:
        per_symbol[event["symbol"]] += 1
    summary = {
        "schema_version": 1,
        "status": "SUCCESS",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": BASE_URL,
        "month_start": "202301",
        "month_end": "202512",
        "months": 36,
        "filtered_event_count": len(filtered),
        "events_per_symbol": per_symbol,
        "events_sha256": hashlib.sha256(EVENTS.read_bytes()).hexdigest(),
        "monthly_raw_manifest": monthly,
        "includes_2026": False,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "SUCCESS", "events_per_symbol": per_symbol, "filtered_event_count": len(filtered)}, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
