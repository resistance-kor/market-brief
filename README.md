# [시황분석] 주식·코인 시황 대시보드

주식과 암호화폐에 영향을 줄 수 있는 뉴스, 주요 지수 차트, 고점 대비 하락 종목, 관심 종목을 한 화면에서 보는 페이지입니다.
주소: https://resistance-kor.github.io/market-brief/

## 화면

- **시황**: 오늘의 시황 요약·주요 일정, 지수 차트(코스피·나스닥·S&P500·비트코인·이더리움·솔라나·미국 10년물·금, 사상 최고 대비)
- **뉴스**: 실시간 헤드라인(RSS), 주식/코인/거시 뉴스 분석
- **고점 대비 하락 종목**: 52주 고점 대비 -30% 이하 — 미국(S&P500·나스닥100), 국내(코스피200). PER 포함, 의류·명품 업종 제외
- **기타 종목**: 관심 종목 카드(TSLL, 인튜이티브 머신스, 유나이티드헬스, PLUS 고배당주)

## 데이터와 갱신

| 파일 | 내용 | 만드는 곳 | 갱신 |
|---|---|---|---|
| `prices.json` | 지수·코인·금리·금 일별 종가 전체 이력, 기타 종목 종가 | GitHub Actions `prices.yml` (Yahoo Finance, 실패 시 FRED·Coinbase) | 매시 13분 |
| `headlines.json` | 언론사 RSS 헤드라인(제목·링크만) | GitHub Actions `headlines.yml` | 20분마다 |
| `kr_drawdown.json` | 코스피200 고점 대비 하락 종목 | GitHub Actions `kr_drawdown.yml` (네이버 증권·Yahoo Finance·다음 금융) | 평일 08:17·16:47 KST |
| `data.json` | 시황 요약·뉴스 분석·일정·미국 하락 종목·기타 종목 PER | Claude 예약 작업 | 매일 07:19·22:19 KST |

- 비트코인·이더리움·솔라나는 페이지에서 Coinbase WebSocket으로 실시간 표시, 미국 지수·금리·금은 TradingView 위젯으로 실시간 표시합니다.
- GitHub의 예약 실행은 몇 분~수십 분 늦어질 수 있습니다.
- `prices.json`은 용량을 줄이려고 첫 날짜(`d0`) + 날짜 간격(`dd`) + 값(`v`) 형식으로 저장합니다(최근 3년 일별, 그 이전 주별).
- 요약과 "영향 해석"은 수집 기사를 근거로 작성한 것이며 투자 권유가 아닙니다.

## 파일

- `index.html` — 화면 전체 (Chart.js)
- `scripts/` — 수집 스크립트 (`fetch_prices.py`, `fetch_headlines.py`, `fetch_kr_drawdown.py`)
- `.github/workflows/` — 자동 수집 작업
- `.nojekyll` — GitHub Pages가 파일을 그대로 서비스하도록 하는 설정
