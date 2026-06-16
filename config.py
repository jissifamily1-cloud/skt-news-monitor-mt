# -*- coding: utf-8 -*-
"""특이뉴스 모니터링(머투 제공) 설정.

키워드 추가/삭제는 이 파일만 수정하면 된다.
GitHub UI에서 직접 한 줄씩 편집 권장 (paste 자동화로 큰 변경 금지).
"""

# 뉴스 검색 쿼리 겸 매칭 키워드 — 제목에 하나라도 있으면 발송 (리스크 필터 없음)
KEYWORDS = [
    # ── 이통사 ──
    "이동통신",
    "통신3사",
    "SKT",
    "KT",
    "LG유플러스",
    "알뜰폰",
    "통신요금",
    "정재헌",      # SKT 대표
    "박윤영",      # KT 대표
    "홍범식",      # LG유플러스 대표
    # ── AI ──
    "인공지능",
    "생성형 AI",
    "오픈AI",
    "OpenAI",
    "앤스로픽",
    "엔비디아",
    "젠슨 황",
    "HBM",
    "SK하이닉스",
    "데이터센터",
    "AI 에이전트",
    "소버린 AI",
    # ── 주요산업 ──
    "반도체",       # "AI 반도체"는 부분일치로 자동 포함
    "이차전지",
    "배터리",
    "전기차",
    "디스플레이",
    "로봇",
    "휴머노이드",
    "자율주행",
    "바이오",
    "양자컴퓨터",
]

# 토픽 제외 — 제목에 하나라도 있으면 발송 안 함 (야구/게임 기사 차단용)
BLOCK_KEYWORDS = [
    # 야구 일반
    "야구", "KBO", "프로야구", "위즈", "시범경기", "퓨처스", "스프링캠프",
    # 경기 용어
    "홈런", "타자", "투수", "포수", "불펜", "타선", "타점", "타율",
    "삼진", "호투", "등판", "끝내기", "완봉", "완투", "마운드", "이닝",
    "선발승", "구원승", "도루",
    # 야구 타격/경기 용어 (2루타·난타전 등은 위즈 없이도 출현)
    "1루타", "2루타", "3루타", "난타전", "재역전", "역전극",
    "실점", "연장전", "9회", "8회", "7회",  # 이닝 표기는 이미 있으나 숫자형 보완
    # KBO 구단 별칭 (KT 위즈 상대팀)
    "베어스", "자이언츠", "이글스", "히어로즈", "다이노스", "랜더스",
    "라이온즈", "타이거즈", "NC다이노스", "위즈파크",
    # e스포츠 (KT 롤스터 기사 차단)
    "LCK", "롤드컵", "리그오브레전드", "롤스터",
    "완파",   # 3대0 완파 등 스포츠 완승 표현
    "젠지",   # Gen.G 이스포츠 팀
    "페이커", "제우스", "케리아",  # T1 선수명 (롤 기사 오탐)
    "세트승", "세트패",  # 이스포츠 세트 결과
]

# 스포츠/게임 전문 매체 — 통신업 기사를 안 쓰므로 도메인 통째 차단
BLOCK_DOMAINS = [
    "mydaily.co.kr",       # 마이데일리
    "spotvnews.co.kr",     # SPOTV뉴스
    "osen.co.kr",          # OSEN
    "xportsnews.com",      # 엑스포츠뉴스
    "sportschosun.com",    # 스포츠조선
    "starnewskorea.com",   # 스타뉴스
    "mksports.co.kr",      # MK스포츠
    "sportsworldi.com",    # 스포츠월드
    "sportsseoul.com",     # 스포츠서울
    "isplus.com",          # 일간스포츠
    "sportalkorea.com",    # 스포탈코리아
    "interfootball.co.kr", # 인터풋볼
    "stnsports.co.kr",     # STN스포츠
    "mhnse.com",           # MHN스포츠
    "sportsq.co.kr",       # 스포츠Q
    "gamefocus.co.kr",     # 게임포커스 (e스포츠)
    "maniareport.com",     # 마니아리포트 (스포츠)
    "stoo.com",            # 스포츠투데이
    "fomos.kr",            # 포모스 (e스포츠)
    "inven.co.kr",         # 인벤 (게임)
]

