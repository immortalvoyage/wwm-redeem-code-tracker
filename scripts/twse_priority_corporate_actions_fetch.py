from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

BASE_URL = "https://www.twse.com.tw/rwd/zh/exRight/TWT49U"
USER_AGENT = "TWSE-priority-universe-corporate-action-audit/1.0"
OUT = Path("twse_priority_universe_output/corporate_actions")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    params = urllib.parse.urlencode({"startDate": "20230101", "endDate": "20230131", "response": "json"})
    url = f"{BASE_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"})
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read()
        final_url = response.geturl()
        status = getattr(response, "status", 200)
    payload = json.loads(raw.decode("utf-8-sig"))
    evidence = {
        "status_code": status,
        "final_url": final_url,
        "stat": payload.get("stat"),
        "fields": payload.get("fields"),
        "row_count": len(payload.get("data") or []),
        "strDate": payload.get("strDate"),
        "endDate": payload.get("endDate"),
        "sample": (payload.get("data") or [])[:3],
    }
    (OUT / "rwd_api_probe.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True))
    if str(payload.get("stat", "")).lower() != "ok":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
