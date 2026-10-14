"""경로와 상수를 한 곳에 모아둔다. 다른 모듈은 여기만 보고 파일 위치를 안다."""

import os
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent


# 키 파일은 프로젝트 밖에 둔다.
# 미리보기용 로컬 서버가 프로젝트 폴더를 통째로 서빙하기 때문에, 여기에 키를 두면
# http://localhost:4173/.env 로 그대로 새어나간다.
KEY_FILE = Path.home() / ".config" / "notefolio" / "env"


def _read_env_file(path: Path) -> None:
    """KEY=VALUE 파일을 환경변수로 올린다. 이미 있는 값은 덮어쓰지 않는다."""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # 값이 빈 줄은 건너뛴다 — 앞선 시도가 남긴 'KEY=' 한 줄이
        # 뒤에 오는 진짜 값을 가리는 일이 있었다.
        if key and value and key not in os.environ:
            os.environ[key] = value


def _load_secrets() -> None:
    """비밀값을 환경변수로 올린다.

    launchd는 로그인 셸 환경을 물려받지 않는다. 터미널에서 export 해둔 키는
    새벽 실행에 닿지 않으므로, 파일 한 곳에 두고 수동 실행과 자동 실행이
    같이 읽게 한다.
    """
    if KEY_FILE.exists():
        _read_env_file(KEY_FILE)

    # 프로젝트 안의 .env는 웹으로 새어나갈 수 있어 쓰지 않는 것이 맞다.
    # 이미 만들어 둔 사람을 위해 읽어는 주되, 옮기라고 알린다.
    stray = ROOT / ".env"
    if stray.exists():
        _read_env_file(stray)
        print("  [경고] {}는 로컬 서버로 노출될 수 있습니다. {}로 옮기세요."
              .format(stray, KEY_FILE))


_load_secrets()

DATA_DIR      = ROOT / "data"
BRIEFINGS_DIR = ROOT / "briefings"
LOG_DIR       = ROOT / "logs"

PORTFOLIO_JSON = DATA_DIR / "portfolio.json"
BRIEFING_JSON  = DATA_DIR / "briefing.json"
BRIEFING_JS    = DATA_DIR / "briefing.js"   # 프로토타입이 <script>로 읽는 파일

KST = ZoneInfo("Asia/Seoul")

# 종목당 가져올 뉴스 개수
NEWS_PER_STOCK = 3

# "KST 기준 오늘 발행분"이 3건에 못 미치면 최근 24시간 안에서 채운다.
# (오전 7시 실행 시 국내 뉴스는 7시간치뿐이라 대부분 비게 된다)
NEWS_FALLBACK_24H = True

# 영문 헤드라인 한글 번역 사용 여부
TRANSLATE_HEADLINES = True

# 번역에 쓰는 모델. 가격을 확인하신 Sonnet 5로 잡아둔다 — 바꾸려면 여기만 고치면 된다.
# ANTHROPIC_API_KEY가 없으면 무료 구글 웹 번역으로 자동으로 물러난다.
TRANSLATE_MODEL = "claude-sonnet-5"
TRANSLATE_MAX_TOKENS = 4000

# 카드 문구 요약(제목 꼬리 + 원인절). 키가 없으면 규칙 기반으로 자동 폴백한다.
SUMMARY_MODEL = "claude-sonnet-5"
SUMMARY_MAX_TOKENS = 8000   # 종목이 늘어도 잘리지 않게 여유를 둔다

