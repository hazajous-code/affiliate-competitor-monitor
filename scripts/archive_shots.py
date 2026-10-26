"""Archive each day's original screenshots to GitHub Releases (one release per month, one zip per day)
before retention.py compresses them. Days already archived are skipped; today's zip is replaced on
re-runs. Needs GH_TOKEN and GITHUB_REPOSITORY (set in the workflow)."""
import datetime as dt
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

SHOTS = Path(__file__).resolve().parent.parent / "site" / "shots"
REPO = os.environ.get("GITHUB_REPOSITORY", "")


def gh(*args, check=True):
    return subprocess.run(["gh", *args, "--repo", REPO], capture_output=True, text=True, check=check)


def main():
    if not SHOTS.is_dir() or not REPO:
        print("archive: skipped (no shots or repo)"); return
    today = dt.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    assets = {}
    for d in sorted(x for x in SHOTS.iterdir() if x.is_dir() and len(x.name) == 10):
        if (d / ".compressed").exists() or not any(d.rglob("*.jpg")):
            continue                                   # only originals are archived
        tag = "shots-" + d.name[:7]
        if tag not in assets:
            r = gh("release", "view", tag, "--json", "assets", check=False)
            if r.returncode != 0:
                gh("release", "create", tag, "--title", f"Screenshots {d.name[:7]} (originals)", "--latest=false",
                   "--notes", "Daily original screenshots (full pages + brand-mention crops), one zip per day. "
                              "The dashboard keeps compressed copies; these are the originals.")
                assets[tag] = set()
            else:
                assets[tag] = {a["name"] for a in json.loads(r.stdout)["assets"]}
        name = f"shots-{d.name}.zip"
        if name in assets[tag] and d.name != today:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            z = shutil.make_archive(str(Path(tmp) / name[:-4]), "zip", root_dir=d)
            gh("release", "upload", tag, z, "--clobber")
        assets[tag].add(name)
        print(f"archive: {tag}/{name}")


if __name__ == "__main__":
    main()
