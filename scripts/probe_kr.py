import json, re, time, urllib.request, http.cookiejar, traceback
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
def get(url, data=None, headers=None, opener=None):
    h = {"User-Agent": UA, "Accept": "*/*"}; h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h)
    with (opener or urllib.request.build_opener()).open(req, timeout=25) as r:
        return r.status, r.read()
def t(name, fn):
    try:
        print(f"== {name}: {fn()}")
    except Exception as e:
        print(f"== {name}: FAIL {type(e).__name__} {str(e)[:200]}")
def kind():
    st, raw = get("https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&marketType=stockMkt")
    txt = raw.decode("euc-kr", "replace"); codes = re.findall(r">(\d{6})<", txt)
    return st, len(raw), len(codes), codes[:5]
def krx_index():
    body = "bld=dbms/MDC/STAT/standard/MDCSTAT00601&locale=ko_KR&indIdx=1&indIdx2=028&trdDd=20261111&money=1&csvxls_isNo=false".encode()
    st, raw = get("https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd", data=body,
                  headers={"Referer": "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd", "Content-Type": "application/x-www-form-urlencoded"})
    return st, raw[:300]
def krx_mktcap():
    body = "bld=dbms/MDC/STAT/standard/MDCSTAT01501&locale=ko_KR&mktId=STK&trdDd=20261111&share=1&money=1&csvxls_isNo=false".encode()
    st, raw = get("https://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd", data=body,
                  headers={"Referer": "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd", "Content-Type": "application/x-www-form-urlencoded"})
    return st, raw[:300]
def yahoo_qs():
    cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    try: get("https://fc.yahoo.com", opener=op)
    except Exception as e: pass
    st, crumb = get("https://query2.finance.yahoo.com/v1/test/getcrumb", opener=op)
    crumb = crumb.decode()
    st2, raw = get(f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/005930.KS?modules=summaryDetail,defaultKeyStatistics,assetProfile,price&crumb={crumb}", opener=op)
    d = json.loads(raw)["quoteSummary"]["result"][0]
    sd = d["summaryDetail"]; ap = d.get("assetProfile", {})
    out = {k: (sd.get(k) or {}).get("raw") if isinstance(sd.get(k), dict) else sd.get(k) for k in ("trailingPE","forwardPE","marketCap","fiftyTwoWeekHigh")}
    out.update(sector=ap.get("sector"), industry=ap.get("industry"), name=d["price"].get("longName"))
    st3, raw3 = get(f"https://query2.finance.yahoo.com/v7/finance/quote?symbols=005930.KS,000660.KS,UNH&crumb={crumb}", opener=op)
    q = json.loads(raw3)["quoteResponse"]["result"]
    return crumb[:4], out, [(x["symbol"], x.get("trailingPE"), x.get("forwardPE"), x.get("marketCap"), x.get("fiftyTwoWeekHigh")) for x in q]
def daum():
    st, raw = get("https://finance.daum.net/api/quotes/A005930?summary=false", headers={"Referer": "https://finance.daum.net/quotes/A005930"})
    d = json.loads(raw); return st, {k: d.get(k) for k in ("name","tradePrice","per","high52wPrice","marketCap","wicsSectorName")}
def daum_kospi200():
    st, raw = get("https://finance.daum.net/api/quotes/sectors?market=KOSPI&perPage=5", headers={"Referer": "https://finance.daum.net/"})
    return st, raw[:200]
def naver_m():
    st, raw = get("https://m.stock.naver.com/api/stock/005930/integration")
    return st, raw[:200]
def wiki():
    st, raw = get("https://en.wikipedia.org/wiki/KOSPI_200")
    return st, len(re.findall(r"\b\d{6}\b", raw.decode("utf-8","replace")))
def kodex200_pdf():
    st, raw = get("https://www.samsungfund.com/api/v1/kodex/product-pdf/2ETF01.do?gijunYMD=")
    return st, raw[:200]
for n, f in [("KIND corpList", kind), ("KRX KOSPI200 구성", krx_index), ("KRX 시총", krx_mktcap), ("Yahoo quoteSummary/quote", yahoo_qs),
             ("Daum 종목", daum), ("Daum 기타", daum_kospi200), ("Naver mobile", naver_m), ("Wikipedia", wiki), ("KODEX200 PDF", kodex200_pdf)]:
    t(n, f)
try:
    import subprocess; subprocess.run(["pip","install","-q","pykrx","finance-datareader"],check=False)
    from pykrx import stock
    t("pykrx KOSPI200", lambda: (lambda l: (len(l), l[:5]))(stock.get_index_portfolio_deposit_file("1028")))
    import FinanceDataReader as fdr
    t("FDR KOSPI", lambda: (lambda df: (len(df), list(df.columns)[:12], df.head(3).values.tolist()))(fdr.StockListing("KOSPI")))
except Exception as e:
    print("lib FAIL", e)
