"""Screenshot retention, run after every collection (before the integrity check).

- last 7 days: originals as captured
- older screenshots (incl. highlighted full-page mention shots): shrunk to 720px wide, JPEG quality 30
  (~5 MB/day, text stays readable), kept for 120 days on the dashboard
- brand-mention crops (shots/<day>/m/): kept for 365 days unchanged (~0.25 MB/day)
- safety budget: if site/shots grows past 850 MB (GitHub Pages limit is 1 GB), the oldest compressed
  full-page days are dropped first
- originals of every day are archived permanently by archive_shots.py (GitHub Releases) before they
  are compressed here
Rows that point at a removed image get their link cleared so the dashboard never shows a broken image.
"""
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SHOTS = SITE / "shots"
DATA = SITE / "data"
ORIGINAL_DAYS = 7
VIEW_DAYS = 120
CROP_DAYS = 365
BUDGET = 850 * 1024 * 1024
WIDTH, QUALITY = 720, 30
MARK = ".compressed"


def day_dirs():
    return sorted(d for d in SHOTS.iterdir() if d.is_dir() and len(d.name) == 10 and d.name[4] == "-")


def size(p):
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def compress(d):
    for f in d.glob("*.jpg"):              # full-page screenshots only; crops live in d/"m"
        im = Image.open(f)
        if im.width > WIDTH:
            im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
        im.convert("RGB").save(f, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    (d / MARK).write_text("compressed to %dpx / q%d\n" % (WIDTH, QUALITY))


def drop_full(d):
    for f in d.glob("*.jpg"):
        f.unlink()
    (d / MARK).unlink(missing_ok=True)


def drop_crops(d):
    m = d / "m"
    if m.is_dir():
        for f in m.glob("*"):
            f.unlink()
        m.rmdir()


def main():
    if not SHOTS.is_dir():
        return
    today = dt.datetime.now(ZoneInfo("America/New_York")).date()
    age = lambda d: (today - dt.date.fromisoformat(d.name)).days
    done = []
    for d in day_dirs():
        if age(d) > CROP_DAYS:
            drop_crops(d); done.append(f"{d.name}: crops removed")
        if age(d) > VIEW_DAYS and any(d.glob("*.jpg")):
            drop_full(d); done.append(f"{d.name}: full-page removed")
        elif age(d) > ORIGINAL_DAYS and any(d.glob("*.jpg")) and not (d / MARK).exists():
            compress(d); done.append(f"{d.name}: compressed")
    total = size(SHOTS)
    for d in day_dirs():                    # budget guard: oldest compressed full-page days go first
        if total <= BUDGET:
            break
        if (d / MARK).exists():
            before = size(d); drop_full(d); total -= before - size(d); done.append(f"{d.name}: full-page removed (budget)")
    for d in day_dirs():
        if not any(d.rglob("*.jpg")):
            for f in d.rglob("*"):
                if f.is_file():
                    f.unlink()
            for sub in sorted((x for x in d.rglob("*") if x.is_dir()), reverse=True):
                sub.rmdir()
            d.rmdir()

    # clear links to images that no longer exist
    exists = lambda rel: bool(rel) and (SITE / rel).exists()
    for name in ("captures.json", "runs.json"):
        p = DATA / name
        if not p.exists():
            continue
        doc = json.loads(p.read_text())
        rows = doc["results"] if name == "runs.json" else doc
        changed = False
        for r in rows:
            for key in ("shot", "full_shot"):
                if r.get(key) and not exists(r[key]):
                    r[key] = None; changed = True
            ms = r.get("mention_shots")
            if ms:
                kept = {b: [m for m in v if exists(m["shot"])] for b, v in ms.items()}
                kept = {b: v for b, v in kept.items() if v}
                if kept != ms:
                    r["mention_shots"] = kept; changed = True
        if changed:
            p.write_text(json.dumps(doc, ensure_ascii=False, indent=1))
    print(f"shots: {total / 1e6:.0f} MB", *(["· " + x for x in done] or ["· no changes"]), sep="\n")


if __name__ == "__main__":
    main()
