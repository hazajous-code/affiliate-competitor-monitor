"""Turn a monthly placement plan (plans/YYYY-MM.txt) into site/data/placements.json.

Input lines: publisher;start;end;placement;OBS/PS;category[;offer copy]
Only matching fields are accepted — cost/performance columns must never be put in plans/.

Each placement gets an observation method:
  rate      the publisher's LG store-page rate should be raised during the window (cash back events)
  presence  LG should appear on a public page (home / category / offers) during the window
  partial   public page exists but the slot is targeted / rotating / portal-specific
  none      not observable without login (email, app, extension alerts, member-only platforms)
  n/a       not a placement (CPA terms, content fee, creative production)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
YEAR = 2026

PS_MEMBER = {"Next Jump", "Passport", "BenefitHub", "PerkSpot", "Life Balance", "EBG", "YouDecide",
             "MJH Life Sciences", "Stars and Stripes", "Access All"}


def parse_date(s, year=YEAR):
    s = s.strip()
    if not s or s.upper() == "TBD":
        return None
    parts = re.split(r"[/-]", s)
    m, d = int(parts[0]), int(parts[1])
    y = int(parts[2]) + 2000 if len(parts) > 2 and len(parts[2]) == 2 else (int(parts[2]) if len(parts) > 2 else year)
    return f"{y:04d}-{m:02d}-{d:02d}"


def classify(pub, name, cat):
    n = name.lower()
    tcb_cat = "tcb-cat-tech" if cat in ("Monitor", "TV") else "tcb-cat-appliances"
    rk_cat = "rakuten-cat-electronics" if cat in ("Monitor", "TV") else "rakuten-cat-home"
    if re.search(r"cpa only|^content$|creative development|q4 media|founders ?card", n):
        return "n/a", [], "지면이 아닌 계약·제작·일괄 매체 항목"
    if re.search(r"e-?mail|newsletter|eblast|perk alert|solo", n):
        return "none", [], "이메일 — 공개 웹에서 확인 불가"
    if re.search(r"\bapp\b", n):
        return "none", [], "앱 지면 — 공개 웹에서 확인 불가"
    if "account overview" in n:
        return "none", [], "로그인 후 계정 화면"
    if pub == "Rakuten":
        if re.search(r"cash back|flash cash|big stack|discover new stores", n):
            return "rate", ["rakuten-lg"], "Rakuten LG 상점 요율이 기간 중 상향 표시되는지"
        if re.search(r"similar store|price magic", n):
            return "none", [], "브라우저 확장·구매 흐름 안 노출"
        if "targeted" in n:
            return "partial", ["rakuten-home"], "타기팅 지면 — 비로그인 홈에는 안 보일 수 있음"
        if "homepage" in n:
            return "presence", ["rakuten-home", "rakuten-hotdeals"], "Rakuten 홈·Hot Deals 화면에 LG 노출"
        if "category page" in n:
            return "presence", [rk_cat], "Rakuten 카테고리 페이지에 LG 노출"
    if pub == "TopCashback":
        if "homepage" in n:
            return "presence", ["tcb-home"], "TopCashback 홈에 LG 노출"
        if re.search(r"category (carousel|navigation)", n):
            return "presence", [tcb_cat], "TopCashback 카테고리 페이지에 LG 노출"
        if re.search(r"featured offers|offer page", n):
            return "presence", ["tcb-offers"], "TopCashback 오퍼 페이지에 LG 노출"
        if "sweet deal" in n:
            return "partial", ["tcb-home", "tcb-offers"], "Sweet Deal 전용 페이지 주소 미확인 — 홈·오퍼 화면으로 대신 확인"
    if pub == "RetailMeNot" and "homepage" in n:
        return "presence", ["rmn-home"], "RetailMeNot 홈 Top Offers에 LG 노출"
    if pub == "Capital One":
        if "fall bonus days" in n and "email" not in n:
            return "rate", ["capone-lg"], "Capital One Shopping LG 리워드가 기간 중 상향되는지"
        if "landing page carousel" in n or "shop electronics offers" in n:
            return "partial", ["capone-lg"], "랜딩 페이지 주소 미확인 — LG 상점 페이지로 대신 확인"
        return "none", [], "카드회원 오퍼·브라우저 확장 알림 — 로그인 필요"
    if pub == "Cartera":
        return "partial", ["cartera-aa-home"], "항공 포털 홈(비로그인)에 보일 때만 확인 가능"
    if pub == "ID.me" and "homepage" in n:
        return "partial", ["idme-home"], "자격 그룹별 캐러셀 — 비로그인 홈에서 일부만 보일 수 있음"
    if pub == "GovX" and "homepage" in n:
        return "partial", ["govx-home"], "GovX 홈 슬라이더 — 화면 렌더링이 불안정"
    if pub == "Future Publishing":
        return "partial", ["techradar-deals", "tomsguide-deals"], "딜 기사 — 딜 목록 화면에 LG 기사 노출 여부로 확인"
    if pub in PS_MEMBER or pub == "ID.me":
        return "none", [], "회원 전용 플랫폼 — 로그인 필요"
    return "none", [], "공개 웹에서 확인할 경로 없음"


def main(path):
    rows = []
    for i, line in enumerate(Path(path).read_text().splitlines()):
        if not line.strip() or line.startswith("#"):
            continue
        f = [x.strip() for x in line.split(";")]
        pub, start, end, name, ch, cat = f[:6]
        offer = f[6] if len(f) > 6 else ""
        s, e = parse_date(start), parse_date(end)
        method, targets, how = classify(pub, name, cat)
        rows.append(dict(id=f"p{len(rows)+1:03d}", publisher=pub, placement=name, start=s, end=e,
                         channel="Partner Store" if ch in ("PS", "Partner Store") else "OBS",
                         category=cat, offer=offer, method=method, targets=targets, how=how))
    month = Path(path).stem
    out = ROOT / "site/data/placements.json"
    out.write_text(json.dumps({"month": month, "source": f"plans/{Path(path).name}", "placements": rows},
                              ensure_ascii=False, indent=1))
    from collections import Counter
    print(len(rows), Counter(r["method"] for r in rows))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT / "plans/2026-10.txt")