# URL에 포함되면 차단 — 종합지 스포츠/게임 섹션 기사까지 커버
BLOCK_URL_KEYWORDS = [
    "/sports/",
    "/baseball/",
    "/esports/",
    "/game/",
    "/lck/",
    "/kbo/",
    "/lol/",
    "sports.",
]

# 오탐 방지 — 텍스트에서 제거 후 매칭 (좁은 표현만 추가할 것)
EXCLUDED_WORDS = [
    # 동명이인 오탐 방지 (성우 정재헌) — 제거되면 인물 매칭 자체가 안 됨
    "성우 정재헌",
    "정재헌 성우",
    # KT 위즈 감독/코치 이름 — 야구 기사에만 등장하는 특정 인물
    "고동빈 감독",
    "감독 고동빈",
]

# 짧은 영문 키워드는 영문자 경계 매칭 적용 대상
# (?<![A-Za-z])KT(?![A-Za-z]) — "SKT" 안의 KT, "마켓컬리"의 KT 등 오탐 방지.
# 한글이 바로 붙는 "KT가"·"SKT는"은 정상 매칭됨 (\b 방식의 버그 수정)
WORD_BOUNDARY_KEYWORDS = {"SKT", "KT", "HBM", "OpenAI"}

# 발행 후 이 시간(분) 이내 기사만 대상 (오래된 기사 재발송 방지 2중 장치)
RECENCY_MINUTES = 120

# 쿼리당 가져올 기사 수
FETCH_COUNT = 30

# 야간 모아보기(06시 첫 실행) 때 쿼리당 가져올 기사 수
FETCH_COUNT_NIGHT = 100

# state.json에 보관할 최대 URL 수
MAX_SEEN_URLS = 3000

# 발송 제어 (텔레그램 429 Too Many Requests 방지)
MAX_SEND_PER_RUN = 20      # run당 최대 발송 건수 (초과분은 다음 run으로 분산)
SEND_INTERVAL_SEC = 2.0    # 메시지 간 간격(초) — 텔레그램 그룹 분당 한도 회피

# 유사 기사(같은 보도자료를 여러 매체가 받아쓴 경우) 묶음 차단
# 제목에서 키워드·일반어·숫자를 뺀 "고유 토큰"을 이 개수 이상 공유하면 같은 사안 → 1건만 발송.
# (한국어 헤드라인은 조사 변형이 심해 Jaccard 비율보다 공유어 개수가 안정적)
NEAR_DUP_MIN_SHARED = 2    # 값을 1로 낮추면 더 공격적으로 묶음(무관기사 오병합 위험↑)
NEAR_DUP_HOURS = 6         # 유사 판정용 제목 시그니처 보관 시간
NEAR_DUP_MAX = 800         # 보관 시그니처 최대 개수

# PRESS_MAP에 없는 도메인의 매체명 동적 조회 (기사 페이지 og:site_name)
PRESS_FETCH_MAX = 10      # 실행당 신규 도메인 조회 상한
PRESS_FETCH_TIMEOUT = 8   # 조회 타임아웃(초)

