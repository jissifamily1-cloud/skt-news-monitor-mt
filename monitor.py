# -*- coding: utf-8 -*-
"""특이뉴스 모니터링 — 통신업계 키워드 기사 탐지 → 텔레그램 발송.

소스: 네이버 뉴스 검색 Open API (NAVER_CLIENT_ID/SECRET 없으면 Google News RSS fallback)
매칭: 제목에 KEYWORDS 중 하나라도 있으면 발송 (BLOCK_KEYWORDS 있으면 제외)
중복: state.json seen_urls / seen_titles + 유사 제목(near-dup) 묶음 차단
발송: run당 MAX_SEND_PER_RUN건, 메시지 간 SEND_INTERVAL_SEC 간격, 429시 안전 중단
      성공한 건만 seen 처리하고 save_state는 항상 실행 → 크래시·재발송 루프 방지
실행: GitHub Actions (cron-job.org 트리거, 06~22시 KST)
야간: 22시~06시 발행분은 06시 첫 실행에서 모아보기로 일괄 발송

환경변수:
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (필수)
  NAVER_CLIENT_ID, NAVER_CLIENT_SECRET (권장 — 네이버 뉴스 검색 API)
  DRY_RUN=1 이면 텔레그램 발송 생략 (테스트용)
"""

import json
import os
import re
import sys
import time
import html as html_mod
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from config import (
    KEYWORDS,
    BLOCK_KEYWORDS,
    BLOCK_DOMAINS,
    BLOCK_URL_KEYWORDS,
    EXCLUDED_WORDS,
    WORD_BOUNDARY_KEYWORDS,
    RECENCY_MINUTES,
    MAX_SEND_PER_RUN,
    SEND_INTERVAL_SEC,
    NEAR_DUP_MIN_SHARED,
    NEAR_DUP_HOURS,
    NEAR_DUP_MAX,
    PRESS_FETCH_MAX,
    PRESS_FETCH_TIMEOUT,
    FETCH_COUNT,
    FETCH_COUNT_NIGHT,
    MAX_SEEN_URLS,
    PRESS_MAP,
)

KST = timezone(timedelta(hours=9))
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
NAVER_ID = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")
DRY_RUN = os.environ.get("DRY_RUN", "") == "1"


# ---------- 매칭 ----------

def _clean_text(text):
    """EXCLUDED_WORDS 제거 후 반환."""
    for w in EXCLUDED_WORDS:
        text = text.replace(w, "")
    return text


def _contains_keyword(text, keyword):
    """키워드 매칭. 짧은 영문 키워드는 영문자 경계 적용.

    (?<![A-Za-z])KT(?![A-Za-z]) — "SKT" 안의 KT는 제외, "KT가"처럼
    한글이 붙은 경우는 매칭 (기존 \\b 방식은 한글 인접 시 매칭 실패).
    """
    if keyword in WORD_BOUNDARY_KEYWORDS:
        pattern = r"(?<![A-Za-z])" + re.escape(keyword) + r"(?![A-Za-z])"
        return re.search(pattern, text, re.IGNORECASE) is not None
    return keyword in text


def match_keyword(title):
    """제목에 KEYWORDS 중 하나라도 있으면 해당 키워드 반환.

    BLOCK_KEYWORDS(야구 등 제외 토픽)가 제목에 있으면 무조건 제외.
    """
    text = _clean_text(title)
    if any(b in text for b in BLOCK_KEYWORDS):
        return None
    return next((k for k in KEYWORDS if _contains_keyword(text, k)), None)


# ---------- 유사 제목(near-duplicate) 판정 ----------

# 제목 토큰화 시 무시할 일반 단어 (같은 사안 판정 정확도 향상)
_STOP_TOKENS = frozenset({
    "속보", "단독", "공식", "종합", "기자", "뉴스", "오늘", "내일", "관련",
    "위해", "통해", "대한", "밝혀", "예정", "이번", "최대", "최초", "그룹",
    "AI", "추진", "전환", "조직", "으로", "일하는", "방식",
})

_KW_LOWER = frozenset(k.lower() for k in KEYWORDS)


def _title_tokens(title):
    """제목에서 고유 토큰 집합 추출. 괄호 태그·일반어·키워드·숫자 제거, 2자 이상만.

    키워드(SKT 등)는 모든 관련 기사에 공통이라 제외해야 변별력이 생긴다.
    """
    t = _clean_text(title)
    t = re.sub(r"\[[^\]]*\]", " ", t)            # [속보] [단독] 등 제거
    out = set()
    for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", t):
        if w in _STOP_TOKENS or w.lower() in _KW_LOWER or w.isdigit():
            continue
        out.add(w)
    return out


