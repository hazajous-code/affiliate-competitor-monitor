"""Save each day's 'today's summary' (site/data/briefs.json) and each week's digest
(site/data/weekly.json) from the dashboard pages.

The summaries are produced by the pages themselves (window.briefSummary / window.weekSummary), so the
archive always matches what people saw. Raw captures are pruned after 60 days; entries here are never
pruned, and a date or week that is no longer in the raw data keeps the text it was saved with.
"""
import datetime as dt
import functools
import http.server
import json
import threading
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

SITE = Path(__file__).resolve().parent.parent / "site"
DAILY = SITE / "data" / "briefs.json"
WEEKLY = SITE / "data" / "weekly.json"


def collect(base):
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(base + "index.html")
        pg.wait_for_function("window.briefReady === true", timeout=30000)
        daily = pg.evaluate("window.briefDates.map(d => [d, window.briefSummary(d)])")
        pg.goto(base + "weekly.html")
        pg.wait_for_function("window.weekReady === true", timeout=30000)
        weekly = pg.evaluate("window.weekKeys.map(w => [w, window.weekSummary(w)])")
        b.close()
    if errors:
        raise SystemExit("dashboard page error: " + "; ".join(errors))
    return daily, weekly


def merge(path, items, now, pick):
    old = json.loads(path.read_text()) if path.exists() else {}
    changed = 0
    for key, val in items:
        entry = pick(val)
        if not entry:
            continue
        cur = {k: v for k, v in old.get(key, {}).items() if k != "saved_at"}
        if cur != entry:
            old[key] = {**entry, "saved_at": now}
            changed += 1
    path.write_text(json.dumps(dict(sorted(old.items())), ensure_ascii=False, indent=1))
    return len(old), changed


def main():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=str(SITE))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        daily, weekly = collect(f"http://127.0.0.1:{srv.server_address[1]}/")
    finally:
        srv.shutdown()

    now = dt.datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="minutes")
    n, c = merge(DAILY, daily, now, lambda b: {"bullets": b} if b else None)
    print(f"briefs: {n} days stored, {c} updated")
    n, c = merge(WEEKLY, weekly, now, lambda w: {"label": w["label"], "days": w["days"], "bullets": w["bullets"]} if w and w.get("bullets") else None)
    print(f"weekly: {n} weeks stored, {c} updated")


if __name__ == "__main__":
    main()
