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
// Category fixes for cards whose text alone misleads the keyword rules: a card linking to the Samsung/Galaxy
// card page is a payment offer even when it sits on the monitor page with only "Earn $200 back" as text;
// carrier deals are Galaxy phone offers.
window.promoCat = p => { const u = (p && p.url) || '', t = (p && p.title) || '';
  if (/samsung-card|galaxy-card|\/credit-card/i.test(u)) return '결제·금융';
  if (/carrier deal|\bGalaxy\b/i.test(t) && p.category === '행사·프로그램') return '모바일';
  return p.category; };
// A card that only links to an anchor on its own page with no amount is a section heading
// (e.g. tab labels read together), not a promotion.
const isHeading = p => !p.discount && /#/.test(p.url || '') && (!p.page_url || (p.url || '').split('#')[0].replace(/\/$/, '') === p.page_url.replace(/\/$/, ''));
const normUrl = u => (u || '').split(/[?#]/)[0].replace(/\/$/, '').toLowerCase();
// Same promotion read on two pages: same key, or same destination link with the same amount.
window.promoMap = (list) => { const m = new Map(); list.forEach(([k, p]) => {
  if (!k || !isBenefit(p) || isHeading(p)) return;
  const q = { ...p, category: promoCat(p), discount: cleanDiscount(p) };
  let hit = findPromo(m.keys(), k);
  if (!hit && q.url) for (const [x, v] of m) if (normUrl(v.url) === normUrl(q.url) && (v.discount || '').toLowerCase().replace(/[^0-9$%]/g, '') === (q.discount || '').toLowerCase().replace(/[^0-9$%]/g, '') && q.discount) { hit = x; break; }
  if (!hit) m.set(k, q);
  else if ((m.get(hit).title || '').length < (q.title || '').length) { m.delete(hit); m.set(k, q); }
}); return m; };
window.promoNotices = (list) => list.filter(([, p]) => !isBenefit(p)).length;

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

// "읽는 법" toggles: a short how-to-read note under each section heading (same wording as the reading guide).
(function () {
  const H = {
    'index|운영 개선 점검 포인트': '고객사 운영 개선안의 4개 방향(캐시백 상시 요율·리뷰 매체·딜 사이트·경쟁사 동향)별로, 오늘 수집 데이터에서 살펴볼 퍼블리셔·카테고리·지면을 자동으로 뽑았습니다. ‘점검’은 현황 확인, ‘강화’는 노출을 늘릴 대상입니다. 공개 화면 관측이며 효과는 CJ 실적으로 확인합니다.',
    'index|오늘의 요약': '그날 변화만 한 줄씩 모았습니다. ‘직전 대비 변동’ ‘신규’ ‘내려감’이 없으면 어제와 같은 상태입니다.',
    'index|캐시백 요율 · LG vs 삼성': '퍼블리셔의 LG·삼성 페이지에 보이는 대표 요율입니다. 초록 ‘평시 N%’는 지금 이벤트로 올려 둔 상태라는 뜻이고, 숫자 아래 작은 글씨는 카테고리별 요율(예: TV 1% · 그 외 2%)입니다.',
    'index|삼성 어필리에이트 잔존도': '‘캐시백 제공 퍼블리셔 11곳 / 확인 11곳’은 살펴본 11곳 모두에 삼성 요율이 보였다는 뜻입니다. 공개 화면 관측이라 계약·지출 규모는 알 수 없고, ‘범위 변경’ 날은 수집 대상이 늘어 전날과 직접 비교하지 않습니다.',
    'index|자사몰 프로모션': '파란 ‘신규’ = 어제 없던 프로모션, 주황 ‘N/N 종료 · D-n’ = 화면에 적힌 종료일까지 남은 날, 회색 ‘내려감’ = 페이지에서 사라짐(종료 확정 아님)입니다.',
    'index|그 외 경쟁사 · 수집 상태': '‘변동 없음’이 평상시입니다. ‘확인 필요’는 요율이 크게 바뀌었는데 근거가 하나뿐이라 게시를 미룬 것이고, 수집 실패는 대부분 봇 확인 화면이라 매일 비슷하게 나옵니다.',
    'index|지난 브리핑': '날짜를 누르면 그날 요약이 펼쳐집니다. 요약은 삭제되지 않고 계속 쌓입니다.',
    'weekly|이번 주 요약': '주간 보고에 그대로 옮겨 쓸 수 있는 문장입니다. 진행 중인 주는 수집일이 적어 출렁임이 크니 보고에는 7일을 다 채운 주를 쓰세요.',
    'weekly|캐시백 요율 격차 · LG vs 삼성': 'LG와 삼성 요율이 같은 날 모두 표시된 퍼블리셔만 모아 평균을 냅니다. ‘LG 우위 7 / 7일’은 그 주 매일, 비교한 모든 퍼블리셔에서 LG가 높았다는 뜻입니다.',
    'weekly|삼성 어필리에이트 잔존도': '언급 비중 = 삼성 ÷ (삼성 + LG). 50%를 넘으면 딜·리뷰 지면에서 삼성 이름이 더 많이 나왔다는 뜻이며, 광고 집행이나 점유율은 아닙니다.',
    'weekly|LG.com 프로모션 × 캐시백 겹침': '분홍 칸 = 캐시백 상향 + LG.com 프로모션 연계, 초록 칸 = 캐시백만 상향, 흰 칸 = 상향 없음, 회색 = 수집 없음입니다.',
    'weekly|카테고리별 추천 목록 순위': '리뷰 매체 ‘Best …’ 목록의 제품 순서입니다. ‘없음’은 그 목록에 해당 브랜드 제품이 없다는 뜻이며, 매체 편집 기준이라 판매량·광고와는 무관합니다.',
    'weekly|지난 주간 다이제스트': '주를 누르면 그 주 요약이 펼쳐지고, ‘이 주 전체 보기’로 그 주 화면을 엽니다.',
    'monitor|변화 감지': '직전 수집일 대비 요율이 바뀐 곳에만 색이 칠해집니다. ‘화면’ 링크로 그날 캡처를 바로 열 수 있습니다.',
    'monitor|퍼블리셔별 요율 비교': '빨간 막대 LG, 회색 가전 경쟁사, 노란 유통사(Best Buy 등)입니다. 유통사는 LG 제품도 파는 곳이라 참고로만 봅니다.',
    'monitor|요율 조건·제외 문구': '같은 요율이라도 카테고리·제외 조건에 따라 실제 적용이 다릅니다. 화면 문구를 그대로 옮겼고 실제 구매 적용은 확인하지 않았습니다.',
    'monitor|브랜드 노출 매트릭스': '숫자를 누르면 그 언급이 나온 딜 카드·리뷰 문단 캡처가 열립니다. 빈칸 = 언급 없음.',
    'monitor|오늘 수집 검증': '‘수집’이 정상입니다. ‘요율 확인 필요’는 읽었지만 보류한 것, ‘봇 확인 화면’·‘차단(HTTP)’은 우회하지 않은 실패입니다. 다른 화면에서 빈칸이 보이면 여기서 사유를 확인하세요.',
    'monitor|요율 추이': '경쟁사가 요율을 올린 날은 붉은 점으로 표시됩니다.',
    'monitor|지면 스크린샷': '최근 7일은 원본, 이후 약 4개월은 압축본입니다. 원본은 월별 보관함에서 내려받습니다.',
    'monitor|퍼블리셔 범위 (미국 기준)': '‘회원 전용’이나 ‘공개 브랜드 페이지 없음’은 공개 화면으로 확인할 수 없는 곳입니다.',
    'lgcom|오늘 LG.com 프로모션': 'NEW = 어제 없던 것, 노란 글씨 = 3일 안에 끝나는 것. 유효기간이 없는 상시 배너는 빠질 수 있어 화면도 함께 보세요.',
    'lgcom|같은 날 LG 캐시백·리워드': '✓ = 그 카테고리가 퍼블리셔 제외 문구에 없음, ⚠ = 제외 문구에 있음(할인은 받아도 캐시백은 안 붙을 수 있음).',
    'lgcom|일자별 타임라인': '캐시백 상향이 프로모션 기간과 같은 줄에 있으면 할인 + 캐시백 연계 운영입니다.',
    'samsung|카테고리별 LG.com vs Samsung.com': '카테고리는 제목 단어로 자동 분류한 값이라 대략적입니다.',
    'samsung|오늘 Samsung.com 프로모션': '가전·TV·모니터가 먼저, 모바일·결제 혜택은 뒤에 나옵니다. 위 버튼으로 카테고리를 걸러 봅니다.',
    'samsung|같은 날 퍼블리셔 캐시백: 삼성 vs LG': '삼성이 프로모션 기간에 캐시백도 올리는지 확인하는 칸입니다.',
    'samsung|일자별 타임라인': '‘내려감’은 페이지에서 사라졌다는 뜻이지 행사 종료 확정이 아닙니다.',
    'samsung|오늘 화면': '이미지 배너 안의 문구는 글자로 읽히지 않을 수 있어 화면으로 확인합니다.',
  };
  function run() {
    const page = (location.pathname.split('/').pop() || 'index.html').replace('.html', '') || 'index';
    const css = document.createElement('style');
    css.textContent = '.howto{font:inherit;font-size:11.5px;font-weight:500;color:var(--muted);background:none;border:1px solid var(--line);border-radius:999px;padding:0 8px;margin-left:8px;cursor:pointer;vertical-align:2px;line-height:18px}.howto:hover,.howto.on{color:var(--fg);border-color:var(--fg)}.howto-note{display:none;margin:6px 0 10px;padding:8px 12px;background:var(--note);border:1px solid var(--line);border-left:3px solid var(--fg);border-radius:6px;font-size:12.5px;line-height:1.6;color:var(--fg)}.howto-note.on{display:block}';
    document.head.append(css);
    document.querySelectorAll('h2').forEach(h => {
      const key = page + '|' + (h.textContent || '').trim();
      const t = H[key]; if (!t) return;
      const b = document.createElement('button'); b.type = 'button'; b.className = 'howto'; b.textContent = '읽는 법';
      const n = document.createElement('div'); n.className = 'howto-note'; n.textContent = t;
      b.onclick = () => { const on = !n.classList.contains('on'); n.classList.toggle('on', on); b.classList.toggle('on', on); };
      h.append(b);
      const anchor = h.closest('.hd') || h;
      anchor.after(n);
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run); else run();
})();

// Text size control (보통 / 크게 / 아주 크게). Pages use fixed px sizes, so the whole page is scaled with CSS zoom;
// '보통' is already a little larger than the original design. The choice is kept per viewer in this browser.
(function () {
  const LV = [['보통', 1.12], ['크게', 1.25], ['아주 크게', 1.4]];
  let cur = 0;
  try { const v = Number(localStorage.getItem('fontLevel')); if (v >= 0 && v < LV.length) cur = v; } catch (e) {}
  // On narrow screens the zoom is capped so the page keeps at least ~360px of layout width.
  const apply = () => { const w = window.innerWidth || 1200; document.documentElement.style.zoom = Math.max(1, Math.min(LV[cur][1], w / 360)); };
  window.addEventListener('resize', apply);
  apply();
  const css = document.createElement('style');
  css.textContent = '.appbar-in{gap:18px}.fsz{margin-left:auto;display:flex;align-items:center;gap:6px;font-size:12.5px;color:var(--muted);white-space:nowrap}.fsz button{font:inherit;font-size:12.5px;font-weight:600;color:var(--fg);background:#fff;border:1px solid var(--line);border-radius:6px;padding:2px 8px;cursor:pointer}.fsz button.on{background:var(--fg);color:#fff;border-color:var(--fg)}@media(max-width:1560px){.brand small{display:none}.fsz .lbl{display:none}}@media(max-width:700px){.fsz{margin-left:0}.fsz .lbl{display:inline}}';
  const run = () => {
    document.head.append(css);
    const host = document.querySelector('.appbar-in'); if (!host) return;
    const box = document.createElement('div'); box.className = 'fsz'; box.setAttribute('role', 'group'); box.setAttribute('aria-label', '글자 크기');
    const lb = document.createElement('span'); lb.className = 'lbl'; lb.textContent = '글자 크기'; box.append(lb); box.title = '글자 크기';
    LV.forEach(([t], i) => { const b = document.createElement('button'); b.type = 'button'; b.textContent = t; if (i === cur) b.className = 'on';
      b.onclick = () => { cur = i; try { localStorage.setItem('fontLevel', i); } catch (e) {} apply(); [...box.querySelectorAll('button')].forEach((x, j) => x.classList.toggle('on', j === i)); };
      box.append(b); });
    host.append(box);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', run); else run();
})();
