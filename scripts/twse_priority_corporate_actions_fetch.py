from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request

PAGE_URL = "https://www.twse.com.tw/zh/announcement/ex-right/twt49u.html"
USER_AGENT = "TWSE-priority-universe-corporate-action-audit/1.0"
KEYWORDS = ("TWT49U", "twt49u", "strDate", "endDate", "startDate", "exchangeReport", "exRight")


def get(url: str) -> tuple[str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/javascript,*/*"})
    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
        return body, response.geturl()


def contexts(text: str, keyword: str, radius: int = 220):
    low = text.lower()
    needle = keyword.lower()
    pos = 0
    count = 0
    while True:
        idx = low.find(needle, pos)
        if idx < 0:
            return
        start = max(0, idx - radius)
        end = min(len(text), idx + len(keyword) + radius)
        yield re.sub(r"\s+", " ", html.unescape(text[start:end]))
        count += 1
        if count >= 8:
            return
        pos = idx + len(keyword)


def main() -> int:
    page, final_url = get(PAGE_URL)
    print(f"PAGE_FINAL_URL={final_url}")
    for keyword in KEYWORDS:
        for snippet in contexts(page, keyword):
            print(f"PAGE[{keyword}] {snippet}")

    script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', page, flags=re.I)
    print(f"SCRIPT_COUNT={len(script_srcs)}")
    for src in script_srcs:
        url = urllib.parse.urljoin(final_url, src)
        print(f"SCRIPT={url}")
        try:
            text, actual = get(url)
        except Exception as exc:
            print(f"SCRIPT_ERROR={url} {type(exc).__name__}: {exc}")
            continue
        matched = False
        for keyword in KEYWORDS:
            snippets = list(contexts(text, keyword))
            if snippets:
                matched = True
                for snippet in snippets:
                    print(f"JS[{keyword}] {snippet}")
        if matched:
            print(f"MATCHED_SCRIPT={actual}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
