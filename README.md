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
| `scripts/verify.py` | 커밋 전 무결성·공개 안전성 점검(내부 성과 용어 차단) |
| `site/data/coverage.json` | 분석 이력의 전체 퍼블리셔와 자동 수집 가능 여부 |
| `site/shots/<날짜>/` | 스크린샷(JPEG, 최근 60일). 저장소 이력이 커지지 않도록 `shots` 브랜치에 커밋 1개로 덮어써 보관 |
| `plans/YYYY-MM.txt` | 월별 편성표 — 매칭용 필드만(퍼블리셔·기간·지면명·OBS/PS·카테고리·오퍼 문구). 비용·성과 열은 넣지 않음 |
| `scripts/import_plan.py` | 편성표 → `site/data/placements.json` 변환 + 지면별 확인 방식 분류 |
| `site/placements.html` | 편성 지면 관측 메뉴 |
| `site/lgcom.html` | LG.com/us 프로모션 × 퍼블리셔 LG 캐시백 비교 메뉴 |
| `site/data/publisher_rank.json` | 퍼블리셔 정렬 순서(판매 실적 순위만, 금액 없음) |

## 대상 추가·수정
`targets.json`에 한 줄을 넣고 Actions › daily-capture › Run workflow로 바로 실행하면 됩니다.
특정 대상만 다시 찍으려면 실행 시 target id를 입력합니다.

## 판정 기준
- **수집**: 화면 저장 + 요율 문구 읽음
- **요율 미확인**: 화면은 저장됐지만 요율 문구를 찾지 못함(페이지 구조 변경 가능)
- **페이지 없음**: 주소가 바뀌었거나 상점이 없음
- **로그인 입구만**: 회원 전용 플랫폼의 공개 입구까지만 확인
- **봇 확인 화면 / 렌더링 실패 / 차단(HTTP) / 접속 실패**: 우회하지 않고 실패로 기록
- **변화 감지**: 읽어 낸 값(요율·카테고리·제외 문구·오퍼)의 지문을 직전 수집일과 비교