def _is_near_dup(tokens, sig_list):
    """tokens가 sig_list 중 하나와 고유어를 NEAR_DUP_MIN_SHARED개 이상 공유하면 True."""
    return any(len(tokens & s) >= NEAR_DUP_MIN_SHARED for s in sig_list)


def _load_recent_sigs(state, now):
    """state의 recent_sigs 중 NEAR_DUP_HOURS 이내만 토큰셋 리스트로 반환 (만료분 정리)."""
    kept = []
    sets = []
    for item in state.get("recent_sigs", []):
        try:
            ts = datetime.fromisoformat(item[0])
        except Exception:
            continue
        if (now - ts) <= timedelta(hours=NEAR_DUP_HOURS):
            kept.append(item)
            sets.append(set(item[1].split()))
    state["recent_sigs"] = kept[-NEAR_DUP_MAX:]
    return sets


# ---------- 수집 ----------

def _http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _strip_tags(s):
    return html_mod.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def fetch_naver_api(query, count):
    """네이버 뉴스 검색 Open API. [(title, url, published_dt, source, desc), ...]"""
    url = (
        "https://openapi.naver.com/v1/search/news.json?query="
        + urllib.parse.quote(query)
        + "&display=%d&sort=date" % count
    )
    raw = _http_get(url, {
        "X-Naver-Client-Id": NAVER_ID,
        "X-Naver-Client-Secret": NAVER_SECRET,
    })
    items = json.loads(raw).get("items", [])
    results = []
    for it in items:
        title = _strip_tags(it.get("title", ""))
        link = it.get("originallink") or it.get("link", "")
        desc = _strip_tags(it.get("description", ""))
        try:
            pub = parsedate_to_datetime(it.get("pubDate", "")).astimezone(KST)
        except Exception:
            pub = None
        results.append((title, link, pub, "", desc))
    return results


def fetch_google_rss(query, count):
    """Google News RSS fallback. [(title, url, published_dt, source, desc), ...]"""
    url = (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote(query + " when:1d")
        + "&hl=ko&gl=KR&ceid=KR:ko"
    )
    raw = _http_get(url)
    results = []
    for m in re.finditer(r"<item>(.*?)</item>", raw, re.S):
        block = m.group(1)
        t = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", block, re.S)
        l = re.search(r"<link/?>(.*?)(?:</link>|<)", block, re.S)
        d = re.search(r"<pubDate>(.*?)</pubDate>", block, re.S)
        s = re.search(r"<source[^>]*>(.*?)</source>", block, re.S)
        dsc = re.search(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", block, re.S)
        if not t or not l:
            continue
        title = _strip_tags(t.group(1))
        source = _strip_tags(s.group(1)) if s else ""
        desc = _strip_tags(dsc.group(1)) if dsc else ""
        # Google RSS 제목 끝의 " - 매체명" 제거
        if source and title.endswith(" - " + source):
            title = title[: -(len(source) + 3)]
        try:
            pub = parsedate_to_datetime(d.group(1)).astimezone(KST) if d else None
        except Exception:
            pub = None
        results.append((title, l.group(1).strip(), pub, source, desc))
    return results[:count]


def fetch_all(count):
    use_naver = bool(NAVER_ID and NAVER_SECRET)
    print("source: %s, count: %d" % ("naver-api" if use_naver else "google-rss", count))
    articles = []
    for q in KEYWORDS:
        try:
            articles += fetch_naver_api(q, count) if use_naver else fetch_google_rss(q, count)
        except Exception as e:
            print("fetch error (%s): %s" % (q, e))
    return articles


# ---------- 상태 ----------

def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"seen_urls": [], "last_run": "", "initialized": False}


def save_state(state):
    state["seen_urls"] = state["seen_urls"][-MAX_SEEN_URLS:]
    state["seen_titles"] = state.get("seen_titles", [])[-MAX_SEEN_URLS:]
    state["recent_sigs"] = state.get("recent_sigs", [])[-NEAR_DUP_MAX:]
    state["last_run"] = datetime.now(KST).isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


_STRIP_PARAMS = frozenset({
    "fbclid", "gclid", "ref", "from", "sid", "cate", "stype", "page",
    "mode", "nt", "naver_source", "s_ref", "searchid", "search_id",
    "category", "section", "listid", "list_id",
})

def _norm_url(u):
    """dedup 키: 추적·섹션 파라미터 제거 후 scheme+host+path+기사ID만 유지."""
    parts = urllib.parse.urlsplit(u)
    query = ""
    if parts.query:
        kept = [
            (k, v) for k, v in urllib.parse.parse_qsl(parts.query)
            if not k.lower().startswith("utm")
            and k.lower() not in _STRIP_PARAMS
        ]
        query = urllib.parse.urlencode(kept)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


