"""Daily capture of US affiliate publisher pages (LG vs appliance competitors).

For each target in targets.json:
  - opens the page in headless Chromium (en-US, New York time zone)
  - saves a viewport screenshot to site/shots/<date>/<target>.jpg
  - reads the visible text and pulls out what the target type allows:
      store pages  -> headline cash back / rewards rate, rates by category, exclusion text
      coupon pages -> number of offers and the top offer
      deal/review  -> brand mention counts only
  - classifies the outcome (collected / rate not found / login entrance only /
    bot check / render failed / page not found / blocked / connection failed)
  - fingerprints the extracted values and the page body to flag day-over-day changes

The run also records the outgoing country code (never the IP address).

Outputs (site/data):
  captures.json  one row per US-Eastern date x target (latest run of the day wins)
  captures.csv   same rows, flattened, for download
  runs.json      the latest run with every target's outcome
"""
import csv
import datetime as dt
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DATA = SITE / "data"
SHOTS = SITE / "shots"
KEEP_DAYS = 60

NY = ZoneInfo("America/New_York")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

BLOCK_HINTS = ["access denied", "just a moment", "verify you are human", "are you a robot",
               "captcha", "request blocked", "unusual traffic", "pardon our interruption",
               "checking your browser", "press & hold"]
NOT_FOUND_HINTS = ["page not found", "404", "we couldn't find", "no results found", "0 results",
                   "page you requested", "doesn't exist", "does not exist"]

# Brands counted on every page. Patterns avoid obvious false hits (e.g. "LG" inside words).
BRANDS = {
    "LG": r"\bLG\b",
    "Samsung": r"\bSamsung\b",
    "Sony": r"\bSony\b",
    "GE Appliances": r"\bGE (?:Appliances|Profile)\b|\bGE Café\b",
    "Whirlpool": r"\bWhirlpool\b",
    "Frigidaire": r"\bFrigidaire\b",
    "Dyson": r"\bDyson\b",
    "Hisense": r"\bHisense\b",
    "TCL": r"\bTCL\b",
    "Bosch": r"\bBosch\b",
    "KitchenAid": r"\bKitchenAid\b",
    "Maytag": r"\bMaytag\b",
    "Shark": r"\bShark(?:Ninja)?\b",
    "Vizio": r"\bVizio\b",
}

PCT = r"(\d{1,2}(?:\.\d{1,2})?)\s*%"
STATUSES = ["수집", "요율 미확인", "로그인 입구만", "봇 확인 화면", "렌더링 실패",
            "페이지 없음", "차단(HTTP)", "접속 실패"]


def squash(text):
    return " ".join(text.split())


def short(s, n=320):
    s = squash(s or "")
    return s if len(s) <= n else s[: n - 1] + "…"


# ---------- headline rate ----------
def parse_rate(parser, t):
    """Return (rate, rate_text) from collapsed page text."""
    if re.search(r"Cash Back is currently not available for", t, re.I):
        return 0.0, "캐시백 미제공(현재 중단)"
    pats = {
        "rakuten": [rf"((?:Up to\s+)?{PCT}\s*Cash Back(?:\s*was\s*{PCT})?)"],
        "tcb": [rf"(Get\s+(?:up to\s+)?{PCT}\s+of the price back)",
                rf"(Online Purchase\s+(?:Improved\s+)?(?:Up to\s+)?{PCT})"],
        "capone": [rf"(Rewards\s+((?:Up to\s+)?){PCT})", rf"((?:Up to\s+)?{PCT}\s+Rewards)"],
        # the store rate sits right above the "Shop Now" button; the nav bar also says "10% Cash Back"
        "befrugal": [rf"((?:up to\s+)?{PCT}\s*Cash Back)\s+Shop Now"],
        "idme": [rf"(Up to\s+{PCT}\s*cash back)"],
    }.get(parser, [])
    for p in pats:
        m = re.search(p, t, flags=re.I)
        if m:
            nums = [g for g in m.groups()[1:] if g and re.fullmatch(r"\d+(?:\.\d+)?", g)]
            return (float(nums[0]) if nums else None), m.group(1).strip()
    return None, None


