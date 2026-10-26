# 어필리에이트 경쟁사 지면 모니터

미국 어필리에이트 퍼블리셔 공개 지면을 매일 캡처해 LG와 가전 경쟁사의
캐시백·리워드 요율, 카테고리별 조건·제외 문구, 쿠폰 오퍼, 딜·리뷰 지면의 브랜드 노출을 쌓는 저장소입니다.

- 캐시백·리워드: Rakuten, TopCashback, Capital One Shopping, BeFrugal, RebatesMe, ID.me Shop
- 쿠폰: RetailMeNot, Savings.com, Slickdeals, TechRadar, Tom's Guide
- 딜·리뷰(브랜드 노출): Slickdeals, DealNews, Brad's Deals, RTINGS, TechRadar, Tom's Guide, Forbes Vetted, WIRED, Good Housekeeping
- 회원 전용 혜택 플랫폼(공개 입구만): PerkSpot, BenefitHub, Next Jump, GOVX

- 대시보드: GitHub Pages (`site/`)
- 수집 시각: 매일 13:07 UTC (미국 동부 오전 9시 전후), GitHub Actions 서버에서 실행 — 개인 PC·Claude 세션과 무관
- 안정 장치: 같은 날 17:37·22:37 UTC 백업 실행(그날 전체 수집이 이미 있으면 건너뜀), 실패 대상 1회 재시도, 실행 때마다 스케줄 재활성화(GitHub의 60일 비활성 정지 방지), 대시보드에 30시간 넘게 수집이 없으면 경고 표시
- 공개 페이지만 수집합니다. 로그인이 필요한 회원 전용 혜택 플랫폼(Next Jump · Passport · BenefitHub 등)과
  내부 지출·매출 수치는 넣지 않습니다.

## 구성
| 경로 | 내용 |
|---|---|
| `targets.json` | 수집 대상(퍼블리셔 × 브랜드 × URL × 요율 읽는 방식) |
| `scripts/capture.py` | Playwright로 화면 캡처 + 요율 문구 추출 + 성공 여부 판정 |
| `site/data/captures.json` | 날짜 × 대상별 누적 원장 |
| `site/data/captures.csv` | 같은 원장의 내려받기용 CSV |
| `site/data/runs.json` | 최근 실행의 대상별 검증 결과 + 접속 국가 코드 |
| `site/data/briefs.json` | 일자별 ‘오늘의 요약’ 보관(삭제하지 않음). `scripts/archive_briefs.py`가 매일 수집 후 저장 |
| `scripts/verify.py` | 커밋 전 무결성·공개 안전성 점검(내부 성과 용어 차단) |
| `site/data/coverage.json` | 분석 이력의 전체 퍼블리셔와 자동 수집 가능 여부 |
| `site/shots/<날짜>/` | 스크린샷(JPEG). 최근 14일은 원본, 이후 720px·품질 30으로 압축해 200일 보관, 언급 캡처(`m/`)는 365일. 850MB를 넘으면 가장 오래된 압축본부터 삭제(`scripts/retention.py`). 저장소 이력이 커지지 않도록 `shots` 브랜치에 커밋 1개로 덮어써 보관 |
| GitHub Releases `shots-YYYY-MM` | 원본 스크린샷 영구 보관 — 월별 릴리스에 날짜별 zip(`scripts/archive_shots.py`, 압축 전에 업로드) |
| `plans/YYYY-MM.txt` | 월별 편성표 — 매칭용 필드만(퍼블리셔·기간·지면명·OBS/PS·카테고리·오퍼 문구). 비용·성과 열은 넣지 않음 |
| `scripts/import_plan.py` | 편성표 → `site/data/placements.json` 변환 + 지면별 확인 방식 분류 |
| `site/index.html` | 데일리 브리핑(첫 화면) — 요율·자사몰 프로모션·편성 요약, 각 탭으로 연결 |
| `site/monitor.html` | 경쟁사 지면 모니터(요율·조건·노출·검증·스크린샷) |
| `site/placements.html` | 편성 지면 관측 메뉴 |
| `site/lgcom.html` | LG.com/us 프로모션 × 퍼블리셔 LG 캐시백 비교 메뉴 |
| `site/samsung.html` | Samsung.com/us 오퍼 페이지 프로모션 × LG.com 카테고리 비교 × 퍼블리셔 삼성/LG 요율 |
| `site/data/publisher_rank.json` | 퍼블리셔 정렬 순서(판매 실적 순위만, 금액 없음) |

