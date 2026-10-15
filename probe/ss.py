from playwright.sync_api import sync_playwright
import re,sys
urls=sys.argv[1:]
with sync_playwright() as p:
    b=p.chromium.launch()
    ctx=b.new_context(locale="en-US",timezone_id="America/New_York",viewport={"width":1366,"height":1500},
      user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
    try:
        print("country", ctx.request.get("https://api.country.is/").json())
    except Exception as e: print("country?",e)
    for i,u in enumerate(urls):
        pg=ctx.new_page()
        try:
            r=pg.goto(u,wait_until="domcontentloaded",timeout=45000); pg.wait_for_timeout(6000)
            pg.mouse.wheel(0,3000); pg.wait_for_timeout(1500); pg.mouse.wheel(0,-3000)
            t=re.sub(r"\s+"," ",pg.inner_text("body"))
            print("==",u,r.status if r else None,pg.url,pg.title(),len(t)); print(t[:1800])
            pg.screenshot(path=f"ss/{i}.jpg",type="jpeg",quality=45,full_page=True,clip={"x":0,"y":0,"width":1366,"height":3600})
        except Exception as e: print("ERR",u,e)
        pg.close()
