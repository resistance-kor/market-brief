"""미국 하락 종목·기타 종목의 재무 지표 → us_fin.json
출처: SEC EDGAR XBRL companyfacts (data.sec.gov, 무료·공식). 10-Q/10-K로 제출된 가장 최근 분기말 값.
- 부채비율 = 부채총계(Liabilities) ÷ 자본총계(StockholdersEquity) × 100
  (Liabilities가 없으면 LiabilitiesAndStockholdersEquity − 자본총계)
- 현금성자산 = CashAndCashEquivalentsAtCarryingValue
- 이익잉여금 = RetainedEarningsAccumulatedDeficit (미국은 액면가가 매우 작아 한국식 유보율이 의미가 없어 대신 표시)
"""
import json, sys, time, urllib.request
from datetime import datetime, timezone

UA = "market-brief dashboard (github.com/resistance-kor/market-brief)"
FORMS = {"10-Q", "10-K", "10-Q/A", "10-K/A", "20-F", "40-F", "6-K"}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def latest(facts, *names):
    """여러 태그 중 가장 최근 분기말(end) 값. (값, 기준일, 서식, 태그)"""
    best = None
    for ns in ("us-gaap", "ifrs-full"):
        for n in names:
            node = facts.get(ns, {}).get(n)
            if not node:
                continue
            for unit, arr in node.get("units", {}).items():
                if unit not in ("USD",):
                    continue
                for x in arr:
                    if x.get("form") not in FORMS or "end" not in x or x.get("val") is None:
                        continue
                    key = (x["end"], x.get("filed", ""))
                    if best is None or key > best[0]:
                        best = (key, float(x["val"]), x["end"], x.get("form"), n)
    return None if best is None else best[1:]


def main(data_path, out_path):
    d = json.load(open(data_path, encoding="utf-8"))
    tickers = [r["ticker"] for r in d.get("drawdown", {}).get("us", {}).get("rows", [])]
    tickers += [w["ticker"] for w in d.get("watchlist", {}).get("items", []) if w.get("currency") != "KRW"]
    tickers = list(dict.fromkeys(t.upper() for t in tickers))
    try:
        prev = json.load(open(out_path, encoding="utf-8")).get("items", {})
    except Exception:
        prev = {}
    cik = {v["ticker"].upper(): v["cik_str"] for v in get("https://www.sec.gov/files/company_tickers.json").values()}
    items, miss = {}, []
    for t in tickers:
        c = cik.get(t) or cik.get(t.replace(".", "-"))
        if not c:
            miss.append(f"{t}: SEC 등록 회사 아님(ETF 등)")
            continue
        try:
            facts = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(c):010d}.json").get("facts", {})
        except Exception as e:
            miss.append(f"{t}: {e}")
            if t in prev:
                items[t] = dict(prev[t], stale=True)
            time.sleep(0.3)
            continue
        eq = latest(facts, "StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest", "Equity")
        li = latest(facts, "Liabilities")
        if li is None or (eq and li[1] != eq[1]):
            tot = latest(facts, "LiabilitiesAndStockholdersEquity", "EquityAndLiabilities")
            if tot and eq and tot[1] == eq[1]:
                li = (tot[0] - eq[0], tot[1], tot[2], "LiabilitiesAndStockholdersEquity-Equity")
        cash = latest(facts, "CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "CashAndCashEquivalents")
        re_ = latest(facts, "RetainedEarningsAccumulatedDeficit", "RetainedEarnings")
        item = {"period": eq[1] if eq else None, "form": eq[2] if eq else None,
                "equity_b": round(eq[0] / 1e9, 3) if eq else None,
                "liabilities_b": round(li[0] / 1e9, 3) if li else None,
                "cash_b": round(cash[0] / 1e9, 3) if cash else None,
                "retained_b": round(re_[0] / 1e9, 3) if re_ else None}
        if eq and li and li[1] == eq[1]:
            item["debt_ratio"] = round(li[0] / eq[0] * 100, 1) if eq[0] > 0 else -1  # -1 = 자본잠식(자본 ≤ 0)
        else:
            item["debt_ratio"] = None
        items[t] = item
        print(f"{t}: 기준 {item['period']} {item['form']} 부채비율 {item['debt_ratio']} 현금 {item['cash_b']}B 이익잉여금 {item['retained_b']}B")
        time.sleep(0.3)  # SEC 권장: 초당 10건 이하
    out = {"updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "source": "SEC EDGAR XBRL companyfacts (10-Q/10-K 최근 분기말)",
           "source_url": "https://www.sec.gov/edgar/search/",
           "items": items, "missing": miss}
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(items)}개 저장, 없음 {len(miss)}: {miss}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data.json", sys.argv[2] if len(sys.argv) > 2 else "us_fin.json")
