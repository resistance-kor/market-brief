import json, re, urllib.request
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
def get(url, headers=None):
    h = {"User-Agent": UA, "Accept": "*/*"}; h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=25) as r:
        return r.status, r.read()
def t(name, fn):
    try: print(f"== {name}: {fn()}")
    except Exception as e: print(f"== {name}: FAIL {type(e).__name__} {str(e)[:200]}")
def integ():
    st, raw = get("https://m.stock.naver.com/api/stock/005930/integration"); d = json.loads(raw)
    return list(d.keys()), [(x.get("code"), x.get("key"), x.get("value")) for x in d.get("totalInfos", [])], d.get("industryCode")
for path in ["index/KPI200/enrollStocks?page=1&pageSize=20", "index/KPI200/stocks?page=1&pageSize=20", "index/KPI200/basic",
             "index/KPI200/integration", "stocks/marketValue/KOSPI?page=1&pageSize=5", "index/KPI200/enrollStock?page=1&pageSize=20"]:
    t("naver m "+path, lambda p=path: (lambda s_r: (s_r[0], s_r[1][:400]))(get("https://m.stock.naver.com/api/"+p)))
t("naver integration 005930", integ)
t("naver basic 005930", lambda: get("https://m.stock.naver.com/api/stock/005930/basic")[1][:600])
t("naver finance annual", lambda: get("https://m.stock.naver.com/api/stock/005930/finance/annual")[1][:300])
def wiki():
    st, raw = get("https://en.wikipedia.org/w/index.php?title=KOSPI_200&action=raw"); txt = raw.decode()
    codes = re.findall(r"\b(\d{6})\b", txt); u = list(dict.fromkeys(codes))
    i = txt.find(u[0]) if u else 0
    return len(u), u[:10], txt[max(0,i-300):i+300], re.findall(r"(?i)as of [^\n|]{0,40}", txt)[:3]
t("wiki raw", wiki)
t("daum kospi200?", lambda: get("https://finance.daum.net/api/quotes/sectors?market=KOSPI200&perPage=3", {"Referer":"https://finance.daum.net/"})[1][:300])
t("daum A005930 keys", lambda: list(json.loads(get("https://finance.daum.net/api/quotes/A005930?summary=false", {"Referer":"https://finance.daum.net/quotes/A005930"})[1]).items())[:80])
