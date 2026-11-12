# [시황분석] 주식·코인 시황 대시보드

주식과 암호화폐에 영향을 줄 수 있는 뉴스, 주요 지수 차트, 고점 대비 하락 종목, 관심 종목을 한 화면에서 보는 페이지입니다.
주소: https://resistance-kor.github.io/market-brief/

## 화면

- **시황**: 오늘의 시황 요약·주요 일정(실적 발표 예정일 자동 포함), 지수 차트(코스피·나스닥·S&P500·비트코인·이더리움·솔라나·미국 10년물·원/달러·달러인덱스·VIX·금·WTI), 코인 지표(공포·탐욕 지수, 펀딩비, 비트코인 현물 ETF 순유입)
- **뉴스**: 실시간 헤드라인(RSS), 주식/코인/거시 뉴스 분석
- **고점 대비 하락 종목**: 52주 고점 대비 -30% 이하 — 미국(S&P500+나스닥100 전 종목), 국내(코스피200 전 종목). PER·PBR·배당·부채비율, 조건 필터, 신규/이탈 표시. 의류·명품 업종 제외
- **기타 종목**: 관심 종목 카드(1년 흐름, PER·PBR·배당)

## 데이터와 갱신

| 파일 | 내용 | 만드는 곳 | 갱신 |
|---|---|---|---|
| `prices.json` | 지수·코인·금리·환율·원자재 일별 종가 이력, 기타 종목 시세, 코인 지표 | `prices.yml` (Yahoo Finance, 네이버 증권, alternative.me, Bitget, Farside) | 매시 13분 |
| `headlines.json` | 언론사 RSS 헤드라인(제목·링크만) | `headlines.yml` | 20분마다 |
| `kr_drawdown.json` | 코스피200 하락 종목 | `kr_drawdown.yml` (네이버 증권·Yahoo Finance·다음 금융) | 평일 08:17·16:47 KST |
| `us_drawdown.json` | S&P500+나스닥100 하락 종목, 미국 기타 종목 재무, 실적 발표 예정일 | `us_drawdown.yml` (Yahoo Finance) | 화~토 07:27 KST |
| `data.json` | 시황 요약·뉴스 분석·일정·기타 종목 목록 | Claude 예약 작업 | 매일 07:19·22:19 KST |

- 비트코인·이더리움·솔라나는 Coinbase WebSocket, 미국 지수·금리·금은 TradingView 위젯으로 실시간 표시합니다.
- GitHub의 예약 실행은 몇 분~수십 분 늦어질 수 있습니다.
- 미국 종목 한국어 이름은 `scripts/us_names_ko.json`에 있으며, 없는 종목은 영문명으로 표시됩니다.
- 요약과 "영향 해석"은 수집 기사를 근거로 작성한 것이며 투자 권유가 아닙니다.

## 파일

- `index.html` — 화면 전체 (Chart.js)
- `scripts/` — 수집 스크립트 (`fetch_prices.py`, `fetch_headlines.py`, `fetch_kr_drawdown.py`, `fetch_us_drawdown.py`)
- `.github/workflows/` — 자동 수집 작업
- `.nojekyll` — GitHub Pages가 파일을 그대로 서비스하도록 하는 설정
