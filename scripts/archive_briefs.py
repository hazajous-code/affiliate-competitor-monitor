"""Save each day's 'today's summary' from the briefing page to site/data/briefs.json.

The summary is produced by the page itself (window.briefSummary), so the archive always matches
what people saw. Raw captures are pruned after 60 days; entries here are never pruned, and a date
that is no longer in the raw data keeps the text it was saved with.
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
OUT = SITE / "data" / "briefs.json"


def main():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=str(SITE))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/index.html"
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            errors = []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.goto(url)
            pg.wait_for_function("window.briefReady === true", timeout=30000)
            got = pg.evaluate("window.briefDates.map(d => [d, window.briefSummary(d)])")
            b.close()
        if errors:
            raise SystemExit("briefing page error: " + "; ".join(errors))
    finally:
        srv.shutdown()

    old = json.loads(OUT.read_text()) if OUT.exists() else {}
    now = dt.datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="minutes")
    changed = 0
    for day, bullets in got:
        if not bullets:
            continue
        if old.get(day, {}).get("bullets") != bullets:
            old[day] = {"bullets": bullets, "saved_at": now}
            changed += 1
    OUT.write_text(json.dumps(dict(sorted(old.items())), ensure_ascii=False, indent=1))
    print(f"briefs: {len(old)} days stored, {changed} updated")


if __name__ == "__main__":
    main()
