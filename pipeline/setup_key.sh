#!/bin/bash
# Anthropic API 키를 ~/.config/notefolio/env 에 저장한다.
#
# 이 파일을 프로젝트 밖(~/.config)에 두는 이유는 미리보기용 로컬 서버가
# 프로젝트 폴더를 통째로 서빙하기 때문이다. 프로젝트 안에 두면 웹으로 새어나간다.
#
# 실행:  bash pipeline/setup_key.sh

set -u

DEST="$HOME/.config/notefolio/env"
mkdir -p "$(dirname "$DEST")"
chmod 700 "$(dirname "$DEST")"

echo "Anthropic 콘솔(console.anthropic.com → API Keys)에서 발급한 키를 붙여넣고"
echo "엔터를 누르세요. 입력은 화면에 표시되지 않습니다."
printf '키: '

stty -echo
IFS= read -r key
stty echo
printf '\n'

# 앞뒤 공백 제거 — 복사할 때 딸려오는 경우가 많다
key="${key#"${key%%[![:space:]]*}"}"
key="${key%"${key##*[![:space:]]}"}"

if [ -z "$key" ]; then
  echo "입력이 비었습니다. 저장하지 않았습니다." >&2
  exit 1
fi

case "$key" in
  sk-ant-*) ;;
  *)
    echo "키가 'sk-ant-'로 시작하지 않습니다. 명령어나 다른 값을 붙여넣지 않았는지" >&2
    echo "확인하세요. 저장하지 않았습니다." >&2
    exit 1 ;;
esac

if [ "${#key}" -lt 50 ]; then
  echo "키가 너무 짧습니다(${#key}자). 콘솔에서 키 전체를 복사했는지 확인하세요." >&2
  exit 1
fi

printf 'ANTHROPIC_API_KEY=%s\n' "$key" > "$DEST"
chmod 600 "$DEST"
echo "저장 완료 — ${#key}자를 $DEST 에 기록했습니다."
