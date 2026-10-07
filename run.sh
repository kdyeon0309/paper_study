#!/bin/sh
# Paper Study 실행. 처음이면 가상환경을 만들고 의존성을 설치한다.
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "처음 실행: 가상환경을 만들고 의존성을 설치합니다..."
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements.txt
fi
exec .venv/bin/python -m app "$@"
