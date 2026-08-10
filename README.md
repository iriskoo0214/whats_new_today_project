# 오늘머니 — 오늘의 증시 브리핑

하루 두 번, 각 시장이 문을 닫은 직후에 보유 종목의 가격과 뉴스를 모아 브리핑을 만들고,
피그마 시안에서 뽑아낸 프로토타입에 그대로 꽂는다.

**배포:** https://oneulmoney.vercel.app

| 시각 (KST) | 대상 | 무엇을 담나 |
| --- | --- | --- |
| 오전 7:00 | `--market us` | 밤사이 끝난 미국 증시 마감 + 해외 종목 뉴스 |
| 오후 6:00 | `--market kr` | 그날 끝난 한국 증시 마감 + 국내 종목 뉴스 |

```
보유 종목 (data/portfolio.json)
      ↓
가격    pykrx(국내) · yfinance(해외)
장중    yfinance 5분봉 → 정해진 시각의 시세 (Portfolios 탭 전용)
뉴스    Google News RSS · yfinance Ticker.news
문구    Claude API — 번역 · 카드 요약 · 시간대별 브리핑
      ↓
briefings/YYYY-MM-DD-{us,kr}.md   ← 사람이 읽는 브리핑 (가격표·뉴스 원문·링크)
data/briefing.js                  ← 프로토타입이 읽는 데이터
      ↓
index.html + styles.css + app.js
```

**각 실행은 자기 시장만 갱신하고 반대편은 직전 것을 그대로 남긴다.** 프로토타입의
시장 전환 버튼(요약 타이틀 탭)이 양쪽 다 살아 있어야 하기 때문이다. 그래서 아침 7시
실행 뒤에도 어젯밤 한국 브리핑을 계속 넘겨볼 수 있다.

## 파일 구성

| 파일 | 역할 |
| --- | --- |
| `index.html` | 마크업. 데이터(`briefing.js`)를 먼저 읽고 `app.js`를 실행한다 |
| `styles.css` | 스타일 전부 |
| `app.js` | 렌더링·스와이프·필터 등 화면 동작 |
| `pipeline/` | 브리핑을 만드는 파이썬 (아래 표 참고) |
| `data/briefing.js` | 파이프라인 산출물. 매 실행마다 덮어써진다 |
| `briefings/*.md` | 뉴스 원문과 링크가 남는 기록 |

| 파이프라인 모듈 | 역할 |
| --- | --- |
| `run_daily.py` | 진입점. 아래 모듈을 순서대로 부른다 |
| `portfolio.py` | 보유 종목 로드 |
| `prices.py` | 종가·전일 대비 등락률 |
| `intraday.py` | 장중 5분봉 → 시간대별 슬롯 |
| `news.py` | 종목별 뉴스 수집 |
| `translate.py` | 영문 헤드라인 → 한글 |
| `summarize.py` | 홈 카드 제목·본문 |
| `intraday_summary.py` | 시간대별 브리핑 문구 |
| `brief.py` | 문구 조립과 길이 맞추기, 마크다운 생성 |
| `emit.py` | `briefing.js` / `briefing.json` 출력 |
| `brokers/toss.py` | 토스증권 연동 자리 (미구현) |

## 자동 실행

**GitHub Actions**가 하루 두 번 돌린다 (`.github/workflows/briefing.yml`).
결과를 저장소에 커밋하면 Vercel이 감지해 자동 재배포한다. 맥이 꺼져 있어도 돌아간다.

```
22:00 UTC = 07:00 KST → --market us
09:00 UTC = 18:00 KST → --market kr
```

- **API 키**는 저장소 Settings → Secrets and variables → Actions 의 `ANTHROPIC_API_KEY`
- Actions 탭에서 **Run workflow**로 즉시 실행할 수 있다
- cron은 정시를 보장하지 않는다. 수 분~수십 분 늦게 도는 일이 흔하다

로컬 launchd 스케줄은 Actions로 옮기면서 해제했다. 되돌리려면
`~/Library/LaunchAgents/disabled-notefolio/`의 plist를 원래 자리로 옮기고 `bootstrap` 한다.

## 직접 실행

```bash
python3 -m venv .venv && .venv/bin/pip install -r pipeline/requirements.txt
bash pipeline/setup_key.sh                      # API 키 저장 (~/.config/notefolio/env)

.venv/bin/python pipeline/run_daily.py --market us    # 미국만
.venv/bin/python pipeline/run_daily.py --market kr    # 한국만
.venv/bin/python pipeline/run_daily.py --market all   # 둘 다
.venv/bin/python pipeline/run_daily.py                # auto — 정오 전이면 us, 후면 kr
```

`--summarizer rule`을 붙이면 API를 쓰지 않고 규칙 기반(헤드라인 나열)으로만 만든다.

프로토타입을 로컬에서 보려면 서버가 필요하다. `data/briefing.js`를 `<script src>`로
읽기 때문에 `file://`로 열면 브라우저가 막고, 그때는 `app.js` 안의 예시 데이터로 떨어진다.

```bash
python3 -m http.server 4173
```

## 보유 종목 바꾸기

`data/portfolio.json`의 `holdings`만 고치면 된다.

```json
{ "market": "KR", "ticker": "000660", "name": "SK하이닉스" }
{ "market": "US", "ticker": "MSFT", "name": "마이크로소프트", "en_name": "Microsoft" }
```

- `market` — `"KR"`이면 pykrx, 그 외에는 yfinance
- `ticker` — 국내는 6자리 종목코드, 해외는 야후 심볼
- `name` — 화면 표기 + 뉴스 검색어
- `en_name` — 해외만. 영문 기사가 이 종목 것인지 걸러내는 데 쓴다

