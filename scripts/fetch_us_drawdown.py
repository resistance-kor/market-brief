"""S&P500 + 나스닥100 전 종목 중 52주 고점 대비 -30% 이하 종목 → us_drawdown.json
1) 구성 종목: S&P500 = github.com/datasets/s-and-p-500-companies, 나스닥100 = nasdaq.com API
2) 시세(최근 약 13개월 일봉·배당): Yahoo Finance chart
   - 52주 고점 = 최근 365일 장중 고가 최댓값, 배당수익률 = 최근 365일 배당 합계 ÷ 종가
3) 걸러진 종목 + 기타 종목(watchlist)의 PER·시가총액·업종(quoteSummary), 분기 재무(fundamentals-timeseries)
   - 부채비율 = 부채총계 ÷ 자본총계, PBR = 시가총액 ÷ 자본총계
4) 의류·신발·명품 업종 제외, 직전 기준일 대비 신규·이탈 표시, 주요 종목 실적 발표 예정일
"""
import csv, io, json, os, sys, time, urllib.request, urllib.parse, http.cookiejar
from datetime import datetime, timezone, timedelta

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
THRESHOLD = -30.0
EXCLUDE_INDUSTRY = {"Apparel Retail", "Apparel Manufacturing", "Footwear & Accessories", "Luxury Goods", "Textile Manufacturing"}
EARNINGS_EXTRA = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "MU", "AMD", "PLTR", "COIN", "MSTR"]
SECTOR_KO = {"Technology": "기술", "Healthcare": "헬스케어", "Financial Services": "금융", "Consumer Cyclical": "경기소비재",
             "Consumer Defensive": "필수소비재", "Industrials": "산업재", "Energy": "에너지", "Utilities": "유틸리티",
             "Real Estate": "부동산", "Basic Materials": "소재", "Communication Services": "커뮤니케이션"}
INDUSTRY_KO = {"Semiconductors": "반도체", "Semiconductor Equipment & Materials": "반도체 장비", "Software - Application": "소프트웨어(응용)",
               "Software - Infrastructure": "소프트웨어(인프라)", "Biotechnology": "바이오", "Aerospace & Defense": "항공우주·방산",
               "Computer Hardware": "컴퓨터 하드웨어·저장장치", "Medical Devices": "의료기기", "Drug Manufacturers - General": "제약",
               "Internet Content & Information": "인터넷 서비스", "Internet Retail": "전자상거래", "Auto Manufacturers": "자동차",
               "Auto Parts": "자동차 부품", "Banks - Regional": "지역 은행", "Banks - Diversified": "은행", "Asset Management": "자산운용",
               "Capital Markets": "증권·자본시장", "Financial Data & Stock Exchanges": "금융 데이터·거래소", "Entertainment": "엔터테인먼트",
               "Information Technology Services": "IT 서비스", "Communication Equipment": "통신장비", "Telecom Services": "통신",
               "Oil & Gas E&P": "석유·가스 개발", "Utilities - Regulated Electric": "전력", "Restaurants": "외식", "Specialty Chemicals": "특수화학",
               "Healthcare Plans": "건강보험", "Diagnostics & Research": "진단·연구", "Medical Instruments & Supplies": "의료기기·소모품",
               "Electronic Components": "전자부품", "Credit Services": "신용·결제", "Travel Services": "여행", "Resorts & Casinos": "리조트·카지노",
               "Packaged Foods": "식품", "Residential Construction": "주택 건설", "Building Products & Equipment": "건축자재",
               "Specialty Industrial Machinery": "산업 기계", "Insurance - Property & Casualty": "손해보험", "Consumer Electronics": "가전·전자"}

_op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
_crumb = None


