"""브리핑이 완성되면 카카오톡으로 알린다.

카카오 '나에게 보내기'를 쓴다. 받는 사람이 본인 한 명이라 친구 목록 권한도,
앱 심사도, 비즈 앱 전환도 필요 없다 — 친구에게 보내기만 심사를 받는다.

예약 시각에 깨어나 "브리핑 올라왔나" 확인하는 방식도 있었지만 쓰지 않는다.
GitHub Actions의 cron이 1~2시간 반씩 밀려서 발송 시각을 맞출 수가 없었다.
여기서 부르면 브리핑을 방금 만든 그 자리라 확인할 것도, 기다릴 것도 없다.

액세스 토큰은 6시간이면 만료되므로 저장하지 않는다. 실행할 때마다 리프레시
토큰으로 새로 발급받아 한 번 쓰고 버린다.

  KAKAO_REST_API_KEY    앱의 REST API 키
  KAKAO_REFRESH_TOKEN   talk_message 동의를 거쳐 받은 리프레시 토큰
  KAKAO_CLIENT_SECRET   클라이언트 시크릿(활성화한 앱이면 필수)

키가 없으면 조용히 건너뛴다. 로컬에서 브리핑만 만들어 볼 때 키가 없다고
실패하면 곤란하다.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from config import HTTP_TIMEOUT

TOKEN_URL = "https://kauth.kakao.com/oauth/token"
SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"

SERVICE_URL = "https://oneulmoney.vercel.app"

# 첫 줄의 두 자리는 시장에 따라 바뀐다. 시각은 그 브리핑의 이름이지 발송 시각이
# 아니다 — 07:00에 만든 미국 브리핑은 몇 시에 알림이 가든 '7시 브리핑'이다.
HEADLINE = {
    "us": "7시 미국 데일리 브리핑을 확인하세요",
    "kr": "6시 국내 데일리 브리핑을 확인하세요",
}

# 텍스트 템플릿 본문 상한. 넘기면 카카오가 통째로 거절하므로 미리 자른다.
TEXT_LIMIT = 200


def _post(url: str, data: dict, headers: dict = None) -> dict:
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers or {})
    req.add_header("Content-Type", "application/x-www-form-urlencoded;charset=utf-8")
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def _access_token(rest_key: str, refresh_token: str, secret: str) -> str:
    """리프레시 토큰으로 액세스 토큰을 새로 받는다."""
    data = {
        "grant_type": "refresh_token",
        "client_id": rest_key,
        "refresh_token": refresh_token,
    }
    # 시크릿을 활성화한 앱은 갱신 요청에도 넣어야 한다. 빠지면 KOE010이 난다.
    if secret:
        data["client_secret"] = secret
    token = _post(TOKEN_URL, data).get("access_token")
    if not token:
        raise RuntimeError("응답에 access_token이 없습니다")
    return token


def message_for(market: str) -> str:
    """알림 본문. 첫 줄은 어느 브리핑인지, 둘째 줄은 바로 열 수 있는 링크."""
    return "{}\n{}".format(HEADLINE[market], SERVICE_URL)


def send(market: str) -> bool:
    """카카오톡으로 알린다. 보냈으면 True.

    무슨 일이 나든 예외를 밖으로 던지지 않는다. 알림은 브리핑의 곁다리라,
    카카오가 죽었다고 브리핑 생성까지 실패로 끝나면 안 된다.
    """
    if market not in HEADLINE:
        print("  [알림] 모르는 시장이라 건너뜁니다: {}".format(market))
        return False

    rest_key = os.environ.get("KAKAO_REST_API_KEY")
    refresh_token = os.environ.get("KAKAO_REFRESH_TOKEN")
    secret = os.environ.get("KAKAO_CLIENT_SECRET", "")
    if not rest_key or not refresh_token:
        print("  [알림] KAKAO_REST_API_KEY / KAKAO_REFRESH_TOKEN 없음 → 발송 건너뜀")
        return False

    text = message_for(market)
    if len(text) > TEXT_LIMIT:
        text = text[:TEXT_LIMIT]

    try:
        token = _access_token(rest_key, refresh_token, secret)
        payload = {
            "object_type": "text",
            "text": text,
            # link는 필수 항목이라 비워둘 수 없다. 본문의 링크와 같은 곳을 가리켜
            # 말풍선 어디를 눌러도 서비스로 열리게 한다.
            "link": {"web_url": SERVICE_URL, "mobile_web_url": SERVICE_URL},
        }
        res = _post(SEND_URL, {"template_object": json.dumps(payload, ensure_ascii=False)},
                    {"Authorization": "Bearer " + token})
    except urllib.error.HTTPError as e:
        # 카카오는 실패 사유를 본문에 담아 보낸다. 상태 코드만 찍으면 원인을 알 수 없다.
        detail = ""
        try:
            detail = " " + e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        print("  [알림] 발송 실패 (HTTP {}){}".format(e.code, detail))
        return False
    except Exception as e:
        print("  [알림] 발송 실패: {}: {}".format(type(e).__name__, e))
        return False

    if res.get("result_code") == 0:
        print("  [알림] 카카오톡 발송 완료 — {}".format(HEADLINE[market]))
        return True
    print("  [알림] 발송은 됐으나 응답이 성공이 아닙니다: {}".format(res))
    return False