## 토스증권 연동 (예정)

`pipeline/brokers/toss.py`의 `fetch_holdings()`만 채우면 된다. `sync()`가 그 결과로
`data/portfolio.json`을 덮어쓰고 나머지 코드는 그대로 둔다.
자격증명은 `TOSS_APP_KEY` / `TOSS_APP_SECRET` / `TOSS_ACCOUNT_NO` 환경변수로 받는다.

## 알아둘 것

**시간대를 시장에 맞춰 나눈 이유.** 오전 7시에는 국내 장이 열리기 전이라 국내 시세가
전 거래일 종가고 뉴스도 7시간치뿐이다. 오후 6시에는 미국 장이 시작도 안 했다.
그래서 각 슬롯이 방금 마감한 시장만 맡는다. 어느 거래일 종가인지는 마크다운의
`기준 거래일` 칸과 `briefing.json`의 `as_of`에 남는다.

**오전 7시는 미국 마감 뒤로 안전하게 떨어져 있다.** 미국 장 마감(현지 16:00)이
서머타임 기간엔 KST 05:00, 표준시 기간엔 KST 06:00이라 어느 계절에도 일봉이 확정된
뒤에 돈다. 6시로 당기면 겨울에 마감과 겹쳐 전일 종가가 잡힐 수 있다.

**시간대별 브리핑은 마감 후에 한 번에 만든다.** 장중에 여러 번 돌 필요 없이 그날
5분봉을 통째로 받아 정해진 시각만 뽑아낸다.

| 시장 | 슬롯 |
| --- | --- |
| 국내 | 9:10AM · 10:30AM · 1:00PM · 마감 |
| 해외 | 11:00PM · 마감 (KST — 한밤중이라 중간 시점을 여러 개 둬도 볼 사람이 없다) |

시각은 `config.INTRADAY_TIMES_KR` / `INTRADAY_TIMES_US`에서 고친다. 30분봉으로는
9:10을 집을 수 없어서 5분봉을 쓰고, 값은 그 봉의 **시가**를 쓴다 — 종가는 5분 뒤
가격이라 '9:10의 주가'로 내걸기에 맞지 않는다.

마지막 슬롯은 공식 종가로 덮어쓴다. yfinance의 장중 마지막 봉이 거래소 종가와
어긋나서(국내는 15:30 마감인데 14:30 봉이 마지막인 경우가 있다) 그대로 두면 같은
화면에서 카드와 슬롯 가격이 달라진다.

**슬롯은 언제나 장이 끝난 거래일에서 뽑는다.** 손으로 장중에 돌리면 오늘 봉이 반쪽만
있어서 9:10과 10:30만 나오고 1:00PM·마감이 빈다. 그런 날은 건너뛰고 직전 거래일을
쓴다. 그러면 슬롯의 거래일이 카드 시세(오늘)와 달라지므로, 등락률 기준선을 그 날의
전 거래일 종가로 다시 잡고 슬롯마다 `date`를 실어 보내 화면이 맞는 날짜를 찍게 한다.

**Portfolios 탭의 색은 그 화면이 보여주는 거래일의 마감 방향으로 고정된다.** 시점마다
뒤집으면 넘기는 동안 오늘 오른 종목인지 내린 종목인지가 읽히지 않는다. 다만 숫자 옆
▲▼와 % 색은 그 시점 값을 따라간다(`data-slot-trend`) — 화면 색에 맞춰 뒤집으면
+0.80%에 ▼가 붙는 거짓말이 된다.

**LLM이 없는 사실을 쓰지 못하게 막아뒀다.** 헤드라인에 근거가 없으면 수급 주체나
"차익실현 매물" 같은 표현을 쓰지 못하고, 헤드라인 발행 시각보다 나중 기사로 앞 시점을
설명하지 못한다. 그래도 완전히 없앨 수는 없으니, 판단은 마크다운의 원문 헤드라인과
링크로 확인하는 편이 안전하다.

**API가 실패해도 브리핑은 나간다.** 키가 없거나 라이브러리가 깨지면 규칙 기반
(헤드라인 나열)으로 물러난다. 문구 품질만 떨어지고 파이프라인은 죽지 않는다.

**카드 길이는 글자 수가 아니라 폭으로 맞춘다.** 한글은 약 12.8px, 영문·숫자는 7.6px라
같은 글자 수여도 구성에 따라 넘치거나 남는다. 한글 한 글자를 1.0으로 환산해
제목은 한 줄(25), 본문은 세 줄(75) 분량을 예산으로 쓴다.

**해외 뉴스는 두 소스를 합친다.** yfinance만 쓰면 무관한 기사(NVDA 뉴스에 다른 회사
배당 기사)가 섞여 들어와서, Google News RSS를 함께 보고 종목명·티커가 제목에 없는
기사는 버린다.

**번역·요약은 Claude API를 쓴다.** 무료 구글 웹 번역은 고유명사를 영문으로 남겨서
카드에 영문이 섞인다. 키가 없으면 구글 → 원문 순으로 물러난다.

**모바일에서는 가짜 상태바와 홈바를 감춘다.** 진짜 폰에는 OS가 이미 그려주기 때문이다.
그만큼(44+34px) 프레임을 줄여 화면을 회수한다. 데스크톱에서 폰 껍데기를 씌워 볼 때는
시안 그대로 812px에 상태바·홈바가 나온다.

**브라우저에서 좌우 여백이 남는 건 주소창 때문이다.** 사파리 UI가 세로를 200px 넘게
먹어서 비율을 지키려면 가로가 줄어든다. 홈 화면에 추가해 전체 화면으로 열면 꽉 찬다.
