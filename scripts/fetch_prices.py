"""지수·코인·금리 일별 종가 전체 이력 수집 → prices.json
- 최근 3년은 일봉, 그 이전은 주봉(매주 마지막 거래일)으로 줄여 저장
- ath(사상 최고 종가)는 줄이기 전 전체 일봉에서 계산
- 1순위 Yahoo Finance, 실패 시 FRED / Coinbase로 대체
"""
import csv, io, json, sys, time, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

UA = "Mozilla/5.0 (market-brief price bot; +https://github.com/resistance-kor/market-brief)"

SERIES = {
    # key: (이름, 그룹, 단위, yahoo 심볼, 대체 소스)
    "KOSPI":  ("코스피",          "stock",  "pt",  "^KS11",   None),
    "NASDAQ": ("나스닥 종합",      "stock",  "pt",  "^IXIC",   ("fred", "NASDAQCOM")),
    "SP500":  ("S&P 500",         "stock",  "pt",  "^GSPC",   ("fred", "SP500")),
    "BTC":    ("비트코인",         "crypto", "USD", "BTC-USD", ("coinbase", "BTC-USD")),
    "ETH":    ("이더리움",         "crypto", "USD", "ETH-USD", ("coinbase", "ETH-USD")),
    "SOL":    ("솔라나",           "crypto", "USD", "SOL-USD", ("coinbase", "SOL-USD")),
    "US10Y":  ("미국 10년물 금리", "macro",  "%",   "^TNX",    ("fred", "DGS10")),
    "GOLD":   ("금 (온스당)",      "macro",  "USD", "GC=F",    ("coinbase", "PAXG-USD")),
    "WTI":    ("WTI 유가 (배럴당)", "macro",  "USD", "CL=F",    None),
    "USDKRW": ("원/달러 환율",     "macro",  "KRW", "KRW=X",   None),
    "DXY":    ("달러인덱스",       "macro",  "pt",  "DX-Y.NYB", None),
    "VIX":    ("VIX 변동성 지수",  "macro",  "pt",  "^VIX",    ("fred", "VIXCLS")),
}
# 기타 종목(watchlist): 화면 티커 → Yahoo 심볼. 최근 약 400일 일봉으로 종가·전일 대비·52주 고/저(종가 기준) 계산
WATCH = {
    "TSLL": "TSLL",
    "LUNR": "LUNR",
    "UNH": "UNH",
    "161510": "161510.KS",   # PLUS 고배당주 (KRX)
    "000810": "000810.KS",   # 삼성화재
    "086790": "086790.KS",   # 하나금융지주
}
SOURCE_NAME = {
    "yahoo": "Yahoo Finance", "fred": "FRED", "coinbase": "Coinbase Exchange",
}

