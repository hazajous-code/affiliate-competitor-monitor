"""Daily capture of US affiliate publisher store pages (LG vs competitors).

For each target in targets.json:
  - opens the page in headless Chromium (US locale / New York time zone)
  - saves a viewport screenshot to site/shots/<date>/<target>.jpg
  - reads the visible text and pulls out the headline cash back / rewards rate
  - records whether the capture really worked (blocked, not found, no rate found)

Results are merged into site/data/captures.json (one row per date x target)
and the latest run is written to site/data/runs.json.
"""
import json
import re
import sys
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DATA = SITE / "data"
SHOTS = SITE / "shots"
KEEP_DAYS = 90

NY = ZoneInfo("America/New_York")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

BLOCK_HINTS = ["access denied", "just a moment", "verify you are human", "are you a robot",
               "captcha", "request blocked", "unusual traffic", "pardon our interruption"]
NOT_FOUND_HINTS = ["page not found", "404", "we couldn't find", "no results found", "0 results"]

PCT = r"(\d{1,2}(?:\.\d{1,2})?)\s*%"


def parse(parser, text):
    """Return (rate_float_or_None, rate_text_or_None)."""
    t = " ".join(text.split())
    pats = {
        "rakuten": [rf"((?:Up to\s+)?{PCT}\s*Cash Back(?:\s*was\s*{PCT})?)"],
        "tcb": [rf"(Get\s+(?:up to\s+)?{PCT}\s+of the price back)", rf"(Online Purchase\s+(?:Improved\s+)?(?:Up to\s+)?{PCT})"],
        "capone": [rf"(Rewards\s+((?:Up to\s+)?){PCT})", rf"((?:Up to\s+)?{PCT}\s+Rewards)"],
        "rmn": [rf"((?:Up to\s+)?{PCT}\s+Cash Back)"],
        "cartera": [r"((?:Up to\s+)?(\d{1,2}(?:\.\d)?)\s*(?:miles|Miles)\s*(?:/|per)\s*\$)"],
    }.get(parser, [rf"((?:Up to\s+)?{PCT}\s*(?:Cash Back|Rewards|back))"])
    for p in pats:
        m = re.search(p, t, flags=re.I)
        if m:
            nums = [g for g in m.groups()[1:] if g and re.fullmatch(r"\d+(?:\.\d+)?", g)]
            rate = float(nums[0]) if nums else None
            return rate, m.group(1).strip()
    return None, None


def classify(title, text, http_status, rate):
    low = (title + " " + text[:3000]).lower()
    if http_status and http_status >= 400 and http_status != 404:
        return "차단·오류", f"HTTP {http_status}"
    if any(h in low for h in BLOCK_HINTS):
        return "차단", "봇 확인 화면"
    if http_status == 404 or (rate is None and any(h in low[:600] for h in NOT_FOUND_HINTS)):
        return "페이지 없음", "주소 확인 필요"
    if rate is None:
        return "요율 미확인", "화면은 저장됨 — 요율 문구를 찾지 못함"
    return "수집", ""


def main():
    targets = json.loads((ROOT / "targets.json").read_text())
    only = set(sys.argv[1:])
    if only:
        targets = [t for t in targets if t["id"] in only]
    now = dt.datetime.now(NY)
    day = now.strftime("%Y-%m-%d")
    shot_dir = SHOTS / day
    shot_dir.mkdir(parents=True, exist_ok=True)

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, locale="en-US", timezone_id="America/New_York",
                                  viewport={"width": 1366, "height": 1500}, device_scale_factor=1)
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        for tg in targets:
            page = ctx.new_page()
            row = {k: tg[k] for k in ("publisher", "brand", "brand_group", "url")}
            row.update(date=day, target=tg["id"], method="자동 스크린샷")
            status_code = None
            try:
                resp = page.goto(tg["url"], wait_until="domcontentloaded", timeout=45000)
                status_code = resp.status if resp else None
                page.wait_for_timeout(5000)
                for sel in ["button:has-text('Accept')", "button:has-text('Got it')", "[aria-label='Close']"]:
                    try:
                        page.locator(sel).first.click(timeout=800)
                    except Exception:
                        pass
                title = page.title()
                text = page.inner_text("body", timeout=10000)
                rel = f"shots/{day}/{tg['id']}.jpg"
                page.screenshot(path=str(SITE / rel), type="jpeg", quality=55, full_page=False)
                rate, rate_text = parse(tg["parser"], text)
                st, why = classify(title, text, status_code, rate)
                row.update(rate=rate, rate_text=rate_text, status=st, reason=why, shot=rel,
                           final_url=page.url, http=status_code, title=title[:120])
            except Exception as e:  # timeout, DNS, etc.
                row.update(rate=None, rate_text=None, status="접속 실패", reason=str(e).split("\n")[0][:160],
                           shot=None, http=status_code)
            finally:
                page.close()
            print(f"{row['status']:<8} {tg['id']:<34} {row.get('rate_text')}")
            results.append(row)
        browser.close()

    # merge into history (replace same date+target)
    cap_path = DATA / "captures.json"
    hist = json.loads(cap_path.read_text()) if cap_path.exists() else []
    new_keys = {(r["date"], r["target"]) for r in results}
    hist = [h for h in hist if (h["date"], h["target"]) not in new_keys] + results
    hist.sort(key=lambda r: (r["date"], r["target"]))
    cap_path.write_text(json.dumps(hist, ensure_ascii=False, indent=1))

    (DATA / "runs.json").write_text(json.dumps({
        "run_at": now.isoformat(timespec="minutes"),
        "summary": {s: sum(1 for r in results if r["status"] == s) for s in sorted({r["status"] for r in results})},
        "results": results,
    }, ensure_ascii=False, indent=1))

    # keep the repo small: drop screenshot folders older than KEEP_DAYS
    cutoff = (now - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    for d in SHOTS.iterdir():
        if d.is_dir() and d.name < cutoff:
            for f in d.iterdir():
                f.unlink()
            d.rmdir()


if __name__ == "__main__":
    main()
