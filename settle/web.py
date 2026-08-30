"""로컬 웹 GUI 서버.

표준 라이브러리 http.server 만 쓴다. 브라우저를 화면으로 삼으면 설치할 것 없이
어느 OS에서나 같은 화면이 나오고, 나중에 진짜 웹/앱으로 갈 때 이 화면을
거의 그대로 옮길 수 있다.

접근 제한
- 127.0.0.1 에만 바인딩한다. 같은 네트워크의 다른 기기는 접속할 수 없다.
- 실행할 때마다 임의 토큰을 만들고, 모든 API 요청에 헤더로 요구한다.
  브라우저는 커스텀 헤더가 붙은 교차 출처 요청을 사전 확인 없이 못 보내므로,
  다른 사이트가 몰래 이 서버에 쓰기 요청을 보내는 것을 막는다.
"""

from __future__ import annotations

import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from . import api, store
from .models import Book

STATIC = Path(__file__).parent / "static"
TOKEN_HEADER = "X-Settle-Token"
MAX_BODY = 4 * 1024 * 1024      # 붙여넣기 텍스트를 넉넉히 받되 무한정은 아니게
FAVICON = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    b'<rect width="32" height="32" rx="7" fill="#2f6df6"/>'
    b'<text x="16" y="23" font-size="19" text-anchor="middle" fill="#fff"'
    b' font-family="system-ui,sans-serif">\xe2\x82\xa9</text></svg>'
)


class _State:
    """디스크의 장부를 요청마다 다시 읽어 CLI와 GUI가 어긋나지 않게 한다."""

    def __init__(self, path: Optional[Path]):
        self.path = path
        self.lock = threading.Lock()
        self.token = secrets.token_urlsafe(24)

    def load(self) -> Book:
        return store.load(self.path)

    def save(self, book: Book) -> None:
        store.save(book, self.path)


def _handler_class(state: _State):
    index_html = (STATIC / "index.html").read_text(encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        server_version = "travel-settle"
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):     # 요청마다 콘솔을 어지럽히지 않는다
            pass

        # --- 응답 도우미 -------------------------------------------
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data: dict) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        def _authorized(self) -> bool:
            return secrets.compare_digest(
                self.headers.get(TOKEN_HEADER, ""), state.token)

        # --- 라우팅 -------------------------------------------------
        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                page = index_html.replace("__SETTLE_TOKEN__", state.token)
                self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
                return
            if path == "/favicon.ico":
                self._send(200, FAVICON, "image/svg+xml")
                return
            if path.startswith("/api/"):
                if not self._authorized():
                    self._json(401, {"error": "인증 토큰이 올바르지 않습니다"})
                    return
                self._dispatch("GET", path, {})
                return
            self._json(404, {"error": "없는 경로입니다"})

        def do_POST(self) -> None:
            path = self.path.split("?", 1)[0]
            if not path.startswith("/api/"):
                self._json(404, {"error": "없는 경로입니다"})
                return
            if not self._authorized():
                self._json(401, {"error": "인증 토큰이 올바르지 않습니다"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                self._json(413, {"error": "요청이 너무 큽니다"})
                return
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json(400, {"error": "요청 본문을 해석할 수 없습니다"})
                return
            if not isinstance(payload, dict):
                self._json(400, {"error": "요청 본문은 객체여야 합니다"})
                return
            self._dispatch("POST", path, payload)

        def _dispatch(self, method: str, path: str, payload: dict) -> None:
            with state.lock:
                book = state.load()
                try:
                    result = api.handle(book, method, path, payload)
                except api.ApiError as exc:
                    self._json(exc.status, {"error": exc.message})
                    return
                except Exception as exc:                      # noqa: BLE001
                    self._json(500, {"error": f"처리 중 오류: {exc}"})
                    return
                if path not in api.READ_ONLY:
                    state.save(book)
            self._json(200, result)

    return Handler


def serve(path: Optional[Path] = None, port: int = 8765,
          open_browser: bool = True) -> None:
    state = _State(path)
    handler = _handler_class(state)
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    except OSError as exc:
        raise RuntimeError(
            f"{port} 포트를 열 수 없습니다 ({exc}). --port 로 다른 번호를 지정하세요."
        ) from exc

    url = f"http://127.0.0.1:{httpd.server_port}/"
    print("여행 정산 계산기 GUI가 열렸습니다.")
    print(f"  {url}")
    print("  이 컴퓨터에서만 접속됩니다. 종료하려면 Ctrl+C.")
    if open_browser:
        threading.Timer(0.4, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n종료했습니다.")
    finally:
        httpd.server_close()
