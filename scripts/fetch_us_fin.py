"""미국 하락 종목·기타 종목의 재무 지표 → us_fin.json
출처: Yahoo Finance 분기 재무제표(fundamentals-timeseries). 가장 최근 분기말 값.
(SEC EDGAR는 GitHub Actions 서버 접속을 403으로 막아 사용하지 않음)
- 부채비율 = 부채총계(TotalLiabilitiesNetMinorityInterest) ÷ 자본총계(StockholdersEquity) × 100
- 현금성자산 = CashAndCashEquivalents
- 이익잉여금 = RetainedEarnings (미국은 액면가가 매우 작아 한국식 유보율이 의미가 없어 대신 표시)
"""
import json, sys, time, urllib.request, urllib.parse
from datetime import datetime, timezone

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
TYPES = {"quarterlyTotalLiabilitiesNetMinorityInterest": "liab", "quarterlyStockholdersEquity": "eq",
         "quarterlyCashAndCashEquivalents": "cash", "quarterlyRetainedEarnings": "ret"}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def fundamentals(sym):
    """{필드: (asOfDate, 값)} — 필드별 가장 최근 분기."""
    p2 = int(time.time()) + 86400
    p1 = p2 - 800 * 86400
    last = None
    for host in ("query2", "query1"):
        try:
            d = get(f"https://{host}.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{urllib.parse.quote(sym)}"
                    f"?type={','.join(TYPES)}&period1={p1}&period2={p2}")
            out = {}
            for res in d.get("timeseries", {}).get("result", []):
                typ = (res.get("meta", {}).get("type") or [None])[0]
                pts = [x for x in res.get(typ) or [] if x and x.get("reportedValue")]
                if typ in TYPES and pts:
                    x = max(pts, key=lambda x: x["asOfDate"])
                    out[TYPES[typ]] = (x["asOfDate"], float(x["reportedValue"]["raw"]))
            return out
        except Exception as e:
            last = e
            time.sleep(1)
    raise RuntimeError(last)


def main(data_path, out_path):
    d = json.load(open(data_path, encoding="utf-8"))
    tickers = [r["ticker"] for r in d.get("drawdown", {}).get("us", {}).get("rows", [])]
    tickers += [w["ticker"] for w in d.get("watchlist", {}).get("items", []) if w.get("currency") != "KRW"]
    tickers = list(dict.fromkeys(t.upper() for t in tickers))
    try:
        prev = json.load(open(out_path, encoding="utf-8")).get("items", {})
    except Exception:
        prev = {}
    items, miss = {}, []
    for t in tickers:
        try:
            f = fundamentals(t)
        except Exception as e:
            miss.append(f"{t}: {e}")
            if t in prev:
                items[t] = dict(prev[t], stale=True)
            continue
        if not f:
            miss.append(f"{t}: 재무 자료 없음(ETF 등)")
            continue
        eq, li, cash, ret = f.get("eq"), f.get("liab"), f.get("cash"), f.get("ret")
        b = lambda x: round(x[1] / 1e9, 3) if x else None
        item = {"period": eq[0] if eq else (li or cash or ret)[0], "equity_b": b(eq), "liabilities_b": b(li), "cash_b": b(cash), "retained_b": b(ret)}
        if eq and li and eq[0] == li[0]:
            item["debt_ratio"] = round(li[1] / eq[1] * 100, 1) if eq[1] > 0 else -1  # -1 = 자본잠식(자본 0 이하)
        else:
            item["debt_ratio"] = None
        items[t] = item
        print(f"{t}: 기준 {item['period']} 부채비율 {item['debt_ratio']} 현금 {item['cash_b']}B 이익잉여금 {item['retained_b']}B")
        time.sleep(0.4)
    out = {"updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "source": "Yahoo Finance 분기 재무제표(최근 분기말)",
           "source_url": "https://finance.yahoo.com/",
           "items": items, "missing": miss}
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(items)}개 저장, 없음 {len(miss)}: {miss}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data.json", sys.argv[2] if len(sys.argv) > 2 else "us_fin.json")
