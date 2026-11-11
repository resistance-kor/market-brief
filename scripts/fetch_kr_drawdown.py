"""코스피200 편입 종목 중 52주 고점 대비 -30% 이하 종목 → kr_drawdown.json
1) 구성 종목: 네이버 증권 모바일 API
2) 시세(최근 약 1년 일봉): Yahoo Finance(<코드>.KS) — 정규장 종가·장중 고가(NXT 시간외 가격 제외)
   - 52주 고점 = 최근 365일 일별 '고가' 중 최댓값(장중 고가 기준), 종가는 마지막 일봉 종가
3) 걸러진 종목만 네이버 증권(PER·추정PER·시가총액)과 다음 금융(WICS 업종)
4) 의류·신발·패션·명품 업종 제외
"""
import json, re, sys, time, urllib.request
from datetime import datetime, timezone, timedelta

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
THRESHOLD = -30.0
EXCLUDE_SECTOR = re.compile(r"섬유|의류|의복|신발|호화품|패션|럭셔리")


def get(url, timeout=25, headers=None):
    h = {"User-Agent": UA, "Accept": "*/*"}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


UNIVERSE_LABEL = "코스피200 편입 종목"


def constituents():
    """코스피200 구성종목: 네이버 증권 모바일 API (index/KPI200/enrollStocks)."""
    found = {}
    for page in range(1, 16):
        items = json.loads(get(f"https://m.stock.naver.com/api/index/KPI200/enrollStocks?page={page}&pageSize=20"))
        if isinstance(items, dict):
            items = items.get("stocks") or []
        before = len(found)
        for it in items:
            code, name = it.get("itemCode"), it.get("stockName")
            if code and name and re.fullmatch(r"\d{6}", code):
                found.setdefault(code, name)
        if len(found) == before or len(items) < 20:
            break
        time.sleep(0.3)
    return found


def yahoo_daily(code):
    p2 = int(time.time()) + 86400
    p1 = p2 - 400 * 86400
    last = None
    for host in ("query1", "query2"):
        try:
            raw = get(f"https://{host}.finance.yahoo.com/v8/finance/chart/{code}.KS?period1={p1}&period2={p2}&interval=1d&includePrePost=false&events=")
            res = json.loads(raw)["chart"]["result"][0]
            off = res["meta"].get("gmtoffset", 0)
            q = res["indicators"]["quote"][0]
            rows = {}
            for t, h, c in zip(res["timestamp"], q["high"], q["close"]):
                if c is None or c <= 0:
                    continue
                d = datetime.fromtimestamp(t + off, tz=timezone.utc).strftime("%Y-%m-%d")
                rows[d] = (float(h) if h else float(c), float(c))
            out = sorted(rows.items())
            if len(out) >= 60:
                return out, res["meta"].get("longName") or res["meta"].get("shortName"), "Yahoo Finance"
            last = f"too short {len(out)}"
        except Exception as e:
            last = f"{type(e).__name__} {e}"
        time.sleep(1)
    raise RuntimeError(last)


def naver_detail(code):
    """PER(최근 실적)·추정PER·시가총액: 네이버 증권 모바일 integration / 업종: 다음 금융(WICS)."""
    d = json.loads(get(f"https://m.stock.naver.com/api/stock/{code}/integration"))
    info = {x.get("code"): x.get("value") for x in d.get("totalInfos", [])}
    def pnum(v):
        if not v:
            return None
        m = re.search(r"-?[\d,]+(?:\.\d+)?", v)
        return float(m.group(0).replace(",", "")) if m else None
    per, fper = pnum(info.get("per")), pnum(info.get("cnsPer"))
    if per is None:  # 적자면 PER이 N/A → EPS 음수면 적자 표시
        eps = pnum(info.get("eps"))
        if eps is not None and eps < 0:
            per = -1.0
    mcap = info.get("marketValue")
    sector = None
    try:
        dd = json.loads(get(f"https://finance.daum.net/api/quotes/A{code}?summary=false",
                            headers={"Referer": f"https://finance.daum.net/quotes/A{code}"}))
        sector = dd.get("wicsSectorName") or dd.get("sectorName")
    except Exception as e:
        print(f"  {code} 업종(다음) 실패: {e}")
    return {"per": per, "fper": fper, "sector": sector, "mcap": (mcap + "원") if mcap else None}


