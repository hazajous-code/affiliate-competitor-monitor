"""Dump the text around each store page's heading and its main call-to-action."""
import json, re, sys
from pathlib import Path
sys.path.insert(0, "scripts")
import capture as C
from playwright.sync_api import sync_playwright

JS = r"""
() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const sq = s => (s || '').replace(/\s+/g, ' ').trim();
  const up = (e, n) => { let box = e, t = ''; for (let i = 0; i < n && box; i++, box = box.parentElement) { t = sq(box.innerText); if (/\d+(?:\.\d+)?\s?%/.test(t)) return { t: t.slice(0, 600), depth: i, tag: box.tagName, cls: (box.className || '').toString().slice(0, 80) }; } return null; };
  const h1 = [...document.querySelectorAll('h1')].filter(vis).map(h => ({ h: sq(h.innerText).slice(0, 100), around: up(h, 6) }));
  const cta = [...document.querySelectorAll('a,button')].filter(e => vis(e) && /^(shop now|get cash back|activate|shop|go to store|get deal|earn now)/i.test(sq(e.innerText))).slice(0, 4).map(e => ({ cta: sq(e.innerText).slice(0, 40), around: up(e, 5) }));
  return { h1, cta };
}
"""
targets = [t for t in json.load(open("targets.json")) if t["parser"] in ("rakuten", "tcb", "capone", "befrugal", "idme") and t.get("enabled", True)]
out = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(locale="en-US", timezone_id="America/New_York", viewport={"width": 1366, "height": 1500},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
    for t in targets:
        pg = ctx.new_page()
        try:
            pg.goto(t["url"], wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(4000)
            txt = C.squash(pg.inner_text("body"))
            out[t["id"]] = {"dom": pg.evaluate(JS), "text_head": txt[:1500], "current": C.parse_rate(t["parser"], txt),
                            "terms": C.parse_terms(t["parser"], txt, t.get("brand") or "")[0]}
        except Exception as e:
            out[t["id"]] = {"error": str(e)[:200]}
        pg.close()
Path("probe/hdr.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
