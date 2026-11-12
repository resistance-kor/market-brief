import json, urllib.request, http.cookiejar
def t(name, url, ua, opener=None):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "identity"})
        with (opener or urllib.request.build_opener()).open(req, timeout=30) as r:
            b = r.read(); print(f"== {name}: {r.status} {len(b)} {b[:120]!r}")
            return b
    except Exception as e:
        print(f"== {name}: FAIL {e}")
for ua in ["market-brief resistance-kor@users.noreply.github.com", "Mozilla/5.0 (compatible; market-brief/1.0; +https://github.com/resistance-kor/market-brief) resistance-kor@users.noreply.github.com"]:
    t("sec tickers "+ua[:20], "https://www.sec.gov/files/company_tickers.json", ua)
    t("sec facts "+ua[:20], "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json", ua)
    t("sec submissions "+ua[:20], "https://data.sec.gov/submissions/CIK0000320193.json", ua)
cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
B = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
t("yahoo fc", "https://fc.yahoo.com", B, op)
c = t("yahoo crumb", "https://query2.finance.yahoo.com/v1/test/getcrumb", B, op)
if c:
    b = t("yahoo qs", f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/UNH?modules=balanceSheetHistoryQuarterly,financialData,defaultKeyStatistics&crumb={c.decode()}", B, op)
    if b:
        d = json.loads(b)["quoteSummary"]["result"][0]
        print("financialData keys", list(d.get("financialData", {}))[:40])
        bs = d.get("balanceSheetHistoryQuarterly", {}).get("balanceSheetStatements", [])
        print("bs", len(bs), list(bs[0])[:40] if bs else None)
        print("fd debtToEquity", d.get("financialData", {}).get("debtToEquity"), "totalCash", d.get("financialData", {}).get("totalCash"), "totalDebt", d.get("financialData", {}).get("totalDebt"))
    t("yahoo ts", "https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/UNH?type=quarterlyTotalLiabilitiesNetMinorityInterest,quarterlyStockholdersEquity,quarterlyCashAndCashEquivalents,quarterlyRetainedEarnings&period1=1700000000&period2=1900000000", B, op)
