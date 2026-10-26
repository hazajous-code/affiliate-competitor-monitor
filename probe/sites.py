import json, re
from pathlib import Path
from playwright.sync_api import sync_playwright
URLS = [
 "https://www.aadvantageeshopping.com/me____.htm?gmid=6190", "https://www.skymilesshopping.com/me____.htm?gmid=4889", "https://www.befrugal.com/store/lgelectronics/",
 "https://www.mypoints.com/samsung-coupons", "https://www.mypoints.com/coupons/samsung", "https://www.mypoints.com/shop/samsung",
 "https://www.upromise.com/samsung-coupons", "https://www.upromise.com/coupons/samsung", "https://www.upromise.com/shop/samsung",
 "https://www.swagbucks.com/shop/search?q=LG",
]
JS = r"""() => { const sq = s => (s||'').replace(/\s+/g,' ').trim();
  const re = /./;
  return [...new Set([...document.querySelectorAll('a[href]')].filter(a => re.test(a.href) || re.test(a.innerText)).map(a => sq(a.innerText).slice(0,60) + ' => ' + a.href))].slice(0, 120); }"""
out = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(locale="en-US", timezone_id="America/New_York", viewport={"width": 1366, "height": 1500})
    for i, u in enumerate(URLS):
        pg = ctx.new_page()
        try:
            r = pg.goto(u, wait_until="domcontentloaded", timeout=45000); pg.wait_for_timeout(5000)
            t = re.sub(r"\s+", " ", pg.inner_text("body"))
            rates = re.findall(r"[^.]{0,60}(?:\d+(?:\.\d+)?\s?%\s*cash back|\d+\s*(?:miles|points|pts|SB)\s*(?:/|per)\s*\$\s?1?|\d+(?:\.\d+)?\s*(?:miles|points|SB)\b)[^.]{0,40}", t, re.I)[:6]
            out[u] = {"status": r.status if r else None, "final": pg.url, "title": pg.title()[:120], "len": len(t), "head": t[:700], "rates": rates, "links": pg.evaluate(JS), "h1": pg.evaluate("() => [...document.querySelectorAll('h1,h2')].slice(0,4).map(h => { let b=h; for (let i=0;i<5&&b;i++,b=b.parentElement){ const t=(b.innerText||'').replace(/\\s+/g,' ').trim(); if (/\\d+(\\.\\d+)?\\s?(%|mile|point)/i.test(t)) return h.tagName+': '+t.slice(0,300);} return h.tagName+': '+(h.innerText||'').trim().slice(0,80); })")}
            pg.screenshot(path=f"probe/s{i}.jpg", type="jpeg", quality=40)
        except Exception as e:
            out[u] = {"error": str(e)[:160]}
        pg.close()
Path("probe/sites.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
