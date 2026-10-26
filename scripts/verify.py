"""Integrity checks run before every commit. Exits non-zero (and blocks the commit) on any failure.

- targets: unique ids, https URLs, known parser/access values
- captures: unique date x target, known statuses, rate only on collected rows,
  screenshot files exist and are JPEG
- runs: covers every enabled target exactly once
- public-safety: no internal figures or terms in anything that will be published
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
sys.path.insert(0, str(ROOT / "scripts"))
from capture import STATUSES  # noqa: E402

errors = []


def fail(msg):
    errors.append(msg)


targets = json.loads((ROOT / "targets.json").read_text())
ids = [t["id"] for t in targets]
if len(ids) != len(set(ids)):
    fail("duplicate target ids")
for t in targets:
    if not t["url"].startswith("https://"):
        fail(f"{t['id']}: url must be https")
    if t["parser"] not in {"rakuten", "tcb", "capone", "befrugal", "idme", "offers", "mentions", "slots", "lgpromo", "sspromo", "cartera", "swagbucks"}:
        fail(f"{t['id']}: unknown parser {t['parser']}")
    if t.get("access", "public") not in {"public", "entry_only"}:
        fail(f"{t['id']}: unknown access")

caps = json.loads((SITE / "data/captures.json").read_text())
keys = [(c["date"], c["target"]) for c in caps]
if len(keys) != len(set(keys)):
    fail("duplicate date x target rows in captures.json")
allowed = set(STATUSES) | {"수집(텍스트)"}
for c in caps:
    k = f"{c['date']} {c['target']}"
    if c["status"] not in allowed:
        fail(f"{k}: unknown status {c['status']}")
    if c.get("rate") is not None and c.get("kind") == "쿠폰":
        fail(f"{k}: a coupon/deal site carries a rate — its listed offers (e.g. welcome codes) are not a cash-back rate")
    if c.get("rate") is not None and c["status"] not in ("수집", "수집(텍스트)"):
        fail(f"{k}: rate recorded on a non-collected row")
    for b, crops in (c.get("mention_shots") or {}).items():
        for m in crops:
            q = SITE / m["shot"]
            if ".." in m["shot"] or not q.exists() or q.read_bytes()[:2] != b"\xff\xd8":
                fail(f"{k}: mention crop missing or not JPEG {m['shot']}")
    if c.get("shot"):
        p = SITE / c["shot"]
        if ".." in c["shot"] or not p.exists():
            fail(f"{k}: screenshot missing {c['shot']}")
        elif p.read_bytes()[:2] != b"\xff\xd8":
            fail(f"{k}: screenshot is not a JPEG")

# A site-wide banner read as the store rate makes every store on one portal show the same number.
by_day = {}
for c in caps:
    if c["target"].startswith("rakuten-") and c.get("rate") is not None:
        by_day.setdefault(c["date"], []).append(c["rate"])
for d, rates in by_day.items():
    if len(rates) >= 6 and len(set(rates)) == 1:
        fail(f"{d}: all {len(rates)} Rakuten stores read as {rates[0]}% — likely a site-wide banner, not the store rate")

runs = json.loads((SITE / "data/runs.json").read_text())
enabled = {t["id"] for t in targets if t.get("enabled", True)}
got = [r["target"] for r in runs.get("results", [])]
if runs.get("results") and (len(got) != len(set(got)) or set(got) != enabled):
    missing, extra = enabled - set(got), set(got) - enabled
    fail(f"runs.json does not match targets (missing {sorted(missing)[:5]}, extra {sorted(extra)[:5]})")
if re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", json.dumps({k: v for k, v in runs.items() if k != "results"})):
    fail("runs.json appears to contain an IP address")

# Placement plan: matching fields only.
pl = SITE / "data/placements.json"
if pl.exists():
    allowed_keys = {"id", "publisher", "placement", "start", "end", "channel", "category", "offer", "method", "targets", "how"}
    for r in json.loads(pl.read_text())["placements"]:
        extra = set(r) - allowed_keys
        if extra:
            fail(f"placements.json {r.get('id')}: non-matching fields {sorted(extra)}")
        for t in r["targets"]:
            if t not in ids:
                fail(f"placements.json {r['id']}: unknown target {t}")
    for f in (ROOT / "plans").glob("*.txt"):
        for no, line in enumerate(f.read_text().splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            cols = line.split(";")
            if len(cols) not in (6, 7):
                fail(f"{f.relative_to(ROOT)}:{no}: expected 6–7 matching fields, got {len(cols)}")
            elif any(re.search(r"\$\s?\d|\d+\.\d{2}\b", c) for c in cols[:6]):
                fail(f"{f.relative_to(ROOT)}:{no}: looks like an amount in a matching field")

# Public repository: internal performance data must never be published.
FORBIDDEN = re.compile(r"커미션|ROAS|매출|지면비|CJ ?Fee|Platform Rev|마젠토|Magento|GA ?Revenue|Advertiser Commission|Sale Amount", re.I)
for path in [ROOT / "targets.json", *sorted((SITE / "data").glob("*.json")), *sorted(SITE.glob("*.html")), *sorted((ROOT / "plans").glob("*.txt"))]:
    text = path.read_text(encoding="utf-8")
    m = FORBIDDEN.search(text)
    if m:
        fail(f"{path.relative_to(ROOT)}: forbidden internal term '{m.group(0)}'")

if errors:
    print("VERIFY FAILED")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print(f"verify ok: {len(targets)} targets, {len(caps)} capture rows, {len(set(c['date'] for c in caps))} dates")
