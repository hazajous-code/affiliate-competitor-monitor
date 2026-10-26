import json, re
from pathlib import Path
from playwright.sync_api import sync_playwright
URLS = [
 "https://www.aadvantageeshopping.com/b____.htm", "https://www.skymilesshopping.com/b____.htm", "https://rapidrewardsshopping.southwest.com/b____.htm",
 "https://www.atmosshopping.com/b____.htm", "https://shopping.mileageplus.com/", "https://www.mileageplusshopping.com/", "https://shopping.mileageplus.com/b____.htm",
 "https://www.swagbucks.com/shop/lg-electronics-coupons", "https://www.swagbucks.com/shop/lgcom-coupons", "https://www.swagbucks.com/shop/lg-com-coupons",
 "https://www.swagbucks.com/shop/whirlpool-coupons", "https://www.swagbucks.com/shop/allstores",
 "https://www.upromise.com/store/lg-electronics", "https://www.upromise.com/stores/lg", "https://www.upromise.com/shop/lg-electronics", "https://www.upromise.com/stores/all",
 "https://www.mypoints.com/", "https://www.mypoints.com/store/lg-electronics", "https://www.mypoints.com/stores/lg", "https://www.mypoints.com/stores/all",
]
JS = r"""() => { const sq = s => (s||'').replace(/\s+/g,' ').trim();
  const re = /\blg\b|lg-electronics|lgelectronics|lg\.com|samsung|whirlpool|ge-?appliances|frigidaire|\/stores?\//i;
  return [...new Set([...document.querySelectorAll('a[href]')].filter(a => re.test(a.href) || re.test(a.innerText)).map(a => sq(a.innerText).slice(0,60) + ' => ' + a.href))].slice(0, 40); }"""
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
            out[u] = {"status": r.status if r else None, "final": pg.url, "title": pg.title()[:120], "len": len(t), "head": t[:700], "rates": rates, "links": pg.evaluate(JS)}
            pg.screenshot(path=f"probe/s{i}.jpg", type="jpeg", quality=40)
        except Exception as e:
            out[u] = {"error": str(e)[:160]}
        pg.close()
Path("probe/sites.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