# ---------- rates by category + exclusion text ----------
def parse_terms(parser, t, brand):
    cats, excl = [], None
    if parser == "rakuten":
        seg = re.search(r"Here's how much you'll earn(.*?)(?:About |Terms & Exclusions|$)", t, re.I)
        if seg:
            for rate, label in re.findall(r"(\d+(?:\.\d+)?)% Cash Back\s+(.*?)(?=\s\d+(?:\.\d+)?% Cash Back|$)", seg.group(1)):
                cats.append({"label": short(label.replace(" | ", ", ").replace("|", ","), 140), "rate": float(rate)})
        m = re.search(r"Exclusions:\s*(.*?)(?:Special Terms:|Posting Time|Free Shipping|$)", t)
        excl = m.group(1) if m else None
    elif parser == "tcb":
        seg = re.search(r"Our customers love us!(.*?)(?:promotions|Read more|Cash Back terms|$)", t, re.I)
        if seg:
            s = re.sub(rf"^\s*{re.escape(brand)}\s+Cash Back\s*", "", seg.group(1).strip(), flags=re.I)
            for label, flag, rate in re.findall(r"([A-Za-z][^%]{1,70}?)\s+(Improved\s+|Increased\s+)?(?:Up to\s+)?(\d+(?:\.\d+)?)%", s):
                cats.append({"label": short(label, 80) + (" (상향)" if flag else ""), "rate": float(rate)})
        m = re.search(r"Cash Back terms and exclusions\s+Exclusions\s+(.*?)\s+Terms\s", t)
        excl = m.group(1) if m else None
    elif parser == "capone":
        for label, rate in re.findall(r"Category Rewards\s+(.+?)\s+(\d+(?:\.\d+)?)%", t):
            cats.append({"label": short(label, 80), "rate": float(rate)})
        m = re.search(r"exclusions apply:\s*(.*?)(?:Activate|Rewards By Categories|$)", t, re.I)
        excl = m.group(1) if m else None
    elif parser == "idme":
        m = re.search(r"save up to (\d+)% off ([^.*]{0,80})", t, re.I)
        if m:
            cats.append({"label": "자격 대상 할인: " + short(m.group(2), 80), "rate": float(m.group(1)), "kind": "discount"})
        m = re.search(r"Restrictions\s+(.*?)(?:Read more|Discounts just for you|$)", t)
        excl = m.group(1) if m else None
    return cats, (short(excl) if excl else None)


# ---------- coupon pages ----------
def parse_offers(t):
    count_pats = [
        r"(\d[\d,]*)\s+VERIFIED OFFERS",                                   # RetailMeNot
        r"(\d[\d,]*)\s+Available Deals",                                   # Savings.com
        r"\bUse (\d[\d,]*)\s+[\w'&.\- ]{1,30}?\s+(?:promo|coupon|discount) codes",  # TechRadar / Tom's Guide
        r"(?<![\d,$])(\d{1,3})\s+(?:verified\s+|active\s+|working\s+|valid\s+|live\s+)?(?:coupons|promo codes|coupon codes|offers|deals)\b",
    ]
    n = next((m for m in (re.search(p, t, re.I) for p in count_pats) if m), None)
    top = (re.search(r"Today's top offer\s+((?:UP TO\s+)?[\d$.,]+%?\s*OFF)", t, re.I)
           or re.search(r"Top Offer\s+((?:up to\s+)?[\d$.,]+%?\s*OFF)", t, re.I)
           or re.search(r"((?:up to\s+)?(?:\d{1,2}%|\$\d[\d,]*)\s+off)", t, re.I))
    cb = re.search(rf"((?:Up to\s+)?{PCT}\s+Cash Back)", t, re.I)
    parts = []
    if n:
        parts.append(f"오퍼 {n.group(1)}건")
    if top:
        parts.append("최상단 " + top.group(1).title())
    if cb:
        parts.append(cb.group(1))
    count = int(n.group(1).replace(",", "")) if n else None
    return (float(cb.group(2)) if cb else None), (" · ".join(parts) or None), count


def mentions(t):
    out = {}
    for b, p in BRANDS.items():
        c = len(re.findall(p, t))
        if c:
            out[b] = c
    return out