def get(url, headers=None, timeout=30):
    h = {"User-Agent": UA, "Accept": "*/*"}
    h.update(headers or {})
    with _op.open(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def yget(path):
    """Yahoo JSON (query2 → query1 재시도)."""
    last = None
    for host in ("query2", "query1"):
        try:
            return json.loads(get(f"https://{host}.finance.yahoo.com{path}"))
        except Exception as e:
            last = e
            time.sleep(1.5)
    raise RuntimeError(last)


def crumb():
    global _crumb
    if not _crumb:
        try:
            get("https://fc.yahoo.com")
        except Exception:
            pass  # 쿠키만 받으면 됨(응답은 404)
        _crumb = get("https://query2.finance.yahoo.com/v1/test/getcrumb").strip()
    return _crumb


def constituents():
    """{야후 심볼: {"name": 영문명, "index": [...]}}"""
    out = {}
    rows = list(csv.DictReader(io.StringIO(get("https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"))))
    for r in rows:
        out[r["Symbol"].strip().replace(".", "-")] = {"name": r["Security"].strip(), "index": ["S&P500"]}
    n_sp = len(out)
    nd = json.loads(get("https://api.nasdaq.com/api/quote/list-type/nasdaq100",
                        headers={"Accept": "application/json", "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}))["data"]["data"]["rows"]
    for r in nd:
        s = r["symbol"].strip().replace(".", "-").replace("/", "-")
        out.setdefault(s, {"name": r["companyName"].split(" Common Stock")[0].split(" Class ")[0].strip(), "index": []})["index"].append("나스닥100")
    print(f"구성종목: S&P500 {n_sp}개, 나스닥100 {len(nd)}개 → 합계 {len(out)}개")
    if n_sp < 450 or len(nd) < 90:
        raise RuntimeError("구성종목 수가 너무 적음")
    return out


def chart(sym):
    p2 = int(time.time()) + 86400
    res = yget(f"/v8/finance/chart/{urllib.parse.quote(sym)}?period1={p2 - 400 * 86400}&period2={p2}&interval=1d&includePrePost=false&events=div")["chart"]["result"][0]
    off, q = res["meta"].get("gmtoffset", 0), res["indicators"]["quote"][0]
    day = lambda t: datetime.fromtimestamp(t + off, tz=timezone.utc).strftime("%Y-%m-%d")
    rows = sorted({day(t): (float(h or c), float(c)) for t, h, c in zip(res["timestamp"], q["high"], q["close"]) if c and c > 0}.items())
    if len(rows) < 30:
        raise RuntimeError(f"too short {len(rows)}")
    d_last, (_, px) = rows[-1]
    cut = (datetime.strptime(d_last, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d")
    hi = max(h for d, (h, c) in rows if d > cut)
    divs = sum(float(x["amount"]) for x in ((res.get("events") or {}).get("dividends") or {}).values() if day(x["date"]) > cut)
    return {"asof": d_last, "price": round(px, 2), "chg1d": round((px / rows[-2][1][1] - 1) * 100, 2), "high52": round(hi, 2),
            "from_high": round((px / hi - 1) * 100, 2), "div_yield": round(divs / px * 100, 2)}


def money(v):
    return None if not v else f"${v / 1e12:.2f}T" if v >= 1e12 else f"${v / 1e9:.1f}B"


def summary(sym):
    """PER·선행PER·시가총액·업종·실적 발표 예정일."""
    d = yget(f"/v10/finance/quoteSummary/{urllib.parse.quote(sym)}?modules=summaryDetail,defaultKeyStatistics,assetProfile,calendarEvents&crumb={urllib.parse.quote(crumb())}")["quoteSummary"]["result"][0]
    raw = lambda x: x.get("raw") if isinstance(x, dict) else x
    sd, ks, ap = d.get("summaryDetail") or {}, d.get("defaultKeyStatistics") or {}, d.get("assetProfile") or {}
    per, eps = raw(sd.get("trailingPE")), raw(ks.get("trailingEps"))
    if per is None and eps is not None and eps < 0:
        per = -1.0  # 적자
    fper = raw(sd.get("forwardPE"))
    ed = [raw(x) for x in ((d.get("calendarEvents") or {}).get("earnings") or {}).get("earningsDate") or []]
    ind = ap.get("industry")
    return {"per": round(per, 2) if per is not None else None, "fper": round(fper, 2) if fper is not None else None,
            "mcap_raw": raw(sd.get("marketCap")), "industry": ind,
            "sector": INDUSTRY_KO.get(ind) or SECTOR_KO.get(ap.get("sector")) or ap.get("sector"),
            "earnings_ts": min(ed) if ed else None}


FIN_TYPES = {"quarterlyTotalLiabilitiesNetMinorityInterest": "liab", "quarterlyStockholdersEquity": "eq",
             "quarterlyCashAndCashEquivalents": "cash", "quarterlyRetainedEarnings": "ret"}


def fundamentals(sym, mcap_raw):
    """최근 분기말 재무 → 부채비율·현금성자산·이익잉여금(십억 달러)·PBR."""
    p2 = int(time.time()) + 86400
    d = yget(f"/ws/fundamentals-timeseries/v1/finance/timeseries/{urllib.parse.quote(sym)}?type={','.join(FIN_TYPES)}&period1={p2 - 800 * 86400}&period2={p2}")
    f = {}
    for res in d.get("timeseries", {}).get("result", []):
        typ = (res.get("meta", {}).get("type") or [None])[0]
        pts = [x for x in res.get(typ) or [] if x and x.get("reportedValue")]
        if typ in FIN_TYPES and pts:
            x = max(pts, key=lambda x: x["asOfDate"])
            f[FIN_TYPES[typ]] = (x["asOfDate"], float(x["reportedValue"]["raw"]))
    eq, li = f.get("eq"), f.get("liab")
    b = lambda k: round(f[k][1] / 1e9, 3) if k in f else None
    out = {"fin_period": (eq or li or f.get("cash") or (None,))[0], "cash": b("cash"), "retained": b("ret"), "debt_ratio": None, "pbr": None}
    if eq and li and eq[0] == li[0]:
        out["debt_ratio"] = round(li[1] / eq[1] * 100, 1) if eq[1] > 0 else -1  # -1 = 자본잠식(자본 0 이하)
    if eq and eq[1] > 0 and mcap_raw:
        out["pbr"] = round(mcap_raw / eq[1], 2)
    return out


def detail(sym):
    s = summary(sym)
    try:
        fin = fundamentals(sym, s["mcap_raw"])
    except Exception as e:
        print(f"  {sym} 재무 실패: {e}")
        fin = {}
    return {**s, **fin, "mcap": money(s["mcap_raw"])}


def main(data_path, out_path):
    data = json.load(open(data_path, encoding="utf-8"))
    wl = [w for w in data.get("watchlist", {}).get("items", []) if w.get("currency") != "KRW"]
    watch_us = [w["ticker"] for w in wl]
    # 한국어 종목명: scripts/us_names_ko.json(없는 종목은 화면에 영문명으로 표시) + 기타 종목에 적힌 이름
    names_ko = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "us_names_ko.json"), encoding="utf-8"))
    names_ko.update({w["ticker"]: w["name_ko"] for w in wl if w.get("name_ko")})
    try:
        prev = json.load(open(out_path, encoding="utf-8"))
    except Exception:
        prev = {}
    cons = constituents()

    hits, fails, asofs = [], [], []
    for i, (sym, meta) in enumerate(cons.items(), 1):
        try:
            c = chart(sym)
            asofs.append(c["asof"])
            if c["from_high"] <= THRESHOLD:
                hits.append({"ticker": sym, "name_ko": names_ko.get(sym), "name": meta["name"], "index": meta["index"], **c})
        except Exception as e:
            fails.append(f"{sym}: {e}")
        time.sleep(0.15)
        if i % 100 == 0:
            print(f"  {i}/{len(cons)} 처리, 해당 {len(hits)}개")
    if len(fails) > len(cons) * 0.2:
        print(f"시세 실패 {len(fails)}개 — 이전 파일 유지: {fails[:5]}")
        sys.exit(0 if prev else 1)

    rows, excluded, earn = [], [], {}
    for r in hits:
        try:
            det = detail(r["ticker"])
        except Exception as e:
            print(f"  {r['ticker']} 상세 실패: {e}")
            det = {}
        if det.get("earnings_ts"):
            earn[r["ticker"]] = det["earnings_ts"]
        if det.get("industry") in EXCLUDE_INDUSTRY:
            excluded.append(f"{r['name']}({det['industry']})")
            continue
        r.update({k: det.get(k) for k in ("per", "fper", "mcap", "sector", "pbr", "debt_ratio", "cash", "retained", "fin_period")})
        rows.append(r)
        time.sleep(0.3)
    rows.sort(key=lambda r: r["from_high"])

    # 기타 종목(미국): PER·시가총액·PBR·배당수익률·재무
    watch = {}
    for t in watch_us:
        try:
            det = detail(t)
            watch[t] = {k: det.get(k) for k in ("per", "fper", "mcap", "pbr", "debt_ratio", "cash", "retained", "fin_period")}
            watch[t]["div_yield"] = chart(t)["div_yield"]
            if det.get("earnings_ts"):
                earn[t] = det["earnings_ts"]
        except Exception as e:
            print(f"  watch {t} 실패: {e}")
            if t in prev.get("watch", {}):
                watch[t] = prev["watch"][t]
    # 실적 발표 예정일(기타 종목 + 주요 대형주, 앞으로 45일 이내, 한국 시간)
    for t in EARNINGS_EXTRA:
        if t not in earn:
            try:
                ts = summary(t)["earnings_ts"]
                if ts:
                    earn[t] = ts
            except Exception as e:
                print(f"  실적일 {t} 실패: {e}")
            time.sleep(0.3)
    now = time.time()
    keep = set(watch_us) | set(EARNINGS_EXTRA)
    earnings = sorted(({"ticker": t, "name_ko": names_ko.get(t), "name": cons.get(t, {}).get("name") or t,
                        "date": (datetime.fromtimestamp(ts, tz=timezone.utc) + timedelta(hours=9)).strftime("%Y-%m-%d"),
                        "time": (datetime.fromtimestamp(ts, tz=timezone.utc) + timedelta(hours=9)).strftime("%H:%M")}
                       for t, ts in earn.items() if t in keep and now - 86400 < ts < now + 45 * 86400), key=lambda e: (e["date"], e["time"]))

    latest = max(asofs) if asofs else None
    if prev.get("asof") and (not latest or latest < prev["asof"]):
        print(f"기준일이 이전({prev['asof']})보다 오래됨({latest}) — 이전 파일 유지")
        sys.exit(0)
    # 신규·이탈: 직전 기준일 목록과 비교(같은 기준일로 다시 돌면 이전 비교 결과 유지)
    changes = prev.get("changes")
    if prev.get("rows") and prev.get("asof") and latest and prev["asof"] < latest:
        old, new, hit_all = {r["ticker"]: r for r in prev["rows"]}, {r["ticker"] for r in rows}, {r["ticker"] for r in hits}
        failed = {f.split(":")[0] for f in fails}
        changes = {"from": prev["asof"], "to": latest, "added": [t for t in new if t not in old],
                   "removed": [{"ticker": t, "name_ko": o.get("name_ko") or o.get("name"), "prev_from_high": o.get("from_high")}
                               for t, o in old.items() if t not in new and t not in hit_all and t not in failed]}
    added = set((changes or {}).get("added", []))
    for r in rows:
        r["new"] = r["ticker"] in added

    out = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "asof": latest,
        "basis": "52주 고점(최근 1년 일별 장중 고가 중 최댓값)", "threshold": THRESHOLD,
        "universe": f"S&P500 + 나스닥100 편입 종목 {len(cons)}개",
        "source": "구성종목: S&P500 공개 목록(datasets)·나스닥 · 시세·PER·시가총액·업종·분기 재무·실적 발표일: Yahoo Finance",
        "source_url": "https://finance.yahoo.com/",
        "excluded_note": ("의류·신발·명품 업종 제외: " + ", ".join(excluded)) if excluded else "의류·신발·명품 업종 제외(이번 해당 없음)",
        "coverage_note": f"대상 {len(cons)}개 전 종목을 계산했습니다." + (f" 시세를 받지 못한 종목 {len(fails)}개는 빠져 있습니다." if fails else ""),
        "missing_names_ko": [r["ticker"] for r in rows if not r.get("name_ko")],
        "failed": fails[:30], "changes": changes, "watch": watch, "earnings": earnings, "rows": rows,
    }
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"기준일 {latest} · -30% 이하 {len(hits)}개(제외 {len(excluded)}) → {len(rows)}개 저장 · 실패 {len(fails)} · 한글명 없음 {len(out['missing_names_ko'])}")
    for r in rows[:40]:
        print(f"  {r['ticker']} {r.get('name_ko') or r['name']} | {r.get('sector')} | {r['price']} 고점 {r['high52']} {r['from_high']}% PER {r.get('per')}/{r.get('fper')} {r.get('mcap')} PBR {r.get('pbr')} 배당 {r['div_yield']}% 부채비율 {r.get('debt_ratio')}")
    print("watch", json.dumps(watch, ensure_ascii=False))
    print("earnings", json.dumps(earnings, ensure_ascii=False))
    print("changes", json.dumps(changes, ensure_ascii=False)[:600])
    for f in fails[:10]:
        print("  실패", f)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data.json", sys.argv[2] if len(sys.argv) > 2 else "us_drawdown.json")
