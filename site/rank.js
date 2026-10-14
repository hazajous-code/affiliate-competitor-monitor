// Publisher order used on every page: CJ sales rank (rank only, no amounts). LG.com always first.
window.loadRank = async function () {
  let order = [];
  try { const r = await fetch('data/publisher_rank.json?v=' + Date.now()); if (r.ok) order = (await r.json()).order || []; } catch (e) {}
  const res = order.map(o => [new RegExp(o.match, 'i'), o.rank]);
  const rankOf = name => { if (/^LG\.com$/i.test(name || '')) return 0; for (const [re, k] of res) if (re.test(name || '')) return k; return 999; };
  const byRank = (a, b) => rankOf(a) - rankOf(b) || String(a).localeCompare(String(b));
  return { rankOf, byRank, order };
};