PROMO_JS = r"""
() => {
  const out = [], seen = new Set();
  const valid = /(valid|ends?|through|thru|offer ends)[^0-9]{0,20}(\d{1,2}\/\d{1,2}(?:\/\d{2,4})?)/i;
  for (const a of document.querySelectorAll('a[href*="/promotions/"], a[href*="-deal"], a[href*="-sale"], a[href*="savings"]')) {
    let box = a, txt = '';
    for (let i = 0; i < 5 && box; i++, box = box.parentElement) {
      txt = (box.innerText || '').replace(/\s+/g, ' ').trim();
      if (valid.test(txt) && txt.length < 700) break;
    }
    if (!txt || !valid.test(txt) || txt.length >= 700) continue;
    const href = a.href.split('?')[0];
    if (seen.has(href)) continue;
    seen.add(href);
    out.push({ text: txt, href });
  }
  return out.slice(0, 30);
}
"""

PROMO_CATS = [("TV·AV", r"\bTVs?\b|OLED|QNED|sound ?bar|projector|home theater|StanbyME"),
              ("모니터·PC", r"monitor|laptop|\bgram\b|UltraGear|workspace|Odyssey|ViewFinity"),
              ("세탁", r"wash|dryer|laundry|WashTower|Styler"),
              ("냉장고", r"refrigerator|fridge|InstaView|freezer"),
              ("주방", r"range|oven|cooktop|microwave|dishwasher|kitchen|cooking"),
              ("가전 전반", r"appliance"),
              ("청소·공조", r"vacuum|CordZero|air ?condition|purifier|dehumid"),
              ("오디오", r"speaker|earbud|xboom|audio")]


def extract_lg_promos(page):
    """Promotion cards on LG.com: headline, discount, 'valid through' date, link."""
    try:
        raw = page.evaluate(PROMO_JS)
    except Exception:
        return []
    out = []
    for c in raw:
        t = c["text"]
        m = re.search(r"(?:valid|ends?|through|thru|offer ends)[^0-9]{0,20}(\d{1,2}/\d{1,2}(?:/\d{2,4})?)", t, re.I)
        body = re.sub(r"(?i)(?:valid|offer ends|ends)\s*(?:through|thru)?\s*:?\s*\d{1,2}/\d{1,2}(?:/\d{2,4})?\.?", " ", t)
        title = re.split(r"(?i)\s(?:shop now|learn more|see details|shop deals?)\b", " " + body.strip())[0].strip(" .:-|*")
        if not title:
            title = body.strip()
        if len(title) > 160:
            title = title[:159] + "…"
        disc = re.search(r"(?i)((?:save |up to |extra |an extra )*(?:\$[\d,]+|\d{1,2}(?:\s*-\s*\d{1,2})?%)(?:\s*off)?)", t)
        cats = [name for name, pat in PROMO_CATS if re.search(pat, t, re.I)]
        out.append({"title": title or short(t, 120), "valid": m.group(1) if m else None,
                    "discount": disc.group(1) if disc else None,
                    "category": cats[0] if cats else "기타", "url": c["href"]})
    return out


SS_PROMO_JS = r"""
() => {
  const SAV = /(save|\boff\b|extra|\bback\b|\bfree\b|on us|buy one get one|bogo|credit|\$\d|\d+\s?%)/i;
  const CTA = /(shop now|learn more|buy now|\bwatch\b|sign up|\bshop\b|see offer|get offer|view more)/i;
  const BAD = /(current price|add to wishlist|product ratings|number of ratings|original price)/i;
  const cands = [];
  for (const e of document.querySelectorAll('div,li,article,section')) {
    const t = (e.innerText || '').replace(/\s+/g, ' ').trim();
    if (t.length < 25 || t.length > 420) continue;
    if (!SAV.test(t) || !CTA.test(t) || BAD.test(t)) continue;
    if (e.closest('[role=tablist]') || e.querySelectorAll('[role=tab],[role=tablist]').length) continue;  // carousel tab labels
    cands.push([e, t]);
  }
  const keep = cands.filter(([e]) => !cands.some(([f]) => f !== e && e.contains(f)));
  const out = [], seen = new Set();
  for (const [e, t] of keep) {
    if (seen.has(t)) continue; seen.add(t);
    let a = e.querySelector('a[href]'), x = e;
    for (let i = 0; !a && i < 3 && x; i++) { x = x.parentElement; a = x && x.closest('a[href]'); }
    const href = a ? a.href.split('?')[0] : null;
    out.push({ text: t, href });
  }
  return out.slice(0, 40);
}
"""

