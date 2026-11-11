"""코스피200 편입 종목 중 52주 고점 대비 -30% 이하 종목 → kr_drawdown.json
1) 구성 종목: 네이버 금융 '코스피200 편입종목' 페이지
2) 시세(최근 약 1년 일봉): Yahoo Finance(<코드>.KS), 실패 시 네이버 siseJson
   - 52주 고점 = 최근 365일 일별 '고가' 중 최댓값(장중 고가 기준), 종가는 마지막 일봉 종가
3) 걸러진 종목만 네이버 종목 페이지에서 PER(후행)·추정 PER(선행)·업종·시가총액
4) 의류·신발·패션·명품 업종 제외
"""
import json, re, sys, time, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
THRESHOLD = -30.0
EXCLUDE_SECTOR = re.compile(r"섬유|의류|의복|신발|호화품|패션")


def get(url, timeout=25, enc=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*", "Referer": "https://finance.naver.com/"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    if enc:
        return raw.decode(enc, "replace")
    for e in ("utf-8", "euc-kr", "cp949"):
        try:
            return raw.decode(e)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", "replace")


UNIVERSE_LABEL = "코스피200 편입 종목"


def _scrape_pages(url_fmt, max_pages):
    found = {}
    for page in range(1, max_pages + 1):
        html = get(url_fmt.format(page=page), enc="euc-kr")
        before = len(found)
        for code, name in re.findall(r'code=(\d{6})"[^>]*>\s*([^<]+?)\s*</a>', html):
            found.setdefault(code, name.strip())
        if len(found) == before:
            break
        time.sleep(0.3)
    return found


def _mobile_api():
    found = {}
    for page in range(1, 4):
        raw = get(f"https://m.stock.naver.com/api/index/KPI200/enrollStocks?page={page}&pageSize=100")
        data = json.loads(raw)
        items = data if isinstance(data, list) else (data.get("stocks") or data.get("result") or data.get("items") or [])
        before = len(found)
        for it in items:
            code = it.get("itemCode") or it.get("code")
            name = it.get("stockName") or it.get("name")
            if code and name:
                found.setdefault(code, name)
        if len(found) == before:
            break
    return found


def constituents():
    """코스피200 구성종목. 여러 경로를 차례로 시도하고, 모두 실패하면 코스피 시가총액 상위 200으로 대체."""
    global UNIVERSE_LABEL
    tries = [
        ("코스피200 편입 종목", lambda: _scrape_pages("https://finance.naver.com/sise/entryJongmok.naver?type=KPI200&page={page}", 25)),
        ("코스피200 편입 종목", lambda: _scrape_pages("https://finance.naver.com/sise/entryJongmok.naver?&page={page}", 25)),
        ("코스피200 편입 종목", lambda: _scrape_pages("https://finance.naver.com/sise/entryJongmok.nhn?&page={page}", 25)),
        ("코스피200 편입 종목", _mobile_api),
    ]
    for label, fn in tries:
        try:
            got = fn()
            print(f"  구성종목 시도 → {len(got)}개")
            if len(got) >= 150:
                UNIVERSE_LABEL = label
                return got
        except Exception as e:
            print(f"  구성종목 시도 실패: {type(e).__name__} {e}")
    got = _scrape_pages("https://finance.naver.com/sise/sise_market_sum.naver?sosok=0&page={page}", 4)
    print(f"  대체: 코스피 시가총액 상위 → {len(got)}개")
    UNIVERSE_LABEL = "코스피 시가총액 상위 200 종목(코스피200 구성 목록을 받지 못해 대체)"
    return dict(list(got.items())[:200])


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


def naver_daily(code):
    end = datetime.now(timezone(timedelta(hours=9)))
    start = end - timedelta(days=400)
    txt = get(f"https://api.finance.naver.com/siseJson.naver?symbol={code}&requestType=1"
              f"&startTime={start:%Y%m%d}&endTime={end:%Y%m%d}&timeframe=day")
    out = []
    for m in re.finditer(r'\["(\d{8})",\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)', txt):
        d, o, h, l, c = m.groups()
        if float(c) > 0:
            out.append((f"{d[:4]}-{d[4:6]}-{d[6:]}", (float(h), float(c))))
    if len(out) < 60:
        raise RuntimeError(f"naver too short {len(out)}")
    return sorted(out), None, "네이버 금융"


def num(s):
    if s is None:
        return None
    s = s.replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def naver_detail(code):
    html = get(f"https://finance.naver.com/item/main.naver?code={code}", enc="euc-kr")
    per = re.search(r'id="_per">\s*([-\d,.]+)\s*<', html)
    fper = re.search(r'id="_cns_per">\s*([-\d,.]+)\s*<', html)
    sector = re.search(r'sise_group_detail\.naver\?type=upjong&(?:amp;)?no=\d+"[^>]*>\s*([^<]+?)\s*</a>', html)
    ms = re.search(r'id="_market_sum">(.*?)</em>', html, re.S)
    mcap = None
    if ms:
        t = re.sub(r"<[^>]+>", " ", ms.group(1))
        t = re.sub(r"\s+", " ", t).strip()          # 예: "1,060조 3,532"
        if t:
            mcap = (t + "억원") if not t.endswith("조") else (t + "원")
    eps_neg = None
    if not per:  # 적자 기업은 PER이 'N/A'로 나옴 → EPS 음수 여부로 적자 표시
        eps = re.search(r'id="_eps">\s*([-\d,.]+)\s*<', html)
        if eps and num(eps.group(1)) is not None and num(eps.group(1)) < 0:
            eps_neg = True
    return {
        "per": (-1.0 if eps_neg else (num(per.group(1)) if per else None)),
        "fper": num(fper.group(1)) if fper else None,
        "sector": sector.group(1).strip() if sector else None,
        "mcap": mcap,
    }


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
    if len(cons) < 150:
        print("구성종목이 너무 적음 — 이전 파일 유지")
        if prev:
            sys.exit(0)
        sys.exit(1)

    hits, fails, asofs = [], [], []
    for i, (code, name) in enumerate(cons.items(), 1):
        try:
            try:
                rows, en, src = yahoo_daily(code)
            except Exception as e1:
                rows, en, src = naver_daily(code)
            d_last, (_, px) = rows[-1]
            prev_close = rows[-2][1][1]
            cut = (datetime.strptime(d_last, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d")
            hi = max(h for d, (h, c) in rows if d > cut)
            fh = (px / hi - 1) * 100
            asofs.append(d_last)
            if fh <= THRESHOLD:
                hits.append({"ticker": code, "name_ko": name, "name": en or "", "index": ["코스피200"],
                             "asof": d_last, "price": round(px), "chg1d": round((px / prev_close - 1) * 100, 2),
                             "high52": round(hi), "from_high": round(fh, 2), "price_source": src})
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
        "universe": f"{UNIVERSE_LABEL} {len(cons)}개 (구성: 네이버 금융)",
        "source": "시세: Yahoo Finance(실패 시 네이버 금융) · PER·업종·시가총액: 네이버 금융 종목 페이지",
        "source_url": "https://finance.naver.com/sise/entryJongmok.naver?type=KPI200",
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
