from __future__ import annotations

import urllib.error
import urllib.request

PAGE_URL = "https://www.twse.com.tw/zh/announcement/ex-right/twt49u.html"
USER_AGENT = "TWSE-priority-universe-corporate-action-audit/1.0"


def main() -> int:
    req = urllib.request.Request(PAGE_URL, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            print(f"STATUS={getattr(response, 'status', 200)}")
            print(f"FINAL_URL={response.geturl()}")
            print(response.read(500).decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        print(f"HTTP_STATUS={exc.code}")
        print(f"LOCATION={exc.headers.get('Location')}")
        print(f"CONTENT_TYPE={exc.headers.get('Content-Type')}")
        try:
            print(exc.read(500).decode("utf-8", errors="replace"))
        except Exception:
            pass
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
