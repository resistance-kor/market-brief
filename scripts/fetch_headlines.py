"""RSS 헤드라인 수집 → headlines.json (제목·링크·출처·시각만 저장, 본문은 저장하지 않음)."""
import json, re, sys, time, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

def gnews(q):
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": q + " when:1d", "hl": "ko", "gl": "KR", "ceid": "KR:ko"})

FEEDS = [
    # (출처 이름, 분류, URL)
    ("한국경제 증권", "stock", "https://www.hankyung.com/feed/finance"),
    ("매일경제 증권", "stock", "https://www.mk.co.kr/rss/50200011/"),
    ("연합뉴스 경제", "stock", "https://www.yna.co.kr/rss/economy.xml"),
    ("구글뉴스: 뉴욕증시", "stock", gnews("뉴욕증시")),
    ("구글뉴스: 코스피", "stock", gnews("코스피 마감")),
    ("CNBC Markets", "stock", "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
    ("블록미디어", "coin", "https://www.blockmedia.co.kr/feed"),
    ("CoinDesk", "coin", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("구글뉴스: 비트코인", "coin", gnews("비트코인")),
]
KEEP_HOURS = 36
MAX_PER_CAT = {"stock": 90, "coin": 60}
UA = "Mozilla/5.0 (market-brief headline bot; +https://github.com/resistance-kor/market-brief)"

def text(el, *names):
    for n in names:
        x = el.find(n)
        if x is not None and (x.text or "").strip():
            return x.text.strip()
        if x is not None and x.get("href"):
            return x.get("href")
    return ""

def parse_date(s):
    if not s:
        return None
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)

def clean(t):
    t = re.sub(r"<[^>]+>", "", t or "")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:200]

def fetch(src, cat, url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
    root = ET.fromstring(raw)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    items = root.findall(".//item") or root.findall(".//a:entry", ns)
    out = []
    for it in items:
        title = clean(text(it, "title", "a:title") if it.find("title") is not None else (it.findtext("a:title", "", ns)))
        link = text(it, "link") or (it.find("a:link", ns).get("href") if it.find("a:link", ns) is not None else "")
        pub = parse_date(text(it, "pubDate", "{http://purl.org/dc/elements/1.1/}date") or it.findtext("a:updated", "", ns) or it.findtext("a:published", "", ns))
        if not title or not link.startswith("http") or pub is None:
            continue
        now = datetime.now(timezone.utc)
        if pub > now + timedelta(minutes=10):
            # 일부 국내 RSS(예: 매일경제)는 한국시간을 +0000으로 표기 → 9시간 보정
            pub = pub - timedelta(hours=9)
            if pub > now + timedelta(minutes=10):
                continue  # 그래도 미래면 버림
        name = src
        if src.startswith("구글뉴스"):  # 구글뉴스는 제목 끝에 " - 언론사" 가 붙음
            m = re.match(r"^(.*) - ([^-]{1,30})$", title)
            if m:
                title, name = m.group(1).strip(), m.group(2).strip()
        out.append({"title": title, "url": link, "source": name, "feed": src, "cat": cat, "published": pub.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return out

def main(path):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=KEEP_HOURS)
    items, status = [], []
    for src, cat, url in FEEDS:
        try:
            got = fetch(src, cat, url)
            fresh = [x for x in got if parse_date(x["published"]) >= cutoff]
            items += fresh
            status.append({"feed": src, "ok": True, "count": len(fresh)})
        except Exception as e:
            status.append({"feed": src, "ok": False, "error": type(e).__name__})
        time.sleep(1)
    seen, uniq = set(), []
    for x in sorted(items, key=lambda x: x["published"], reverse=True):
        key = re.sub(r"\W+", "", x["title"].lower())[:60]
        if key in seen or x["url"] in seen:
            continue
        seen.add(key); seen.add(x["url"]); uniq.append(x)
    kept, cnt = [], {}
    for x in uniq:
        if cnt.get(x["cat"], 0) < MAX_PER_CAT.get(x["cat"], 60):
            kept.append(x); cnt[x["cat"]] = cnt.get(x["cat"], 0) + 1
    data = {"updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "keep_hours": KEEP_HOURS, "feeds": status, "items": kept}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)
    ok = sum(1 for s in status if s["ok"])
    print(f"feeds ok {ok}/{len(status)}, items {len(data['items'])}")
    for s in status:
        print(s)
    if ok == 0:
        sys.exit(1)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "headlines.json")