SS_EXTRA_CATS = [("모바일", r"Galaxy (?:Z|S\d|A\d|Tab|Watch|Buds|Book|Fold|Flip)|smartphone|phone|wearable"),
                 ("결제·금융", r"Galaxy Card|PayPal|Affirm|\bAPR\b|pay over time|financ"),
                 ("행사·프로그램", r"Samsung Week|trade.?in|Offer Program|student|educator|carrier|Rewards")]
CTA_RE = r"(?i)(?:(?<=[\s.,!])|^)(?:shop now|learn more|buy now|sign up|see offer|get offer|view more|shop)\b"
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _ss_valid(t, page_text, raw=""):
    """End date as M/D/YY. Card text first, then the page's own footnotes keyed by the card's marker."""
    for mk in re.findall(r"[\u0370-\u04FF\u20A0-\u20CF\u2200-\u22FF\u1E00-\u1EFF\uA720-\uA7FF]", raw):
        f = re.search(re.escape(mk) + r"\s*(?:valid\s*)?(?:through|thru)\s*(\d{1,2}/\d{1,2}/\d{2,4})", page_text, re.I)
        if f:
            return f.group(1)
    m = re.search(r"(?i)(?:valid|through|thru|ends?|until)\s*(?:through|thru)?\s*:?\s*(\d{1,2}/\d{1,2}/\d{2,4})", t)
    if m:
        return m.group(1)
    m = re.search(r"(?i)~\s*([A-Z][a-z]{2})[a-z]*\.?\s*(\d{1,2})\.?,?\s*(\d{4})", t)
    if m and m.group(1).lower() in MONTHS:
        return f"{MONTHS[m.group(1).lower()]}/{int(m.group(2))}/{m.group(3)[2:]}"
    return None


def extract_ss_promos(page, page_cat=None, page_text=""):
    """Offer banners on Samsung.com/us offer pages: headline, saving, end date when shown, link.
    Product price tiles are excluded — only promotional offers."""
    try:
        raw = page.evaluate(SS_PROMO_JS)
    except Exception:
        return []
    out = []
    for c in raw:
        t = re.sub(r"[^\x20-\x7E\u2122\u00AE\u2014\u2013\u2019]", "", c["text"]).strip()
        t = re.sub(r"\s+", " ", t)
        t = re.sub(r"(?i)^(?:shop now|learn more|buy now|shop|watch)\s*-\s*", "", t)
        title = re.split(CTA_RE, t)[0].strip(" .:-|*")
        title = re.sub(r"(?i)\s+watch$", "", title)
        if len(title) < 12:
            title = t
        if len(title) > 160:
            title = title[:159] + "…"
        disc = re.search(r"(?i)((?:save |up to |an extra |extra |get )*(?:\$[\d,]+(?:\.\d{2})?|\d{1,2}(?:\s*-\s*\d{1,2})?\s?%)(?:\s*(?:off|back|cash rewards))?)", t)
        cats = [name for name, pat in PROMO_CATS + SS_EXTRA_CATS if re.search(pat, t, re.I)]
        out.append({"title": title, "valid": _ss_valid(t, page_text, c["text"]), "discount": disc.group(1).strip() if disc else None,
                    "category": cats[0] if cats else (page_cat or "기타"), "url": c["href"]})
    # Sale-event windows written as "Valid from Oct 12. 2026 ~ Nov 01. 2026" (e.g. Samsung Week)
    for m in re.finditer(r"Valid from ([A-Z][a-z]{2})[a-z]*\.? (\d{1,2})\.?,? (\d{4}) ~ ([A-Z][a-z]{2})[a-z]*\.? (\d{1,2})\.?,? (\d{4})", page_text):
        before = re.split(r"(?i)learn more|shop now|terms apply|buy now|\bnext\b|previous", page_text[max(0, m.start() - 120):m.start()])[-1].strip(" .")
        if m.group(4).lower()[:3] in MONTHS and before:
            out.append({"title": before[:120], "valid": f"{MONTHS[m.group(4).lower()[:3]]}/{int(m.group(5))}/{m.group(6)[2:]}",
                        "discount": None, "category": "행사·프로그램", "url": None})
    # drop exact repeats and shorter titles that are a prefix of a longer one
    keep, seen = [], set()
    for o in sorted(out, key=lambda o: -len(o["title"])):
        k = o["title"].lower()
        if k[:80] in seen or any(x.startswith(k) for x in seen):
            continue
        seen.add(k)
        keep.append(o)
    order = {id(o): i for i, o in enumerate(out)}
    return sorted(keep, key=lambda o: order[id(o)])


