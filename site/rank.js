// Publisher order used on every page: CJ sales rank (rank only, no amounts). LG.com always first.
window.loadRank = async function () {
  let order = [];
  try { const r = await fetch('data/publisher_rank.json?v=' + Date.now()); if (r.ok) order = (await r.json()).order || []; } catch (e) {}
  const res = order.map(o => [new RegExp(o.match, 'i'), o.rank]);
  const rankOf = name => { if (/^LG\.com$/i.test(name || '')) return 0; for (const [re, k] of res) if (re.test(name || '')) return k; return 999; };
  const byRank = (a, b) => rankOf(a) - rankOf(b) || String(a).localeCompare(String(b));
  return { rankOf, byRank, order };
};

// Promotion identity. Samsung.com cards are read sometimes as the headline only ("Save up to $900 on ranges")
// and sometimes as eyebrow + headline + body ("Save up to $900 on ranges enjoy installation on us ..."),
// which used to show up as 9~10 'new' and 'ended' promotions a day. Two titles are the same promotion when
// the shorter normalized title (20+ chars) sits inside the longer one.
window.promoKey = t => String(t || '').toLowerCase().replace(/[®™*]/g, '').replace(/[^a-z0-9$%]+/g, ' ').trim().slice(0, 160);
window.samePromo = (a, b) => a === b || (Math.min(a.length, b.length) >= 20 && (a.length <= b.length ? b.includes(a) : a.includes(b)));
window.findPromo = (keys, k) => { for (const x of keys) if (samePromo(x, k)) return x; return null; };
// Only cards that offer something count as promotions. Notices such as "99% coverage in the U.S. ...
// product support" or "Enjoy a 2-year limited warranty" were being counted, and the "99%" read as a discount.
const BENEFIT = /\$\s?\d|\d+(?:\.\d+)?\s?%\s*(?:off|back|cash|savings?|rewards?)|\b(?:save|savings|off|free|credit|gift|on us|bonus|rebate|rewards?|cash ?back|financ\w*|apr|trade[- ]?in|bogo|bundle|discount|deals?|price guarantee\w*|sale|event|week)\b|buy\b.*\bget\b/i;
window.isBenefit = p => BENEFIT.test(((p && p.title) || '') + ' ' + ((p && p.discount) || ''));
// A bare "99%" with no off/back/rewards next to it in the card is not a discount.
window.cleanDiscount = p => { const d = p && p.discount; if (!d) return d; if (/^\s*\d+(?:\.\d+)?\s?%\s*$/.test(d) && !new RegExp(d.trim().replace('%', '\\s?%') + '\\s*(?:off|back|cash|savings?|rewards?)', 'i').test(p.title || '')) return null; return d; };
// Map of key -> promo for one day, merging cards that are the same promotion and dropping non-offers.
window.promoMap = (list) => { const m = new Map(); list.forEach(([k, p]) => { if (k && isBenefit(p) && !findPromo(m.keys(), k)) m.set(k, { ...p, discount: cleanDiscount(p) }); }); return m; };
window.promoNotices = (list) => list.filter(([, p]) => !isBenefit(p)).length;

// Placement evidence. Seeing LG on a page proves the slot ran only if LG is NOT there on ordinary days.
//  - rate:   LG store rate raised in the window                 -> '요율 상향' (counts as observed)
//  - window: LG on the page in the window, mostly absent outside -> '기간 한정 노출' (counts as observed)
//  - brand:  LG on the page in the window but also on most days outside it, or no outside days to compare
//            -> '브랜드 존재만' (does not prove the slot; not counted as observed)
window.placementJudge = function (at, dates) {
  const OK = s => s === '수집' || s === '수집(텍스트)';
  const BASE = { 'capone-lg': 2.5 };   // usual public reward rate when no event runs
  const elevated = r => r && OK(r.status) && r.rate != null && (/was\s/i.test(r.rate_text || '') || (BASE[r.target] != null && r.rate > BASE[r.target]));
  const lgSeen = r => r && OK(r.status) && ((r.lg_snippets && r.lg_snippets.length) || (r.mentions && r.mentions.LG));
  const row = (d, t) => at[d] && at[d][t];
  const outside = p => { const out = dates.filter(d => d < p.start || d > (p.end || p.start)); const seen = out.filter(d => p.targets.some(t => lgSeen(row(d, t)))); return { n: out.length, seen: seen.length }; };
  const judgeDay = (p, d) => {
    const rows = p.targets.map(t => row(d, t)).filter(Boolean);
    if (!rows.length) return { s: 'none' };
    const hit = rows.find(p.method === 'rate' ? elevated : lgSeen);
    if (hit) return { s: 'hit', row: hit };
    if (rows.some(r => OK(r.status) || r.status === '요율 미확인' || r.status === '요율 확인 필요')) return { s: 'miss', row: rows[0] };
    return { s: 'fail', row: rows[0] };
  };
  // judge over the given days (a single day, a week, or the whole window)
  const judge = (p, days) => {
    if (!['rate', 'presence', 'partial'].includes(p.method) || !p.start) return { s: 'none', of: 0 };
    const win = days.filter(d => d >= p.start && d <= (p.end || p.start));
    const per = win.map(d => ({ d, ...judgeDay(p, d) }));
    const hits = per.filter(x => x.s === 'hit');
    const o = p.method === 'rate' ? null : outside(p);
    if (hits.length) {
      const brand = o && (o.n === 0 || o.seen / o.n >= 0.5);
      return { s: brand ? 'brand' : 'hit', level: p.method === 'rate' ? '요율 상향' : brand ? '브랜드 존재만' : '기간 한정 노출', hits, per, of: win.length, outside: o };
    }
    if (per.some(x => x.s === 'miss')) return { s: 'miss', per, of: win.length, outside: o };
    if (per.some(x => x.s === 'fail')) return { s: 'fail', per, of: win.length, outside: o };
    return { s: 'none', per, of: win.length, outside: o };
  };
  return { judge, judgeDay, elevated, lgSeen, outside };
};

// Shorten text at a word boundary (no half words in the briefing).
window.cutWords = (s, n) => { s = String(s || '').replace(/\s+/g, ' ').trim(); if (s.length <= n) return s; const c = s.slice(0, n); const i = c.lastIndexOf(' '); return (i > n * 0.5 ? c.slice(0, i) : c).replace(/[\s,.;:—–-]+$/, '') + '…'; };

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