# ---- 시장 전체 헤드라인 / "OO장 어땠지" 3줄 요약 (Home 탭 전용) ----
# 종목 뉴스(NEWS_PER_STOCK)는 보유종목 이름으로만 검색해서 "코스피 6700선
# 붕괴" 같은 지수·유가·금리 이슈를 못 잡는다. 여기는 종목과 무관하게 시장
# 전체를 검색어로 찾는다.
#
# 마감 브리핑(run_daily.py, --slots-only 아닐 때)에서만 부른다. 장중 실행은
# emit._merge_slots가 카드의 slots만 갈아끼우고 이 필드는 건드리지 않는다.
#
# 3줄 요약은 번호마다 담당 영역이 정해져 있다(market_summary.py). 재료도 번호별로
# 따로 모은다 — 한 통에 섞으면 기사가 제일 많은 지수 시황이 재료를 다 먹어서,
# 수급·업종·환율 같은 칸이 비거나 제목을 되풀이하게 된다(2026-10-14 "6600선 턱걸이"
# 중복). (key, 화면에 안 나가는 영역 이름, 검색어들) 순서가 곧 1·2·3번이다.
MARKET_SUMMARY_SLOTS = {
    "kr": [
        ("supply",   "수급",        ["코스피 마감", "외국인 순매수 코스피", "코스닥 마감"]),
        ("sector",   "업종·주도주", ["업종별 등락 마감", "마감시황 급등 업종", "반도체주 마감"]),
        ("external", "대외 변수",   ["원달러 환율 마감", "뉴욕증시 마감", "미국 CPI 증시"]),
    ],
    # "국제유가"만 검색하면 한국 구글뉴스는 '주유소 기름값 18주 하락·유류세·고속도로
    # 통행료' 같은 국내 생활뉴스를 잔뜩 끌어온다 — 미국 시장요약이 한국 이야기가 됐던
    # 원인(2026-09-19). 유가·금리도 뉴욕 시장 맥락으로 좁혀서 찾는다.
    "us": [
        ("sector",   "업종·주도주",  ["뉴욕증시 마감 업종", "뉴욕증시 기술주 마감", "뉴욕증시 급등 종목"]),
        ("macro",    "금리·유가·달러", ["美 국채금리 뉴욕증시", "뉴욕유가 WTI 마감", "달러인덱스 뉴욕"]),
        ("event",    "이벤트·일정",  ["연준 금리 뉴욕증시", "美 실적 발표 뉴욕증시", "미국 경제지표 발표 증시"]),
    ],
}
# 재료로 쓸 기사의 발행 시각 — 요약하는 장의 개장 3시간 전 ~ 발송 기준 시각(KST).
# 홈 요약은 "오후 6시 기준 국내 시황", "오전 7시 기준 미국 시황"이다. 그래서 끝은
# 실행 시각이 아니라 발송 기준 시각(cutoff, 한국 시간)으로 고정한다 — 늦게 다시 돌려도
# 그 시각까지 나온 기사로만 만들어 정시 발송본과 같은 범위가 된다. 예전엔 "최근 24시간"
# 으로 모아서 한국 마감 뒤 21:30에 나온 美 CPI 결과가 그날 코스피 하락의 원인처럼
# 쓰였다(2026-10-14). 개장 전 3시간은 전날 밤 뉴욕 마감·개장 전 시황처럼 그날 장에
# 실제로 영향을 준 기사를 담으려고 열어둔다.
MARKET_SESSION = {
    "kr": {"tz": "Asia/Seoul",       "open": (9, 0),  "close": (15, 30), "cutoff_kst": (18, 0)},
    "us": {"tz": "America/New_York", "open": (9, 30), "close": (16, 0),  "cutoff_kst": (7, 0)},
}
MARKET_SESSION_LEAD_HOURS = 3
# 시장별로 재료에서 뺄 헤드라인의 단어. 다른 나라 시장 얘기나 국내 생활물가가 섞이면
# LLM이 그걸 그대로 요약해 버린다(위 참고). 국내 쪽은 뉴욕 시황이 원인으로 자주
# 언급되므로(예: "뉴욕 훈풍에 코스피 상승") 빼지 않는다.
MARKET_NEWS_EXCLUDE = {
    "us": ["코스피", "코스닥", "주유소", "기름값", "유류세", "통행료", "최고가격제",
           "삼성전자", "SK하이닉스", "삼전", "닉스", "원·달러", "원/달러"],
    # 구글뉴스 "코스피 마감" 검색에 도박 스팸(바카라·토토 광고성 글)이 섞여 온다
    "kr": ["바카라", "토토", "카지노", "배팅", "먹튀"],
}
# 요약 결과에 이 단어가 나오면 그 시장 요약을 버린다 — 재료를 걸렀는데도 LLM이
# 엉뚱한 나라 이야기를 쓴 경우의 마지막 안전망(market_summary.summarize의 forbid).
MARKET_SUMMARY_FORBID = {
    "us": ["코스피", "코스닥", "삼성전자", "SK하이닉스", "삼전", "닉스", "유류세", "통행료", "주유소"],
    "kr": [],
}
MARKET_NEWS_PER_QUERY = 6    # 검색어 하나에서 가져오는 최신 기사 수
MARKET_NEWS_PER_SLOT = 8     # 번호 하나에 LLM에게 주는 헤드라인 수(그대로 불릿이 되는 게 아니라 재료)
MARKET_BULLET_MAX_LEN = 28   # 불릿 최대 글자 수(공백 포함) — 홈 카드 폭(15px)에서 한 줄
MARKET_BULLET_RETRIES = 2    # 넘친 불릿만 다시 쓰게 하는 횟수

MARKET_SUMMARY_MODEL = "claude-sonnet-5"
MARKET_SUMMARY_MAX_TOKENS = 2000

# ---- 시간대별 브리핑 (Portfolios 탭 전용) ----
# 홈 탭은 하루 두 번 마감 브리핑만 쓰고, 장중 흐름은 여기서만 보여준다.
INTRADAY_ENABLED = True
# 시간대별 브리핑을 찍을 시점. (시, 분) 모두 KST 기준이고, "마감"은 언제나
# 마지막에 자동으로 붙으므로 여기 적지 않는다.
#
# 국내는 장중 네 토막(개장 직후·오전·오후·마감)으로 나눈다.
# 해외는 KST 한밤중에 열려서 중간 시점을 여러 개 둬도 볼 사람이 없다.
# 밤 11시(서머타임 기준 개장 30분 뒤) 하나와 마감이면 충분하다.
INTRADAY_TIMES_KR = [(9, 10), (10, 30), (13, 0)]
INTRADAY_TIMES_US = [(23, 0)]

# 봉 간격. 위 시점을 정확히 집으려면 5분봉이어야 한다 — 30분봉으로는 9:10을 못 집는다.
INTRADAY_INTERVAL = "5m"
# 목표 시각에 해당하는 봉이 없을 때(개장 전·거래 정지) 허용할 오차.
INTRADAY_TOLERANCE_MIN = 30
INTRADAY_MAX_TOKENS = 8000

HTTP_TIMEOUT = 15
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def ensure_dirs() -> None:
    for d in (DATA_DIR, BRIEFINGS_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
