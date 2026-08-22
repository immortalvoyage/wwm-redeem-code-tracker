from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://www.twse.com.tw/exchangeReport/TWT49U"
USER_AGENT = "TWSE-priority-universe-corporate-action-audit/1.0"


def main() -> int:
    params = urllib.parse.urlencode({"response": "json", "strDate": "1120101", "endDate": "1120131"})
    url = f"{BASE_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            print(f"STATUS={getattr(response, 'status', 200)}")
            print(f"FINAL_URL={response.geturl()}")
            print(response.read(300).decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        print(f"HTTP_STATUS={exc.code}")
        print(f"LOCATION={exc.headers.get('Location')}")
        print(f"CONTENT_TYPE={exc.headers.get('Content-Type')}")
        try:
            print(exc.read(300).decode("utf-8", errors="replace"))
        except Exception:
            pass
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