## 대상 추가·수정
`targets.json`에 한 줄을 넣고 Actions › daily-capture › Run workflow로 바로 실행하면 됩니다.
특정 대상만 다시 찍으려면 실행 시 target id를 입력합니다.

## 수집 원칙
- 자동화 브라우저임을 숨기지 않는 일반 헤드리스 Chromium으로 엽니다. 봇 확인 화면·차단은 그대로 실패로 기록하고 우회하지 않습니다(2026-10-26부터 브라우저 위장 설정 제거 — 이로 인해 RetailMeNot 전 페이지가 Cloudflare 확인 화면으로 수집 불가).
- 브랜드 노출 매트릭스: 딜·리뷰 페이지에서 브랜드가 언급된 카드·문단을 브랜드당 최대 2장 잘라 `shots/<날짜>/m/`에 저장(브랜드명 노란 표시, 365일 보관). 매트릭스 숫자를 누르면 표시.
- Cartera(항공 쇼핑몰 5곳)는 $1당 마일·포인트로, % 캐시백과 단위가 달라 따로 표시합니다.

## 판정 기준
- **수집**: 화면 저장 + 요율 문구 읽음
- **요율 확인 필요**: 요율은 읽었지만 게시를 보류함. 아래 규칙 2·3에 걸린 경우(`held_rate`에 읽은 값 보관)
- **요율 미확인**: 화면은 저장됐지만 요율 문구를 찾지 못함(페이지 구조 변경 가능)
- **페이지 없음**: 주소가 바뀌었거나 상점이 없음
- **로그인 입구만**: 회원 전용 플랫폼의 공개 입구까지만 확인
- **봇 확인 화면 / 렌더링 실패 / 차단(HTTP) / 접속 실패**: 우회하지 않고 실패로 기록

### 요율 오인식 방지 규칙 (2026-10-20 도입)
10/19 라쿠텐 Flash Cash 때 상단 메뉴의 "10% Cash Back"을 모든 상점 요율로 잘못 읽은 일이 있어 도입했습니다.
1. **정해진 자리에서만 읽기**: Rakuten은 Shop Now 버튼 위, TopCashback은 제목 아래 "Get N% of the price back", Capital One은 Activate 버튼 상자, BeFrugal은 제목부의 "Activate N% Cash Back at …"에서만 대표 요율을 읽음(`rate_source=header`). 자리를 못 찾을 때만 본문 검색으로 대체(`rate_source=text`).
2. **두 군데 맞춰 보기**: 대표 요율이 같은 화면 카테고리별 요율의 최고값보다 높으면 보류(ID.me는 카테고리가 할인율이라 제외).
3. **급변 보류**: 직전 게시 값에서 2%p 이상 또는 2배/절반 이상 바뀌었는데 두 번째 근거가 없으면 보류. 근거 = "was N%"·Improved 같은 상향 표시, 카테고리 요율 일치, 또는 다음 수집일에 같은 값(이틀 연속).
- 쿠폰·딜 사이트(Savings.com·RetailMeNot·TechRadar 등)는 요율을 기록하지 않음. 페이지에 올라온 "Get 20% Cash Back with MyLG Rewards"(웰컴 쿠폰 WELCOME20) 같은 문구는 남의 오퍼이지 그 사이트의 캐시백 요율이 아니기 때문(2026-10-21 피드백 반영). 오퍼 수·최상단 딜만 기록.
- 추가로, 한 날짜에 라쿠텐 상점 6곳 이상이 모두 같은 요율이면 `verify.py`가 게시 자체를 막음.

- **변화 감지**: 읽어 낸 값(요율·카테고리·제외 문구·오퍼)의 지문을 직전 수집일과 비교
