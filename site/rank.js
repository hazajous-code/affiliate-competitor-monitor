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