# 기사 URL 도메인 → 매체명 (네이버 API는 매체명을 안 주므로 도메인으로 추정)
# 여기 없는 도메인은 기사 페이지 og:site_name을 1회 조회해 state.json에 캐시
PRESS_MAP = {
    "it.chosun.com": "IT조선",
    "yna.co.kr": "연합뉴스",
    "news1.kr": "뉴스1",
    "newsis.com": "뉴시스",
    "biz.chosun.com": "조선비즈",
    "chosun.com": "조선일보",
    "donga.com": "동아일보",
    "joongang.co.kr": "중앙일보",
    "hani.co.kr": "한겨레",
    "khan.co.kr": "경향신문",
    "hankookilbo.com": "한국일보",
    "kmib.co.kr": "국민일보",
    "segye.com": "세계일보",
    "munhwa.com": "문화일보",
    "seoul.co.kr": "서울신문",
    "mk.co.kr": "매일경제",
    "hankyung.com": "한국경제",
    "sedaily.com": "서울경제",
    "fnnews.com": "파이낸셜뉴스",
    "mt.co.kr": "머니투데이",
    "edaily.co.kr": "이데일리",
    "asiae.co.kr": "아시아경제",
    "heraldcorp.com": "헤럴드경제",
    "etnews.com": "전자신문",
    "zdnet.co.kr": "지디넷코리아",
    "ddaily.co.kr": "디지털데일리",
    "dt.co.kr": "디지털타임스",
    "inews24.com": "아이뉴스24",
    "bloter.net": "블로터",
    "kbs.co.kr": "KBS",
    "imbc.com": "MBC",
    "sbs.co.kr": "SBS",
    "jtbc.co.kr": "JTBC",
    "tvchosun.com": "TV조선",
    "ichannela.com": "채널A",
    "mbn.co.kr": "MBN",
    "ytn.co.kr": "YTN",
    "yonhapnewstv.co.kr": "연합뉴스TV",
    "nocutnews.co.kr": "노컷뉴스",
    "ohmynews.com": "오마이뉴스",
    "mediatoday.co.kr": "미디어오늘",
    "dailian.co.kr": "데일리안",
    "kukinews.com": "쿠키뉴스",
    "ajunews.com": "아주경제",
    "businesspost.co.kr": "비즈니스포스트",
    "newdaily.co.kr": "뉴데일리",
    "pressian.com": "프레시안",
    "mtn.co.kr": "MTN",
    "epnc.co.kr": "테크월드뉴스",
    "digitaltoday.co.kr": "디지털투데이",
    "ebn.co.kr": "EBN",
    "techm.kr": "테크M",
    "asiatoday.co.kr": "아시아투데이",
    "newspim.com": "뉴스핌",
    "etoday.co.kr": "이투데이",
    "newstomato.com": "뉴스토마토",
    "newsway.co.kr": "뉴스웨이",
    "econovill.com": "이코노믹리뷰",
    "g-enews.com": "글로벌이코노믹",
    "shinailbo.co.kr": "신아일보",
    "polinews.co.kr": "폴리뉴스",
    "popcornnews.net": "팝콘뉴스",
    "dailypop.kr": "데일리팝",
    "metroseoul.co.kr": "메트로신문",
    "viva100.com": "브릿지경제",
    "ceoscoredaily.com": "CEO스코어데일리",
    "theguru.co.kr": "더구루",
    "enewstoday.co.kr": "이뉴스투데이",
    "dnews.co.kr": "대한경제",
    "datanet.co.kr": "데이터넷",
    "byline.network": "바이라인네트워크",
    "thelec.kr": "디일렉",
    "wowtv.co.kr": "한국경제TV",
    "sisajournal.com": "시사저널",
    "sisajournal-e.com": "시사저널e",
    "ilyo.co.kr": "일요신문",
    "joseilbo.com": "조세일보",
    "ekn.kr": "에너지경제",
    "businesskorea.co.kr": "비즈니스코리아",
    "koreaherald.com": "코리아헤럴드",
    "koreatimes.co.kr": "코리아타임스",
    "seoulfn.com": "서울파이낸스",
    "paxetv.com": "팍스경제TV",
    "m-economynews.com": "M이코노미뉴스",
    "dealsitetv.com": "딜사이트TV",
    "megaeconomy.co.kr": "메가경제",
    "seoultimes.news": "서울타임즈뉴스",
    "huffingtonpost.kr": "허프포스트코리아",
    "weekly.hankooki.com": "주간한국",
    "chukkyung.co.kr": "축산경제신문",
    "mediapen.com": "미디어펜",
    "delighti.co.kr": "딜라이트닷넷",
}