def lg_snippets(t, limit=6):
    """Short text around each LG mention — the evidence shown next to a placement."""
    out = []
    for m in re.finditer(r"\bLG\b", t):
        a, b = max(0, m.start() - 70), min(len(t), m.end() + 90)
        snip = ("…" if a else "") + t[a:b].strip() + ("…" if b < len(t) else "")
        key = t[m.start():m.start() + 40]
        if not any(key in o for o in out):
            out.append(snip)
        if len(out) >= limit:
            break
    return out


def classify(tg, title, t, http_status, rate, rate_text, final_url):
    low = (title + " " + t[:3000]).lower()
    if http_status and http_status >= 400 and http_status != 404:
        return "차단(HTTP)", f"HTTP {http_status}"
    if any(h in low for h in BLOCK_HINTS):
        return "봇 확인 화면", "보안 확인 화면만 열림 — 우회하지 않음"
    if len(t) < 150:
        return "렌더링 실패", "본문이 거의 표시되지 않음"
    if http_status == 404 or any(h in low[:700] for h in NOT_FOUND_HINTS):
        return "페이지 없음", "주소 확인 필요"
    if urlparse(final_url).path in ("", "/") and urlparse(tg["url"]).path not in ("", "/"):
        return "페이지 없음", "홈 화면으로 이동됨"
    if tg.get("access") == "entry_only":
        return "로그인 입구만", "공개 소개·로그인 화면까지만 확인. 회원 전용 혜택은 수집하지 않음"
    if tg["parser"] in ("rakuten", "tcb", "capone", "befrugal", "idme") and rate is None:
        return "요율 미확인", "화면은 저장됨 — 요율 문구를 찾지 못함"
    if tg["parser"] in ("lgpromo", "sspromo") and rate_text is None and not tg.get("promo_optional"):
        return "요율 미확인", "화면은 저장됨 — 프로모션 문구를 찾지 못함"
    if tg["parser"] == "offers" and rate_text is None:
        return "요율 미확인", "화면은 저장됨 — 오퍼 수를 찾지 못함"
    return "수집", ""


def fp(*parts):
    return hashlib.sha1(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]


def check_country(ctx):
    for url, key in [("https://ipapi.co/json/", "country_code"), ("https://api.country.is/", "country")]:
        try:
            r = ctx.request.get(url, timeout=15000)
            if r.ok:
                c = r.json().get(key)
                if c:
                    return c
        except Exception:
            pass
    return None


