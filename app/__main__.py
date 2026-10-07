"""`python -m app` starts the server and opens the browser."""
import argparse
import threading
import webbrowser

import uvicorn


def main():
    parser = argparse.ArgumentParser(prog="python -m app", description="Paper Study 서버 실행")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-open", action="store_true", help="브라우저를 열지 않는다")
    args = parser.parse_args()
    url = f"http://127.0.0.1:{args.port}"
    if not args.no_open:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    print(f"Paper Study: {url}  (끄려면 Ctrl+C)", flush=True)
    # 127.0.0.1에만 연다. 로그인이 없는 개인용 도구라서 같은 네트워크의 다른 기기에 노출하지 않는다.
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
