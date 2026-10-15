from playwright.sync_api import sync_playwright
import re,sys,json
urls=sys.argv[1:]
with sync_playwright() as p:
    b=p.chromium.launch()
    ctx=b.new_context(locale="en-US",timezone_id="America/New_York",viewport={"width":1366,"height":1500},
      user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
    for i,u in enumerate(urls):
        pg=ctx.new_page()
        try:
            r=pg.goto(u,wait_until="domcontentloaded",timeout=45000); pg.wait_for_timeout(5000)
            for sel in ["button:has-text('Continue')","button:has-text('Accept')","[aria-label='Close']"]:
                try: pg.locator(sel).first.click(timeout=800)
                except Exception: pass
            for k in range(12):
                pg.mouse.wheel(0,600); pg.wait_for_timeout(500)
            pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(1000)
            t=re.sub(r"\s+"," ",pg.inner_text("body"))
            print("==",u,r.status if r else None,pg.url,pg.title(),len(t)); print(t[:6000])
            links=pg.evaluate("""()=>[...new Set([...document.querySelectorAll('a[href]')].map(a=>a.href.split('?')[0]).filter(h=>/\\/us\\/(offer|shop\\/.*deal|.*offers?\\/)/.test(h)))]""")
            print("LINKS",json.dumps(links[:80]))
            pg.screenshot(path=f"ss/{i}.jpg",type="jpeg",quality=45,full_page=True,clip={"x":0,"y":0,"width":1366,"height":3600})
        except Exception as e: print("ERR",u,e)
        pg.close()