def capture_one(ctx, tg, day):
    page = ctx.new_page()
    row = {k: tg.get(k) for k in ("publisher", "brand", "brand_group", "kind", "url")}
    row.update(date=day, target=tg["id"], method="자동 스크린샷",
               captured_at=dt.datetime.now(NY).isoformat(timespec="minutes"))
    http = None
    try:
        resp = page.goto(tg["url"], wait_until="domcontentloaded", timeout=45000)
        http = resp.status if resp else None
        try:
            page.wait_for_load_state("load", timeout=10000)
        except Exception:
            pass
        page.wait_for_timeout(3500)
        # dismiss cookie bars and sign-up modals so the evidence is readable
        for sel in ["button:has-text('Accept')", "button:has-text('Got it')", "button:has-text('Close')",
                    "button:has-text('Dismiss')", "button:has-text('No thanks')",
                    "[aria-label='Close']", "[aria-label='close']", "[aria-label*='Close modal']"]:
            try:
                page.locator(sel).first.click(timeout=600)
            except Exception:
                pass
        if tg["parser"] == "sspromo":
            # Samsung's cookie notice only closes with "Continue"; its tiles load as you scroll
            try:
                page.locator("button:has-text('Continue')").first.click(timeout=1500)
            except Exception:
                pass
            for _ in range(12):
                page.mouse.wheel(0, 600)
                page.wait_for_timeout(450)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(800)
        page.keyboard.press("Escape")
        page.wait_for_timeout(600)
        title = page.title()
        text = page.inner_text("body", timeout=10000)
        t = squash(text)
        rel = f"shots/{day}/{tg['id']}.jpg"
        if tg["parser"] in ("slots", "lgpromo", "sspromo"):
            # placement / promotion pages: scroll once so lazy tiles render, then keep the top 3,600px
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(1500)
            page.mouse.wheel(0, -3000)
            page.wait_for_timeout(500)
            text = page.inner_text("body", timeout=10000)
            t = squash(text)
            h = min(3600, page.evaluate("document.documentElement.scrollHeight"))
            page.screenshot(path=str(SITE / rel), type="jpeg", quality=45, full_page=True,
                            clip={"x": 0, "y": 0, "width": 1366, "height": h})
        else:
            page.screenshot(path=str(SITE / rel), type="jpeg", quality=55, full_page=False)

        rate = rate_text = offers = None
        cats, excl = [], None
        promos = []
        if tg["parser"] in ("lgpromo", "sspromo"):
            promos = extract_lg_promos(page) if tg["parser"] == "lgpromo" else extract_ss_promos(page, tg.get("promo_cat"), t)
            rate_text = f"프로모션 {len(promos)}건" if promos else None
        elif tg["parser"] == "offers":
            rate, rate_text, offers = parse_offers(t)
        elif tg["parser"] not in ("mentions", "slots", "sspromo"):
            rate, rate_text = parse_rate(tg["parser"], t)
            cats, excl = parse_terms(tg["parser"], t, tg.get("brand") or "")
            if tg["parser"] == "idme" and cats:
                rate_text = f"할인 최대 {cats[0]['rate']:g}%" + (f" · {rate_text}" if rate_text else "")
        st, why = classify(tg, title, t, http, rate, rate_text, page.url)
        ok = st in ("수집", "요율 미확인", "로그인 입구만")
        row.update(rate=rate if st == "수집" else None, rate_text=rate_text if ok else None,
                   offers=offers, categories=cats if ok else [], exclusions=excl if ok else None,
                   promos=promos if ok else [],
                   mentions=mentions(t) if st in ("수집", "요율 미확인") else {},
                   lg_snippets=lg_snippets(t) if tg["parser"] == "slots" and st == "수집" else [],
                   status=st, reason=why, shot=rel, final_url=page.url, http=http, title=short(title, 120),
                   sig=fp(rate_text, cats, excl, offers, [(p["title"], p["valid"]) for p in promos]) if ok else None,
                   body_hash=fp(t) if ok else None)
    except Exception as e:  # timeout, DNS, crash
        row.update(rate=None, rate_text=None, offers=None, categories=[], exclusions=None, mentions={},
                   status="접속 실패", reason=short(str(e).split("\n")[0], 160), shot=None, http=http,
                   sig=None, body_hash=None)
    finally:
        page.close()
    return row


def annotate_changes(results, hist):
    """Compare each result with the same target's latest earlier date."""
    prev = {}
    for h in sorted(hist, key=lambda r: r["date"]):
        if h.get("sig") or h.get("rate_text") is not None:
            prev[(h["target"], h["date"])] = h
    for r in results:
        earlier = [h for (tid, d), h in prev.items() if tid == r["target"] and d < r["date"]]
        if not earlier:
            r.update(prev_date=None, changed=None, body_changed=None, prev_rate_text=None)
            continue
        p = max(earlier, key=lambda h: h["date"])
        same_val = (p.get("rate_text"), p.get("rate")) == (r.get("rate_text"), r.get("rate"))
        same_sig = p.get("sig") is None or r.get("sig") is None or p.get("sig") == r.get("sig")
        r.update(prev_date=p["date"], prev_rate_text=p.get("rate_text"), prev_rate=p.get("rate"),
                 changed=(not same_val) or (not same_sig) if r.get("status") == "수집" else None,
                 body_changed=(p.get("body_hash") != r.get("body_hash")) if p.get("body_hash") and r.get("body_hash") else None)


