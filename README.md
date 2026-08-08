# 오늘머니 종목 뉴스 데일리 브리핑

하루 두 번, 각 시장이 문을 닫은 직후에 보유 종목의 가격과 뉴스를 모아 브리핑을 만들고,
피그마에서 뽑아낸 프로토타입(`index.html`)에 그대로 꽂는다.

| 시각 (KST) | 대상 | 무엇을 담나 |
| --- | --- | --- |
| 오전 7:00 | `--market us` | 밤사이 끝난 미국 증시 마감 + 해외 종목 뉴스 |
| 오후 6:00 | `--market kr` | 그날 끝난 한국 증시 마감 + 국내 종목 뉴스 |

```
포트폴리오(data/portfolio.json)
      ↓
가격  pykrx(국내) · yfinance(해외)
뉴스  Google News RSS when:1d(국내) · yfinance Ticker.news + 한글 번역(해외)
      ↓
briefings/YYYY-MM-DD-{us,kr}.md   ← 사람이 읽는 브리핑 (가격표·종목별 뉴스·핵심 한 줄·오늘의 액션)
data/briefing.js / .json          ← 프로토타입이 읽는 데이터 (두 시장이 함께 들어 있다)
      ↓
index.html (Home 탭 카드 · Portfolios 탭 시세)
```

**각 실행은 자기 시장만 갱신하고 반대편은 직전 것을 그대로 남긴다.** 프로토타입의
시장 전환 버튼(요약 타이틀 탭)이 양쪽 다 살아 있어야 하기 때문이다. 그래서 아침 7시
실행 뒤에도 어젯밤 한국 브리핑을 계속 넘겨볼 수 있다.

## 실행

```bash
.venv/bin/python pipeline/run_daily.py --market us   # 미국만
.venv/bin/python pipeline/run_daily.py --market kr   # 한국만
.venv/bin/python pipeline/run_daily.py --market all  # 둘 다
.venv/bin/python pipeline/run_daily.py               # auto — 정오 전이면 us, 후면 kr
```

프로토타입 보기 — `data/briefing.js`를 `<script src>`로 읽기 때문에 로컬 서버가 필요하다.
(`file://`로 열면 브라우저가 차단하고, 이때는 `index.html` 안의 예시 데이터로 자동으로 떨어진다.)

```bash
python3 -m http.server 4173
```

## 보유 종목 바꾸기

`data/portfolio.json`의 `holdings`만 고치면 된다. 파이프라인·프로토타입은 손댈 필요 없다.

```json
{ "market": "KR", "ticker": "000660", "name": "SK하이닉스" }
```

- `market` — `"KR"`이면 pykrx, 그 외에는 yfinance로 조회
- `ticker` — 국내는 6자리 종목코드, 해외는 야후 심볼
- `name` — 화면 표기 + 국내 뉴스 검색어로 쓰인다

## 토스증권 연동 (예정)

`pipeline/brokers/toss.py`의 `fetch_holdings()`만 채우면 된다.
`sync()`가 그 결과로 `data/portfolio.json`을 덮어쓰고, 나머지 코드는 그대로 둔다.
자격증명은 환경변수 `TOSS_APP_KEY` / `TOSS_APP_SECRET` / `TOSS_ACCOUNT_NO`로 받는다.

## 스케줄

`~/Library/LaunchAgents/`에 두 개가 등록돼 있다.

| 에이전트 | 시각 | 인자 |
| --- | --- | --- |
| `com.notefolio.dailybrief.morning` | 07:00 | `us` |
| `com.notefolio.dailybrief.evening` | 18:00 | `kr` |

```bash
launchctl list | grep notefolio                                        # 등록 확인
launchctl kickstart -k gui/$(id -u)/com.notefolio.dailybrief.morning   # 지금 한 번 실행
launchctl bootout   gui/$(id -u)/com.notefolio.dailybrief.morning      # 중지(해제)
launchctl bootout   gui/$(id -u)/com.notefolio.dailybrief.evening
```

시각을 바꾸려면 `pipeline/com.notefolio.dailybrief.*.plist`의 `StartCalendarInterval`을 고친 뒤
`~/Library/LaunchAgents/`로 복사하고 `bootout` → `bootstrap`을 다시 한다.

로그는 `logs/YYYY-MM.log`에 두 슬롯이 함께 쌓인다. 해당 시각에 맥이 꺼져 있으면 그 실행은
건너뛰고, 잠들어 있었다면 깨어난 직후에 돌아간다.

## 알아둘 것

- **시간대를 시장에 맞춰 나눈 이유.** 오전 7시에는 국내 장이 열리기 전이라 국내 시세가
  전 거래일 종가고 뉴스도 7시간치뿐이다. 오후 6시에는 미국 장이 시작도 안 했다.
  그래서 각 슬롯이 방금 마감한 시장만 맡는다.
  어느 거래일 종가인지는 마크다운의 `기준 거래일` 칸과 `briefing.json`의 `as_of`에 남는다.
- **오전 7시는 미국 마감 뒤로 안전하게 떨어져 있다.** 미국 장 마감(현지 16:00)이
  서머타임 기간엔 KST 05:00, 표준시(11월~3월 초) 기간엔 KST 06:00이라 어느 계절에도
  일봉이 확정된 뒤에 돈다. 6시로 당기면 겨울에 마감과 겹쳐 전일 종가가 잡힐 수 있다.
- **뉴스가 3건에 못 미치면 최근 24시간에서 채운다.** 그렇게 채운 항목은 마크다운에
  `(24시간 내)`로 표시된다. `pipeline/config.py`의 `NEWS_FALLBACK_24H`로 끌 수 있다.
- **카드 본문은 가격 문장이 앞에 온다.** 프로토타입 카드가 본문을 3줄에서 잘라내기 때문에
  (`-webkit-line-clamp:3`) 숫자를 먼저 보여주는 편이 안전하다. 뉴스 원문·출처·링크는 마크다운에 전부 있다.
- **Portfolios 탭의 시간대별 브리핑은 '마감' 하나뿐이다.** 하루 한 번 도는 파이프라인은
  종가만 알기 때문에 장중 시간대를 지어내지 않는다. 예시 데이터로 볼 때만 4개 시간대가 나온다.
- **해외 헤드라인 번역은 무료 구글 웹 엔드포인트를 쓴다.** 비공식 경로라 막히면 원문이 그대로 나온다.
  `DEEPL_API_KEY`를 환경변수에 넣어두면 DeepL을 먼저 쓴다.