def main(path):
    try:
        prev = json.load(open(path, encoding="utf-8"))
    except Exception:
        prev = None
    log = []
    try:
        cons = constituents()
    except Exception as e:
        cons = {}
        log.append(f"구성종목 수집 실패: {type(e).__name__} {e}")
        print(log[-1])
    print(f"코스피200 구성종목 {len(cons)}개")
    if len(cons) < 190:
        print("구성종목이 너무 적음 — 이전 파일 유지")
        if prev:
            sys.exit(0)
        sys.exit(1)

    hits, fails, asofs = [], [], []
    for i, (code, name) in enumerate(cons.items(), 1):
        try:
            rows, en, _ = yahoo_daily(code)
            d_last, (_, px) = rows[-1]
            prev_close = rows[-2][1][1]
            cut = (datetime.strptime(d_last, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d")
            hi = max(h for d, (h, c) in rows if d > cut)
            fh = (px / hi - 1) * 100
            asofs.append(d_last)
            if fh <= THRESHOLD:
                hits.append({"ticker": code, "name_ko": name, "name": en or "", "index": ["코스피200"],
                             "asof": d_last, "price": round(px), "chg1d": round((px / prev_close - 1) * 100, 2),
                             "high52": round(hi), "from_high": round(fh, 2)})
        except Exception as e:
            fails.append(f"{code} {name}: {e}")
        time.sleep(0.25)
        if i % 50 == 0:
            print(f"  {i}/{len(cons)} 처리, 해당 {len(hits)}개")

    excluded = []
    out_rows = []
    for r in hits:
        try:
            det = naver_detail(r["ticker"])
        except Exception as e:
            det = {"per": None, "fper": None, "sector": None, "mcap": None}
            log.append(f"{r['ticker']} 상세 실패: {e}")
        r.update(det)
        if r["sector"] and EXCLUDE_SECTOR.search(r["sector"]):
            excluded.append(f"{r['name_ko']}({r['sector']})")
            continue
        out_rows.append(r)
        time.sleep(0.3)
    out_rows.sort(key=lambda r: r["from_high"])

    latest = max(asofs) if asofs else None
    out = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "asof": latest,
        "basis": "52주 고점(최근 1년 일별 장중 고가 중 최댓값)",
        "threshold": THRESHOLD,
        "universe": f"{UNIVERSE_LABEL} {len(cons)}개 (구성: 네이버 증권)",
        "source": "구성종목·PER·추정PER·시가총액: 네이버 증권 · 시세(정규장 종가·장중 고가): Yahoo Finance · 업종(WICS): 다음 금융",
        "source_url": "https://m.stock.naver.com/domestic/index/KPI200/total",
        "excluded_note": ("의류·신발·패션·명품 업종 제외: " + ", ".join(excluded)) if excluded else "의류·신발·패션·명품 업종 제외(이번 해당 없음)",
        "coverage_note": f"대상 {len(cons)}개 전 종목을 계산했습니다." + (f" 시세를 받지 못한 종목 {len(fails)}개는 빠져 있습니다." if fails else ""),
        "failed": fails[:30],
        "log": log[:30],
        "rows": out_rows,
    }
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"기준일 {latest} · -30% 이하 {len(hits)}개(제외 {len(excluded)}) → {len(out_rows)}개 저장 · 실패 {len(fails)}")
    for r in out_rows[:60]:
        print(f"  {r['ticker']} {r['name_ko']} {r['sector']} {r['price']} 고점 {r['high52']} {r['from_high']}% PER {r['per']}/{r['fper']} {r['mcap']}")
    for f in fails[:10]:
        print("  실패", f)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "kr_drawdown.json")