CSV_COLS = ["date", "captured_at", "publisher", "kind", "brand", "brand_group", "status", "rate", "rate_text",
            "offers", "categories", "exclusions", "mentions", "changed", "prev_date", "prev_rate_text",
            "reason", "url", "shot"]


def write_csv(hist):
    with open(DATA / "captures.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS, extrasaction="ignore")
        w.writeheader()
        for r in hist:
            row = dict(r)
            row["categories"] = "; ".join(f"{c['label']} {c['rate']:g}%" for c in r.get("categories") or [])
            row["mentions"] = "; ".join(f"{k} {v}" for k, v in (r.get("mentions") or {}).items())
            w.writerow(row)


def main():
    from playwright.sync_api import sync_playwright

    all_targets = json.loads((ROOT / "targets.json").read_text())
    only = set(a for a in sys.argv[1:] if a.strip())
    targets = [t for t in all_targets if t.get("enabled", True) and (not only or t["id"] in only)]
    now = dt.datetime.now(NY)
    day = now.strftime("%Y-%m-%d")
    (SHOTS / day).mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=UA, locale="en-US", timezone_id="America/New_York",
                                  viewport={"width": 1366, "height": 1500}, device_scale_factor=1)
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        country = check_country(ctx)
        print("country:", country or "unknown")
        results = []
        for tg in targets:
            row = capture_one(ctx, tg, day)
            row["country"] = country
            print(f"{row['status']:<8} {tg['id']:<34} {row.get('rate_text')}")
            results.append(row)
        # one retry for transient failures (timeouts, bot checks, blank renders) with a fresh page
        retry = {"접속 실패", "봇 확인 화면", "렌더링 실패"}
        by_id = {t["id"]: t for t in targets}
        for i, row in enumerate(results):
            if row["status"] in retry:
                time.sleep(8)
                again = capture_one(ctx, by_id[row["target"]], day)
                again["country"] = country
                if again["status"] not in retry or again["status"] != row["status"]:
                    again["reason"] = ((again.get("reason") or "") + " (재시도)").strip()
                    results[i] = again
                print(f"retry   {row['target']:<34} {row['status']} -> {again['status']}")
        browser.close()

    cap_path = DATA / "captures.json"
    hist = json.loads(cap_path.read_text()) if cap_path.exists() else []
    annotate_changes(results, hist)
    new_keys = {(r["date"], r["target"]) for r in results}
    hist = [h for h in hist if (h["date"], h["target"]) not in new_keys] + results
    hist.sort(key=lambda r: (r["date"], r["target"]))
    cap_path.write_text(json.dumps(hist, ensure_ascii=False, indent=1))
    write_csv(hist)

    # A partial re-run (target ids given) replaces only those targets' rows and keeps the rest,
    # so runs.json always covers every enabled target. run_at only moves on a full run,
    # because the dashboard's freshness check is about the daily full capture.
    runs_path = DATA / "runs.json"
    prev = json.loads(runs_path.read_text()) if runs_path.exists() else {}
    run_at = now.isoformat(timespec="minutes")
    partial_at = None
    if only:
        done = {r["target"] for r in results}
        enabled = {t["id"] for t in all_targets if t.get("enabled", True)}
        results = [r for r in prev.get("results", []) if r["target"] not in done and r["target"] in enabled] + results
        run_at, partial_at = prev.get("run_at") or run_at, now.isoformat(timespec="minutes")
    order = {t["id"]: i for i, t in enumerate(all_targets)}
    results.sort(key=lambda r: order.get(r["target"], 999))
    runs_path.write_text(json.dumps({
        "run_at": run_at,
        "partial_at": partial_at,
        "country": country,
        "us_ip_verified": country == "US",
        "summary": {s: sum(1 for r in results if r["status"] == s) for s in STATUSES if any(r["status"] == s for r in results)},
        "results": results,
    }, ensure_ascii=False, indent=1))

    cutoff = (now - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    for d in SHOTS.iterdir():
        if d.is_dir() and d.name < cutoff:
            for f in d.iterdir():
                f.unlink()
            d.rmdir()


if __name__ == "__main__":
    main()
