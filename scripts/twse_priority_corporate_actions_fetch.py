from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PAGE_URL = "https://www.twse.com.tw/zh/announcement/ex-right/twt49u.html"
USER_AGENT = "TWSE-priority-universe-corporate-action-audit/1.0"
KEYWORDS = ("TWT49U", "twt49u", "strDate", "endDate", "startDate", "exchangeReport", "exRight", "api")
OUT = Path("twse_priority_universe_output/corporate_actions")


def get(url: str) -> tuple[str, str]:
    last = None
    for delay in (0, 1, 3):
        if delay:
            time.sleep(delay)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/javascript,*/*"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                return response.read().decode("utf-8", errors="replace"), response.geturl()
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code not in {301, 302, 303, 307, 308}:
                raise
    raise RuntimeError(f"fetch failed after retries: {url}: {last}")


def snippets(text: str, keyword: str, radius: int = 260, limit: int = 12) -> list[str]:
    low = text.lower()
    needle = keyword.lower()
    out = []
    pos = 0
    while len(out) < limit:
        idx = low.find(needle, pos)
        if idx < 0:
            break
        start = max(0, idx - radius)
        end = min(len(text), idx + len(keyword) + radius)
        out.append(re.sub(r"\s+", " ", html.unescape(text[start:end])))
        pos = idx + len(keyword)
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    page, final_url = get(PAGE_URL)
    findings = {"page_url": PAGE_URL, "final_url": final_url, "page": {}, "scripts": []}
    for keyword in KEYWORDS:
        found = snippets(page, keyword)
        if found:
            findings["page"][keyword] = found

    script_srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', page, flags=re.I)
    for src in script_srcs:
        url = urllib.parse.urljoin(final_url, src)
        record = {"url": url, "matches": {}}
        try:
            text, actual = get(url)
            record["final_url"] = actual
            for keyword in KEYWORDS:
                found = snippets(text, keyword)
                if found:
                    record["matches"][keyword] = found
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        if record["matches"] or record.get("error"):
            findings["scripts"].append(record)

    path = OUT / "frontend_probe.json"
    path.write_text(json.dumps(findings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "SUCCESS", "script_count": len(script_srcs), "matched_scripts": len(findings["scripts"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
