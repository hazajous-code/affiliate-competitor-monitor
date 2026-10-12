# 어필리에이트 경쟁사 지면 모니터

미국 어필리에이트 퍼블리셔(Rakuten · TopCashback · Capital One Shopping · RetailMeNot · Cartera 항공 포털)의
상점 페이지를 매일 캡처해 LG와 가전 경쟁사(Samsung · Sony · Whirlpool · GE Appliances · Frigidaire · Dyson)의
캐시백·리워드 요율과 화면을 쌓는 저장소입니다.

- 대시보드: GitHub Pages (`site/`)
- 수집 시각: 매일 13:07 UTC (미국 동부 오전 9시 전후), GitHub Actions의 미국 리전 러너에서 실행
- 공개 페이지만 수집합니다. 로그인이 필요한 회원 전용 혜택 플랫폼(Next Jump · Passport · BenefitHub 등)과
  내부 지출·매출 수치는 넣지 않습니다.

## 구성
| 경로 | 내용 |
|---|---|
| `targets.json` | 수집 대상(퍼블리셔 × 브랜드 × URL × 요율 읽는 방식) |
| `scripts/capture.py` | Playwright로 화면 캡처 + 요율 문구 추출 + 성공 여부 판정 |
| `site/data/captures.json` | 날짜 × 대상별 누적 원장 |
| `site/data/runs.json` | 최근 실행의 대상별 검증 결과 |
| `site/data/coverage.json` | 분석 이력의 전체 퍼블리셔와 자동 수집 가능 여부 |
| `site/shots/<날짜>/` | 스크린샷(JPEG, 최근 90일 보관) |

## 대상 추가·수정
`targets.json`에 한 줄을 넣고 Actions › daily-capture › Run workflow로 바로 실행하면 됩니다.
특정 대상만 다시 찍으려면 실행 시 target id를 입력합니다.

## 판정 기준
- **수집**: 화면 저장 + 요율 문구 읽음
- **요율 미확인**: 화면은 저장됐지만 요율 문구를 찾지 못함(페이지 구조 변경 가능)
- **페이지 없음**: 주소가 바뀌었거나 상점이 없음
- **차단 / 접속 실패**: 봇 확인 화면 또는 시간 초과
