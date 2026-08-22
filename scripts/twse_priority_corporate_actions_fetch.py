from __future__ import annotations

import calendar
import hashlib
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://www.twse.com.tw/rwd/zh/exRight/TWT49U"
SYMBOLS = {"00642U", "1721", "2312", "3607", "3706"}
USER_AGENT = "TWSE-priority-universe-corporate-action-audit/1.1"
OUT = Path("twse_priority_universe_output/corporate_actions")
RAW = OUT / "raw_twt49u"
EVENTS = OUT / "filtered_events.json"
SUMMARY = OUT / "corporate_action_summary.json"


def months():
    for year in range(2023, 2026):
        for month in range(1, 13):
            yield year, month


def fetch_month(year: int, month: int) -> tuple[bytes, str]:
    start = f"{year}{month:02d}01"
    end = f"{year}{month:02d}{calendar.monthrange(year, month)[1]:02d}"
    params = urllib.parse.urlencode({"startDate": start, "endDate": end, "response": "json"})
    url = f"{BASE_URL}?{params}"
    last = None
    for delay in (0, 1, 3, 6):
        if delay:
            time.sleep(delay)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                raw = response.read()
            payload = json.loads(raw.decode("utf-8-sig"))
            if str(payload.get("stat", "")).upper() != "OK":
                raise ValueError(f"TWSE stat={payload.get('stat')!r}")
            return raw, url
        except Exception as exc:
            last = exc
    raise RuntimeError(f"failed {start}..{end}: {type(last).__name__}: {last}")


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    monthly = []
    filtered = []
    field_signature = None

    for idx, (year, month) in enumerate(months(), start=1):
        key = f"{year}{month:02d}"
        print(f"[{idx:02d}/36] TWT49U {key}", flush=True)
        raw, url = fetch_month(year, month)
        payload = json.loads(raw.decode("utf-8-sig"))
        fields = [str(v) for v in (payload.get("fields") or [])]
        rows = payload.get("data") or []
        if field_signature is None:
            field_signature = fields
        elif fields != field_signature:
            raise RuntimeError(f"field schema changed at {key}")
        path = RAW / f"{key}.json"
        path.write_bytes(raw)
        monthly.append({
            "month": key,
            "rows": len(rows),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "source": url,
        })
        for row in rows:
            if not isinstance(row, list) or len(row) < 7:
                continue
            symbol = str(row[1]).strip()
            if symbol not in SYMBOLS:
                continue
            record = {field: value for field, value in zip(fields, row)}
            event_type = str(row[6]).strip()
            filtered.append({
                "month": key,
                "symbol": symbol,
                "date": str(row[0]).strip(),
                "event_type": event_type,
                "value_plus_dividend": str(row[5]).strip(),
                "contains_right": "權" in event_type,
                "contains_dividend": "息" in event_type,
                "record": record,
            })
        time.sleep(0.25)

    EVENTS.write_text(json.dumps(filtered, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    per_symbol = {}
    for symbol in sorted(SYMBOLS):
        events = [e for e in filtered if e["symbol"] == symbol]
        per_symbol[symbol] = {
            "events": len(events),
            "dividend_events": sum(bool(e["contains_dividend"]) for e in events),
            "right_events": sum(bool(e["contains_right"]) for e in events),
            "event_types": sorted({e["event_type"] for e in events}),
        }

    summary = {
        "schema_version": 3,
        "status": "SUCCESS",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": BASE_URL,
        "query_date_format": "YYYYMMDD",
        "month_start": "202301",
        "month_end": "202512",
        "months": 36,
        "symbols": sorted(SYMBOLS),
        "field_signature": field_signature,
        "filtered_event_count": len(filtered),
        "per_symbol": per_symbol,
        "events_sha256": hashlib.sha256(EVENTS.read_bytes()).hexdigest(),
        "monthly_raw_manifest": monthly,
        "includes_2026": False,
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "SUCCESS", "filtered_event_count": len(filtered), "per_symbol": per_symbol}, ensure_ascii=False, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