def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def is_daily(pts):
    """최근 1년 구간의 날짜 간격 중앙값이 4일 이하면 일봉으로 판단."""
    tail = [datetime.strptime(d, "%Y-%m-%d") for d, _ in pts[-260:]]
    gaps = sorted((b - a).days for a, b in zip(tail, tail[1:]))
    return bool(gaps) and gaps[len(gaps) // 2] <= 4

def yahoo(sym):
    q = urllib.parse.quote(sym)
    for host in ("query1", "query2"):
        try:
            p2 = int(time.time()) + 86400
            raw = get(f"https://{host}.finance.yahoo.com/v8/finance/chart/{q}?period1=0&period2={p2}&interval=1d&includePrePost=false&events=")
            res = json.loads(raw)["chart"]["result"][0]
            ts = res["timestamp"]; close = res["indicators"]["quote"][0]["close"]
            off = res["meta"].get("gmtoffset", 0)
            pts = {}
            for t, c in zip(ts, close):
                if c is None or c <= 0:
                    continue
                d = datetime.fromtimestamp(t + off, tz=timezone.utc).strftime("%Y-%m-%d")
                pts[d] = round(float(c), 4)
            out = sorted(pts.items())
            if len(out) > 200 and is_daily(out):
                return out
            print(f"  yahoo {host} {sym}: 일봉이 아님(또는 너무 짧음) {len(out)}개")
        except Exception as e:
            print(f"  yahoo {host} {sym}: {type(e).__name__} {e}")
        time.sleep(2)
    raise RuntimeError("yahoo failed")

def yahoo_recent(sym, days=400):
    """최근 days일 일봉 종가와 Yahoo 메타(이름·통화·거래소)."""
    q = urllib.parse.quote(sym)
    p2 = int(time.time()) + 86400; p1 = p2 - (days + 1) * 86400
    last = None
    for host in ("query1", "query2"):
        try:
            raw = get(f"https://{host}.finance.yahoo.com/v8/finance/chart/{q}?period1={p1}&period2={p2}&interval=1d&includePrePost=false&events=")
            res = json.loads(raw)["chart"]["result"][0]
            meta = res["meta"]; off = meta.get("gmtoffset", 0)
            pts = {}
            for t, c in zip(res["timestamp"], res["indicators"]["quote"][0]["close"]):
                if c is None or c <= 0:
                    continue
                pts[datetime.fromtimestamp(t + off, tz=timezone.utc).strftime("%Y-%m-%d")] = float(c)
            out = sorted(pts.items())
            if len(out) >= 30:
                return out, meta
            last = f"too short {len(out)}"
        except Exception as e:
            last = f"{type(e).__name__} {e}"
        time.sleep(2)
    raise RuntimeError(last)

def naver_info(code):
    """국내 종목 PER·추정PER·시가총액: 네이버 증권 모바일 API (ETF는 PER 없음)."""
    try:
        d = json.loads(get(f"https://m.stock.naver.com/api/stock/{code}/integration"))
    except Exception as e:
        return {"naver_error": str(e)[:80]}
    info = {x.get("code"): x.get("value") for x in d.get("totalInfos", [])}
    def num(v):
        import re
        m = re.search(r"-?[\d,]+(?:\.\d+)?", v or "")
        return float(m.group(0).replace(",", "")) if m else None
    per = num(info.get("per"))
    if per is None and (num(info.get("eps")) or 0) < 0:
        per = -1.0
    mv = info.get("marketValue")
    return {"per": per, "fper": num(info.get("cnsPer")), "mcap": (mv + "원") if mv else None,
            "pbr": num(info.get("pbr")), "div_yield": num(info.get("dividendYieldRatio"))}

def watch_quote(sym):
    pts, meta = yahoo_recent(sym)
    d_last, px = pts[-1]
    prev = pts[-2][1]
    cut = (datetime.strptime(d_last, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d")
    yr = [v for d, v in pts if d > cut]
    hi, lo = max(yr), min(yr)
    r = lambda v, n=4: round(v, n)
    return {
        "symbol": sym,
        "yahoo_name": meta.get("longName") or meta.get("shortName"),
        "currency": meta.get("currency"),
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
        "asof": d_last, "price": r(px), "prev_close": r(prev),
        "chg1d": round((px / prev - 1) * 100, 2),
        "high52_close": r(hi), "low52_close": r(lo),
        "from_high": round((px / hi - 1) * 100, 2),
        "basis": "최근 52주 일별 종가 기준",
        "spark": [round(v, 2) for d, v in pts if d > cut][::-1][::5][::-1],  # 최근 1년 종가, 5거래일 간격(마지막 값 포함)
        "source": f"Yahoo Finance ({sym})",
    }

def crypto_indicators(prev):
    """코인 심리·수급 지표. 각 항목은 실패하면 이전 값을 유지."""
    import re
    out = dict(prev or {})
    try:  # 공포·탐욕 지수 (alternative.me, 0=극단적 공포 ~ 100=극단적 탐욕)
        d = json.loads(get("https://api.alternative.me/fng/?limit=30"))["data"]
        KO = {"Extreme Fear": "극단적 공포", "Fear": "공포", "Neutral": "중립", "Greed": "탐욕", "Extreme Greed": "극단적 탐욕"}
        out["fng"] = {"value": int(d[0]["value"]), "label": KO.get(d[0]["value_classification"], d[0]["value_classification"]),
                      "date": datetime.fromtimestamp(int(d[0]["timestamp"]), tz=timezone.utc).strftime("%Y-%m-%d"),
                      "hist": [int(x["value"]) for x in d][::-1], "source": "alternative.me"}
        print("fng", out["fng"]["value"], out["fng"]["label"])
    except Exception as e:
        print("fng 실패", e)
    try:  # 무기한 선물 펀딩비 (Bitget USDT-M)
        fr = {}
        for c in ("BTC", "ETH", "SOL"):
            x = json.loads(get(f"https://api.bitget.com/api/v2/mix/market/current-fund-rate?symbol={c}USDT&productType=usdt-futures"))["data"][0]
            fr[c] = {"rate_pct": round(float(x["fundingRate"]) * 100, 4), "interval_h": int(float(x.get("fundingRateInterval") or 8))}
            time.sleep(0.2)
        out["funding"] = {"items": fr, "asof": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source": "Bitget USDT-M 무기한 선물"}
        print("funding", fr)
    except Exception as e:
        print("funding 실패", e)
    try:  # 미국 비트코인 현물 ETF 일별 순유입 (Farside, 백만 달러)
        html = get("https://farside.co.uk/btc/").decode("utf-8", "replace")
        rows = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
            cells = [re.sub(r"<[^>]+>|&nbsp;|\s+", " ", c).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            if len(cells) < 3 or not re.fullmatch(r"\d{1,2} \w{3} \d{4}", cells[0]):
                continue
            t = cells[-1].replace(",", "")
            m = re.fullmatch(r"\(?(-?[\d.]+)\)?", t)
            if not m:
                continue
            v = float(m.group(1)) * (-1 if t.startswith("(") else 1)
            rows.append((datetime.strptime(cells[0], "%d %b %Y").strftime("%Y-%m-%d"), v))
        rows.sort()
        if rows:
            out["etf_flow"] = {"unit": "백만 달러", "days": [{"date": d, "net": v} for d, v in rows[-5:]], "source": "Farside Investors"}
            print("etf_flow", rows[-5:])
        else:
            print("etf_flow: 표를 찾지 못함")
    except Exception as e:
        print("etf_flow 실패", e)
    return out

def fred(sid):
    raw = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}").decode()
    pts = []
    for row in csv.reader(io.StringIO(raw)):
        if len(row) < 2 or row[0] in ("DATE", "observation_date"):
            continue
        try:
            v = float(row[1])
        except ValueError:
            continue
        pts.append((row[0], v))
    if len(pts) < 200 or not is_daily(pts):
        raise RuntimeError("fred too short / not daily")
    return pts

def coinbase(pid):
    pts = {}
    end = datetime.now(timezone.utc)
    for _ in range(15):  # 300일씩 거꾸로
        start = end - timedelta(days=300)
        url = (f"https://api.exchange.coinbase.com/products/{pid}/candles?granularity=86400"
               f"&start={start.strftime('%Y-%m-%dT%H:%M:%SZ')}&end={end.strftime('%Y-%m-%dT%H:%M:%SZ')}")
        rows = json.loads(get(url))
        if not rows:
            break
        for t, lo, hi, op, cl, vol in rows:
            pts[datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d")] = float(cl)
        end = start
        time.sleep(0.5)
    if len(pts) < 200:
        raise RuntimeError("coinbase too short")
    return sorted(pts.items())

def thin(pts, daily_years=3):
    """최근 daily_years년은 일봉, 그 이전은 ISO 주의 마지막 값만."""
    if not pts:
        return pts
    cut = (datetime.strptime(pts[-1][0], "%Y-%m-%d") - timedelta(days=365 * daily_years)).strftime("%Y-%m-%d")
    old, out = {}, []
    for d, v in pts:
        if d < cut:
            y, w, _ = datetime.strptime(d, "%Y-%m-%d").isocalendar()
            old[(y, w)] = (d, v)
        else:
            out.append((d, v))
    return sorted(old.values()) + out

def encode(points, unit):
    """용량 절감: 첫 날짜(d0) + 날짜 간격(dd, 일 단위) + 값 배열(v, 지수·가격 소수 2자리 / 금리 3자리)."""
    nd = 3 if unit == "%" else 2
    first = datetime.strptime(points[0][0], "%Y-%m-%d")
    prev, gaps, vals = first, [], []
    for d, v in points:
        cur = datetime.strptime(d, "%Y-%m-%d")
        gaps.append((cur - prev).days); prev = cur
        r = round(v, nd)
        vals.append(int(r) if r == int(r) else r)
    return {"d0": points[0][0], "dd": gaps[1:], "v": vals}

def main(path):
    try:
        prev = json.load(open(path, encoding="utf-8"))
    except Exception:
        prev = {"series": {}}
    out = {"updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "series": {}}
    ok = 0
    for key, (name, group, unit, ysym, fb) in SERIES.items():
        pts, src = None, None
        try:
            pts, src = yahoo(ysym), f"Yahoo Finance ({ysym})"
        except Exception:
            if fb:
                try:
                    kind, sid = fb
                    pts = fred(sid) if kind == "fred" else coinbase(sid)
                    src = f"{SOURCE_NAME[kind]} ({sid})"
                except Exception as e:
                    print(f"  fallback {key}: {type(e).__name__} {e}")
        if not pts:
            if key in prev.get("series", {}):
                out["series"][key] = prev["series"][key]
                out["series"][key]["stale"] = True
                print(f"{key}: 실패 — 이전 값 유지")
            else:
                print(f"{key}: 실패 — 데이터 없음")
            continue
        # 검증: 날짜 오름차순·중복 없음·값 > 0
        pts = sorted({d: v for d, v in pts if v and v > 0}.items())
        ath_d, ath_v = max(pts, key=lambda p: p[1])
        thinned = thin(pts)
        out["series"][key] = {
            "name": name, "group": group, "unit": unit, "source": src,
            "first": pts[0][0], "last": pts[-1][0],
            "ath": {"date": ath_d, "value": ath_v},
            **encode(thinned, unit),
        }
        ok += 1
        print(f"{key}: {src} {len(pts)}일 ({pts[0][0]}~{pts[-1][0]}) 마지막 {pts[-1][1]} / 사상최고 {ath_v} ({ath_d}) → 저장 {len(thinned)}개")
        time.sleep(1)
    out["watch"] = {}
    for tk, sym in WATCH.items():
        try:
            w = watch_quote(sym)
            if sym.endswith(".KS"):
                w.update(naver_info(tk))
            out["watch"][tk] = w
            print(f"watch {tk}: {w['yahoo_name']} {w['currency']} {w['asof']} {w['price']} ({w['chg1d']}%) 52주종가고점 {w['high52_close']} → {w['from_high']}%")
        except Exception as e:
            if tk in prev.get("watch", {}):
                out["watch"][tk] = dict(prev["watch"][tk], stale=True)
            print(f"watch {tk}: 실패 {e}")
        time.sleep(1)
    out["crypto_ind"] = crypto_indicators(prev.get("crypto_ind"))
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"prices.json {len(json.dumps(out, ensure_ascii=False, separators=(',', ':')).encode()):,} bytes")
    print(f"ok {ok}/{len(SERIES)}")
    if ok == 0:
        sys.exit(1)

if __name__ == "__main__":

    main(sys.argv[1] if len(sys.argv) > 1 else "prices.json")
