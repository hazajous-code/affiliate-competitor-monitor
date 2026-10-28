// Publisher order used on every page: CJ sales rank (rank only, no amounts). LG.com always first.
window.loadRank = async function () {
  let order = [];
  try { const r = await fetch('data/publisher_rank.json?v=' + Date.now()); if (r.ok) order = (await r.json()).order || []; } catch (e) {}
  const res = order.map(o => [new RegExp(o.match, 'i'), o.rank]);
  const rankOf = name => { if (/^LG\.com$/i.test(name || '')) return 0; for (const [re, k] of res) if (re.test(name || '')) return k; return 999; };
  const byRank = (a, b) => rankOf(a) - rankOf(b) || String(a).localeCompare(String(b));
  return { rankOf, byRank, order };
};

// Dates that hold a complete collection. A one-page re-run creates a date with only a few rows;
// such a date is left out until the full run fills it, so every tab compares like with like.
window.reportDates = function (caps) {
  const cnt = {};
  caps.forEach(r => { cnt[r.date] = (cnt[r.date] || 0) + 1; });
  const max = Math.max(0, ...Object.values(cnt));
  return Object.keys(cnt).filter(d => cnt[d] >= max * 0.6).sort();
};


// Fetch JSON with retries (a request can fail for a moment while the site is being redeployed).
window.loadJSON = async function (p, tries = 3) {
  for (let i = 0; i < tries; i++) {
    try { const r = await fetch(p + '?v=' + Date.now(), { cache: 'no-store' }); if (r.ok) return await r.json(); } catch (e) {}
    await new Promise(res => setTimeout(res, 1500 * (i + 1)));
  }
  return null;
};

// Dates a visitor sees: complete collections up to the published day (runs.complete_day).
// While a new day is still being collected, the previous complete day stays on screen.
window.publishedDates = function (caps, runs) {
  const all = reportDates(caps);
  const cut = runs && runs.complete_day;
  return cut ? all.filter(d => d <= cut) : all;
};

// Small status line at the top while data loads, and a clear message if it cannot be loaded.
(function () {
  const bar = document.createElement('div');
  bar.id = 'loadbar';
  bar.textContent = '최신 데이터를 불러오는 중…';
  bar.style.cssText = 'position:fixed;left:50%;transform:translateX(-50%);top:64px;z-index:30;background:#111827;color:#fff;font-size:12.5px;padding:6px 14px;border-radius:999px;box-shadow:0 2px 8px rgba(0,0,0,.15)';
  const add = () => document.body && document.body.append(bar);
  if (document.body) add(); else document.addEventListener('DOMContentLoaded', add);
  window.loadDone = function (ok) {
    if (ok) { bar.remove(); return; }
    bar.style.background = '#b91c1c';
    bar.textContent = '데이터를 불러오지 못했습니다. 사이트 업데이트 중일 수 있으니 잠시 후 새로고침해 주세요.';
  };
})();
