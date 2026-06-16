# 머투 제공

# mt-news-monitor — 특이뉴스 모니터링(머투 제공)

이통사·AI·주요산업 키워드 기사를 06~22시 KST 주기 실행으로 탐지해 텔레그램으로 발송하는 자동화 시스템. 기존 `특이뉴스 모니터링` 채널과 **푸시 양식·주기 동일**, 키워드만 교체한 별도 채널.

## 키워드 (config.py)

| 그룹 | 키워드 |
|---|---|
| 이통사 | 이동통신 · 통신3사 · SKT · KT · LG유플러스 · 알뜰폰 · 통신요금 · 정재헌(SKT) · 박윤영(KT) · 홍범식(LGU+) |
| AI | 인공지능 · 생성형 AI · 오픈AI · OpenAI · 앤스로픽 · 엔비디아 · 젠슨 황 · HBM · SK하이닉스 · 데이터센터 · AI 에이전트 · 소버린 AI |
| 주요산업 | 반도체 · 이차전지 · 배터리 · 전기차 · 디스플레이 · 로봇 · 휴머노이드 · 자율주행 · 바이오 · 양자컴퓨터 |

> "AI 반도체"는 `반도체`가 부분일치로 자동 커버. 산업 일반어(반도체·배터리·전기차 등)가 많아 발송량이 큼 — 폭주 시 광범위어부터 정리.

## 구조

| 항목 | 값 |
|---|---|
| 소스 | 네이버 뉴스 검색 Open API (키 없으면 Google News RSS 자동 fallback) |
| 매칭 | 제목에 **키워드** 중 하나라도 있으면 발송. 단 BLOCK_KEYWORDS(야구 등)가 제목에 있으면 제외 |
| 매체명 | Google RSS source → PRESS_MAP 도메인 → 기사 페이지 og:site_name 동적 조회(state.json `press_names` 캐시) |
| 중복 방지 | `state.json` seen_urls + 최근 120분 발행 기사만 + 유사 제목 묶음 차단 |
| 실행 | GitHub Actions (`workflow_dispatch`) ← cron-job.org 트리거 |
| 주기 | `*/2 6-21 * * *` KST (06:00~21:58, 하루 480회) |
| 발송 | 텔레그램 @skt_personnel_bot → 머투 제공 채널 |

## 파일

- `monitor.py` — 수집·매칭·발송·상태관리 전부 (기존 채널과 동일)
- `config.py` — 키워드 설정 (유지보수 시 이 파일만 수정)
- `state.json` — 발송 이력·매체명 캐시 (자동 갱신, `initialized:false`로 시작 → 최초 실행은 baseline만)
- `.github/workflows/cron.yml` — Actions 워크플로우 (`cron.yml`을 이 경로로 업로드)

## 셋업 순서

### 1. 텔레그램 채널 생성
1. 새 채널 생성 (예: "특이뉴스 머투")
2. `@skt_personnel_bot`을 관리자로 추가 ("메시지 게시" 권한 필수) — 기존 봇 재사용 가능(채널별 chat_id만 다름)
3. chat_id 확인: web.telegram.org/k/ 에서 채널 클릭 → URL의 음수 숫자 (예: `-100xxxxxxxxxx`)

### 2. 네이버 API 키
- 이 채널 전용 키: Client ID `q88Qhq6zO86MXUxkWBfP` / Client Secret `hr1qpbSlcx`
- GitHub Secret으로만 등록(코드 하드코딩 금지). 무료 일 25,000회 한도 내.

### 3. GitHub repo 생성
1. **public** repo `skt-news-monitor-mt` 생성 (public이어야 Actions 무료 무제한)
2. 파일 업로드: `monitor.py`, `config.py`, `state.json`, 그리고 `cron.yml`은 `.github/workflows/cron.yml` 경로로
3. Settings → Secrets and variables → Actions → 등록:
   - `TELEGRAM_BOT_TOKEN` (기존 봇 토큰 재사용)
   - `TELEGRAM_CHAT_ID` (1에서 확인한 새 채널 음수 ID)
   - `NAVER_CLIENT_ID` = `q88Qhq6zO86MXUxkWBfP`
   - `NAVER_CLIENT_SECRET` = `hr1qpbSlcx`
4. Settings → Actions → General → Workflow permissions → **Read and write permissions** 체크 (state.json commit용)

### 4. 동작 확인
1. Actions 탭 → mt-news-monitor → Run workflow (수동 실행)
2. 최초 실행은 기존 기사를 baseline 처리만 하고 발송하지 않음 (`initialized:false`)
3. 한 번 더 실행해 신규 기사 매칭 여부 확인

### 5. cron-job.org 등록
1. https://console.cron-job.org/jobs → Create cronjob
2. URL: `https://api.github.com/repos/{계정}/skt-news-monitor-mt/actions/workflows/cron.yml/dispatches`
3. Method: POST, Body: `{"ref":"main"}`
4. Headers:
   - `Authorization: Bearer {GitHub PAT}` (기존 시스템과 동일 PAT 사용 가능, repo+workflow 권한)
   - `Accept: application/vnd.github+json`
   - `Content-Type: application/json`
5. Schedule: `*/2 6-21 * * *` (KST 타임존 확인)

## 유지보수

- **키워드 추가/삭제**: `config.py`의 `KEYWORDS` — GitHub UI에서 직접 한 줄씩 편집 (paste 자동화로 큰 변경 금지)
- **발송 폭주 시**: `반도체`·`배터리`·`전기차`·`인공지능` 같은 광범위 키워드부터 제거
- **야구 등 토픽 제외**: `config.py`의 `BLOCK_KEYWORDS` — 제목에 있으면 무조건 발송 제외
- **매체명 오표기 시**: `config.py`의 `PRESS_MAP`에 도메인 추가 또는 `state.json`의 `press_names` 캐시 수정
- **오탐 제거**: `EXCLUDED_WORDS`에 좁은 표현만 추가
- **키워드 변경 후 기존 기사 재평가**: `state.json`을 `{"seen_urls": [], "last_run": "", "initialized": false}`로 reset
- **"chat not found"**: 봇이 채널 관리자인지, chat_id가 `-100`으로 시작하는지 확인

## 비용

전부 무료: public repo Actions 무제한 + cron-job.org 무료 + 네이버 API 무료 한도 내 + 텔레그램 무료.