# ---------- 발송 ----------

def _h(text):
    """HTML 특수문자 이스케이프 (&, <, >)."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _post_telegram(text):
    """텔레그램 단건 메시지 발송 (HTML 파싱 모드). 실패 시 예외 그대로 전파."""
    if DRY_RUN:
        print("[DRY_RUN] message:\n%s\n" % text)
        return
    chat_id_val = int(CHAT_ID) if CHAT_ID.lstrip("-").isdigit() else CHAT_ID
    payload = json.dumps({
        "chat_id": chat_id_val,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.telegram.org/bot%s/sendMessage" % BOT_TOKEN,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        print("telegram: %s" % resp.status)


def _host_of(url):
    return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")


def _fetch_site_name(url):
    """기사 페이지에서 og:site_name 매체명 추출. 실패 시 None."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=PRESS_FETCH_TIMEOUT) as resp:
            data = resp.read(65536)
    except Exception:
        return None
    head = data[:2048].decode("ascii", errors="ignore").lower()
    enc = "euc-kr" if ("euc-kr" in head or "ms949" in head or "cp949" in head) else "utf-8"
    text = data.decode(enc, errors="replace")
    m = re.search(
        r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)', text, re.I
    ) or re.search(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:site_name["\']', text, re.I
    )
    if not m:
        # 2차: copyright 메타/문구에서 매체명 추출
        # 예: <meta name="Copyright" content="서울타임즈뉴스">
        #     "Copyright ⓒ 메가경제 All rights reserved"
        m = re.search(
            r'<meta[^>]+name=["\']copyright["\'][^>]+content=["\']([^"\']+)', text, re.I
        ) or re.search(
            r'Copyright\s*[@ⓒ©]?\s*([^\s<>][^<>\n]{0,28}?)\s*(?:Corp\.?)?\s*All\s+rights\s+reserved',
            text, re.I,
        )
    if not m:
        return None
    name = html_mod.unescape(m.group(1)).strip().strip('.@ⓒ© ')
    return name[:30] or None


def press_name(url, source="", cache=None):
    """매체명 결정: Google RSS source → PRESS_MAP → 캐시. 미해결이면 None."""
    if source:
        return source
    host = _host_of(url)
    for domain, name in PRESS_MAP.items():
        if host == domain or host.endswith("." + domain):
            return name
    if cache and host in cache and cache[host] != host:
        return cache[host]
    return None  # 미캐시 또는 과거 실패(도메인 그대로 캐시) → 재조회 대상


def resolve_press_names(hits, cache):
    """hits의 매체명 확정. 미등록 도메인은 기사 페이지에서 동적 조회 후 캐시.

    실행당 최대 PRESS_FETCH_MAX건만 신규 조회. 실패 시 도메인명으로 캐시해
    반복 조회를 방지한다 (수동 교정은 PRESS_MAP 또는 state.json press_names).
    """
    budget = PRESS_FETCH_MAX
    resolved = []
    for title, url, pub, source, kw, desc in hits:
        name = press_name(url, source, cache)
        if name is None:
            host = _host_of(url) or "기타"
            if budget > 0:
                budget -= 1
                name = _fetch_site_name(url) or host
                cache[host] = name
            else:
                name = host
        resolved.append((name, title, url, desc))
    return resolved


def blocked_url(url):
    """스포츠/게임 전문 매체 도메인 또는 스포츠 섹션 URL이면 True."""
    host = _host_of(url)
    for d in BLOCK_DOMAINS:
        if host == d or host.endswith("." + d):
            return True
    return any(k in url.lower() for k in BLOCK_URL_KEYWORDS)


# ---------- 메인 ----------

def main():
    if not DRY_RUN and (not BOT_TOKEN or not CHAT_ID):
        print("ERROR: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 미설정")
        sys.exit(1)

    # TEMP DIAG: 봇이 보는 실제 chat id 조회 (채널 chat_id 확인용 — 확인 후 제거)
    try:
        _diag = _http_get("https://api.telegram.org/bot%s/getUpdates" % BOT_TOKEN)
        print("DIAG getUpdates:", _diag[:1500])
    except Exception as _e:
        print("DIAG getUpdates err:", _e)

    state = load_state()
    seen = set(state["seen_urls"])
    seen_titles = set(state.get("seen_titles", []))
    now = datetime.now(KST)

    # 마지막 실행 이후 발행분 커버 (야간 공백 포함). 최소 RECENCY_MINUTES 보장.
    last_run = None
    try:
        last_run = datetime.fromisoformat(state.get("last_run", ""))
    except (ValueError, TypeError):
        pass
    default_cutoff = now - timedelta(minutes=RECENCY_MINUTES)
    cutoff = min(last_run, default_cutoff) if last_run else default_cutoff

    # 마지막 실행과 2시간 이상 공백이면 야간 모아보기 모드
    night_mode = last_run is not None and (now - last_run) > timedelta(hours=2)
    night_range = None
    if night_mode:
        night_range = "%s ~ %s" % (last_run.strftime("%m-%d %H:%M"), now.strftime("%m-%d %H:%M"))

    articles = fetch_all(FETCH_COUNT_NIGHT if night_mode else FETCH_COUNT)
    print("fetched: %d, night_mode: %s" % (len(articles), night_mode))

    first_run = not state.get("initialized", False)
    recent_sigs = _load_recent_sigs(state, now)

    def _mark_seen(key, tkey):
        if key and key not in seen:
            seen.add(key)
            state["seen_urls"].append(key)
        if tkey not in seen_titles:
            seen_titles.add(tkey)
            state.setdefault("seen_titles", []).append(tkey)

    # 1) 중복 URL/제목 제거 + 기간·차단·키워드 필터 → 후보 (발송 전엔 seen 처리 안 함)
    candidates = []
    for title, url, pub, source, desc in articles:
        key = _norm_url(url)
        tkey = re.sub(r"\s+", "", title)[:60]
        if (key and key in seen) or tkey in seen_titles:
            continue
        if (pub and pub < cutoff) or blocked_url(url) or not match_keyword(title):
            _mark_seen(key, tkey)   # 발송 대상 아님 → 즉시 seen 처리
            continue
        candidates.append((title, url, pub, source, match_keyword(title), desc, key, tkey))

    # 2) 유사 기사(같은 보도자료) 묶음 차단
    accepted = []
    run_sigs = []
    for (title, url, pub, source, kw, desc, key, tkey) in candidates:
        toks = _title_tokens(title)
        if len(toks) >= NEAR_DUP_MIN_SHARED and (_is_near_dup(toks, recent_sigs) or _is_near_dup(toks, run_sigs)):
            _mark_seen(key, tkey)   # 같은 사안 → 1건만 남기고 드롭
            continue
        run_sigs.append(toks)
        accepted.append((title, url, pub, source, kw, desc, key, tkey, toks))

    print("hits: %d (candidates: %d)" % (len(accepted), len(candidates)))

    try:
        if first_run:
            # 최초 실행은 기존 기사를 seen 처리만 하고 발송 생략 (과거 기사 폭주 방지)
            print("first run — baseline only, no send")
            for item in accepted:
                _mark_seen(item[6], item[7])
        elif accepted:
            cache = state.setdefault("press_names", {})
            to_send = accepted[:MAX_SEND_PER_RUN]   # 초과분은 seen 처리 안 함 → 다음 run으로 분산
            resolved = resolve_press_names(
                [(t, u, p, s, kw, d) for (t, u, p, s, kw, d, k, tk, to) in to_send], cache
            )
            if night_range:
                try:
                    _post_telegram("야간 모아보기 %s" % night_range)
                except Exception as e:
                    print("header send error: %s" % e)
            sent = 0
            for idx, (name, title, url, desc) in enumerate(resolved):
                key, tkey, toks = to_send[idx][6], to_send[idx][7], to_send[idx][8]
                excerpt = ("\n" + _h(desc[:200]) + ("..." if len(desc) > 200 else "")) if desc else ""
                try:
                    _post_telegram("%s\n<a href=\"%s\">%s</a>%s%s" % (_h(name), url, _h(title), excerpt, (("\n🏷 키워드: " + _h(to_send[idx][4])) if to_send[idx][4] else "")))
                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        print("429 rate limit — stop (%d sent, %d남음 다음 run)" % (sent, len(to_send) - idx))
                        break
                    try:
                        _err_body = e.read().decode("utf-8", "replace")[:300]
                    except Exception:
                        _err_body = "<no body>"
                    print("send error 4xx (skip): %s | %s" % (e, _err_body))
                    _mark_seen(key, tkey)   # 400 등 영구 오류는 재시도 무의미 → seen 처리
                    continue
                except Exception as e:
                    print("send error — stop: %s" % e)
                    break
                # 성공 → seen + 유사판정 시그니처 기록
                _mark_seen(key, tkey)
                state.setdefault("recent_sigs", []).append([now.isoformat(), " ".join(toks)])
                recent_sigs.append(toks)
                sent += 1
                time.sleep(SEND_INTERVAL_SEC)
            print("sent: %d" % sent)
    finally:
        state["initialized"] = True
        save_state(state)


if __name__ == "__main__":
    main()
