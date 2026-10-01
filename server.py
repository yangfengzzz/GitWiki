#!/usr/bin/env python3
"""GitWiki local web server. Run with: .venv/bin/python server.py"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from gitwiki.github import GitHubClient, GitHubError
from gitwiki.store import Store
from gitwiki.sync import SyncManager


ROOT = Path(__file__).resolve().parent
DATA_PATH = Path(os.environ.get("GITWIKI_DB", ROOT / "data" / "gitwiki.sqlite3"))
STORE = Store(DATA_PATH)
CLIENT = GitHubClient()
SYNC = SyncManager(STORE, CLIENT)


class Handler(BaseHTTPRequestHandler):
    server_version = "GitWiki/1.0"

    def log_message(self, format, *args):
        # Never log request bodies or credentials.
        if self.path.startswith("/api/status"):
            return
        print("%s - %s" % (self.address_string(), format % args), flush=True)

    def _send(self, status: int, content: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' https://github.com https://*.githubusercontent.com data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(content)

    def json(self, status: int, value) -> None:
        self._send(status, json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _host_ok(self) -> bool:
        host = self.headers.get("Host", "")
        return host in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

    def _body(self) -> dict:
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            raise ValueError("需要 application/json")
        size = int(self.headers.get("Content-Length", "0"))
        if size < 1 or size > 131_072:
            raise ValueError("请求内容过大或为空")
        value = json.loads(self.rfile.read(size))
        if not isinstance(value, dict):
            raise ValueError("请求必须是 JSON 对象")
        return value

    def _post_ok(self) -> bool:
        origin = self.headers.get("Origin", "")
        return origin in (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}")

    def do_GET(self):
        if not self._host_ok():
            self.json(403, {"error": "Invalid local host"})
            return
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path == "/api/state":
                repos = STORE.repos()
                self.json(200, {
                    "repos": repos,
                    "categories": STORE.categories(),
                    "username": STORE.setting("username"),
                    "connected": bool(CLIENT.token),
                    "last_sync": STORE.setting("last_sync"),
                    "jobs": SYNC.status(),
                    "count": len(repos),
                })
            elif parsed.path == "/api/status":
                self.json(200, {"jobs": SYNC.status(), "last_sync": STORE.setting("last_sync"),
                                "connected": bool(CLIENT.token), "username": STORE.setting("username")})
            elif parsed.path == "/api/readme":
                repo_id = (query.get("id") or [""])[0]
                item = STORE.repo(repo_id)
                if not item:
                    self.json(404, {"error": "项目不存在"})
                    return
                if item["readme_status"] in ("pending", "error") and CLIENT.token:
                    try:
                        content, status = CLIENT.fetch_readme(repo_id)
                        STORE.set_readme(repo_id, content, status)
                        item = STORE.repo(repo_id)
                    except GitHubError as exc:
                        self.json(502, {"error": str(exc)})
                        return
                self.json(200, {"id": repo_id, "readme": item["readme"] or "", "status": item["readme_status"]})
            elif parsed.path == "/api/search-readme":
                term = (query.get("q") or [""])[0][:100]
                self.json(200, {"ids": sorted(STORE.search_readmes(term))})
            elif parsed.path in ("/", "/index.html", "/live.js", "/styles.css", "/favicon.svg", "/vendor/markdown-it.min.js", "/vendor/dompurify.min.js"):
                filename = "index.html" if parsed.path == "/" else parsed.path[1:]
                content = (ROOT / filename).read_bytes()
                mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
                self._send(200, content, mime + ("; charset=utf-8" if mime.startswith("text/") or mime == "application/javascript" else ""))
            else:
                self.json(404, {"error": "页面不存在"})
        except Exception as exc:
            self.json(500, {"error": str(exc)})

    def do_POST(self):
        if not self._host_ok() or not self._post_ok():
            self.json(403, {"error": "仅允许本地页面发起更改"})
            return
        path = urlparse(self.path).path
        try:
            body = self._body()
            if path == "/api/auth":
                token = str(body.get("token", "")).strip()
                if not token or len(token) > 500:
                    raise ValueError("请输入 GitHub 访问令牌")
                candidate = GitHubClient(token)
                username = candidate.viewer()["login"]
                CLIENT.token = token
                STORE.set_setting("username", username)
                self.json(200, {"username": username})
            elif path == "/api/sync":
                if not CLIENT.token:
                    self.json(401, {"error": "请先连接 GitHub"})
                    return
                self.json(202, {"started": SYNC.start(), "jobs": SYNC.status()})
            elif path == "/api/readmes":
                self.json(202, {"started": SYNC.start_readmes()})
            elif path == "/api/classify":
                self.json(202, {"started": SYNC.start_classification()})
            elif path == "/api/categories":
                item = STORE.create_category(str(body.get("name", "")), body.get("parent"))
                self.json(201, item)
            elif path == "/api/category-update":
                item = STORE.update_category(str(body.get("id", "")), str(body.get("name", "")), body.get("parent"))
                self.json(200, item)
            elif path == "/api/category-delete":
                STORE.delete_category(str(body.get("id", "")))
                self.json(200, {"ok": True})
            elif path == "/api/repo-categories":
                ids = body.get("repo_ids")
                cats = body.get("category_ids")
                mode = body.get("mode", "replace")
                if not isinstance(ids, list) or not isinstance(cats, list) or len(ids) > 500 or len(cats) > 80:
                    raise ValueError("分类请求格式不正确")
                STORE.set_categories(ids, cats, mode)
                self.json(200, {"ok": True})
            elif path == "/api/tags":
                repo_id, tags = body.get("repo_id"), body.get("tags")
                if not isinstance(repo_id, str) or not isinstance(tags, list) or len(tags) > 100:
                    raise ValueError("标签请求格式不正确")
                STORE.set_tags(repo_id, tags)
                self.json(200, {"ok": True})
            elif path == "/api/notes":
                repo_id, note = body.get("repo_id"), body.get("note")
                if not isinstance(repo_id, str) or not isinstance(note, str) or len(note) > 100_000:
                    raise ValueError("笔记请求格式不正确")
                STORE.set_note(repo_id, note)
                self.json(200, {"ok": True})
            else:
                self.json(404, {"error": "API 不存在"})
        except GitHubError as exc:
            self.json(exc.status or 502, {"error": str(exc)})
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self.json(400, {"error": str(exc)})
        except Exception as exc:
            self.json(500, {"error": str(exc)})


def main():
    parser = argparse.ArgumentParser(description="GitWiki local Star library")
    parser.add_argument("--port", type=int, default=4173)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"GitWiki: http://127.0.0.1:{args.port}/", flush=True)
    print("GitHub login:", "available" if CLIENT.token else "not found", flush=True)
    if STORE.setting("last_sync"):
        if CLIENT.token and STORE.readme_pending():
            SYNC.start_readmes()
        if (STORE.setting("unclassified_review_run") or STORE.setting("full_classification_run")
                or (CLIENT.token and not STORE.setting("initial_classified"))):
            SYNC.start_classification()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
