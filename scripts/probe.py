import json, re, urllib.request, http.cookiejar
B = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
def get(url, opener=None, headers=None):
    h = {"User-Agent": B, "Accept": "*/*"}; h.update(headers or {})
    with (opener or urllib.request.build_opener()).open(urllib.request.Request(url, headers=h), timeout=30) as r:
        return r.read()
def t(name, fn):
    try: print(f"== {name}: {fn()}")
    except Exception as e: print(f"== {name}: FAIL {type(e).__name__} {str(e)[:200]}")
t("naver integ codes", lambda: [(x.get("code"), x.get("key"), x.get("value")) for x in json.loads(get("https://m.stock.naver.com/api/stock/000810/integration")).get("totalInfos", [])])
t("naver etf integ", lambda: [(x.get("code"), x.get("key"), x.get("value")) for x in json.loads(get("https://m.stock.naver.com/api/stock/161510/integration")).get("totalInfos", [])])
t("fng", lambda: get("https://api.alternative.me/fng/?limit=3")[:400])
t("bitget funding", lambda: get("https://api.bitget.com/api/v2/mix/market/current-fund-rate?symbol=BTCUSDT&productType=usdt-futures")[:300])
t("bitget funding hist", lambda: get("https://api.bitget.com/api/v2/mix/market/history-fund-rate?symbol=BTCUSDT&productType=usdt-futures&pageSize=3")[:300])
t("okx funding", lambda: get("https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USDT-SWAP")[:300])
t("farside", lambda: (lambda b: (len(b), b[:150]))(get("https://farside.co.uk/btc/")))
t("sp500 csv", lambda: (lambda b: (len(b.splitlines()), b[:200]))(get("https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv").decode()))
def wiki(title):
    txt = get(f"https://en.wikipedia.org/w/index.php?title={title}&action=raw", headers={"User-Agent": "market-brief/1.0 (https://github.com/resistance-kor/market-brief)"}).decode()
    return len(txt), txt[txt.find("==Components=="):][:600] if "==Components==" in txt else txt[:200]
t("wiki ndx", lambda: wiki("Nasdaq-100"))
t("wiki spx", lambda: wiki("List_of_S%26P_500_companies")[0])
t("nasdaq api", lambda: (lambda d: (len(d["data"]["data"]["rows"]), d["data"]["data"]["rows"][0]))(json.loads(get("https://api.nasdaq.com/api/quote/list-type/nasdaq100", headers={"Accept": "application/json", "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}))))
cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
try: get("https://fc.yahoo.com", op)
except Exception: pass
c = get("https://query2.finance.yahoo.com/v1/test/getcrumb", op).decode(); print("crumb", len(c))
def qs(sym):
    d = json.loads(get(f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}?modules=summaryDetail,defaultKeyStatistics,assetProfile,price,calendarEvents&crumb={c}", op))["quoteSummary"]["result"][0]
    sd, ks, ap, ce = d.get("summaryDetail", {}), d.get("defaultKeyStatistics", {}), d.get("assetProfile", {}), d.get("calendarEvents", {})
    r = lambda x: x.get("raw") if isinstance(x, dict) else x
    return {k: r(sd.get(k)) for k in ("trailingPE", "forwardPE", "marketCap", "dividendYield", "trailingAnnualDividendYield", "fiftyTwoWeekHigh")}, {k: r(ks.get(k)) for k in ("priceToBook", "trailingEps", "forwardPE")}, ap.get("sector"), ap.get("industry"), ce.get("earnings", {}).get("earningsDate"), d.get("price", {}).get("longName")
for s in ("UNH", "NVDA", "LUNR", "TSLL", "BRK-B", "000810.KS"):
    t("qs " + s, lambda s=s: qs(s))
t("chart div", lambda: (lambda res: (list((res.get("events") or {}).get("dividends", {}).values())[-2:], res["meta"].get("fiftyTwoWeekHigh")))(json.loads(get("https://query1.finance.yahoo.com/v8/finance/chart/UNH?range=1y&interval=1d&events=div"))["chart"]["result"][0]))
