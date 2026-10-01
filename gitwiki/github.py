"""Small GitHub REST/GraphQL client using the user's existing gh login."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable


class GitHubError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def token_from_gh() -> str | None:
    """Read the existing gh credential into process memory; never print or persist it."""
    try:
        result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10, check=True)
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


class GitHubClient:
    def __init__(self, token: str | None = None, opener=None):
        self.token = token or os.environ.get("GITHUB_TOKEN") or token_from_gh()
        self.opener = opener or urllib.request.urlopen
        self.last_request = 0.0
        self.lock = threading.Lock()

    def _request(self, path: str, *, method: str = "GET", payload: dict | None = None,
                 accept: str = "application/vnd.github+json", limit: int = 12_000_000):
        if not self.token:
            raise GitHubError("GitHub 未登录。请运行 gh auth login，或设置 GITHUB_TOKEN。", 401)
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Invalid GitHub API path")
        # A gentle shared pace also helps avoid GitHub's secondary rate limit.
        with self.lock:
            delay = 0.35 - (time.monotonic() - self.last_request)
            if delay > 0:
                time.sleep(delay)
            self.last_request = time.monotonic()
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            "https://api.github.com" + path, data=body, method=method,
            headers={
                "Authorization": "Bearer " + self.token,
                "Accept": accept,
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "GitWiki-local",
                **({"Content-Type": "application/json"} if body is not None else {}),
            },
        )
        for attempt in range(3):
            try:
                with self.opener(request, timeout=35) as response:
                    raw = response.read(limit + 1)
                    if len(raw) > limit:
                        raise GitHubError("GitHub 响应超过本地缓存大小限制")
                    if accept == "application/vnd.github.raw+json":
                        return raw.decode("utf-8", errors="replace")
                    if "json" in response.headers.get("Content-Type", ""):
                        return json.loads(raw.decode("utf-8"))
                    return raw.decode("utf-8", errors="replace")
            except urllib.error.HTTPError as exc:
                try:
                    detail = json.loads(exc.read(4096).decode("utf-8"))
                    message = detail.get("message") or str(exc)
                except (ValueError, UnicodeError):
                    message = str(exc)
                if exc.code in (500, 502, 503, 504) and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                if exc.code == 403 and exc.headers.get("X-RateLimit-Remaining") == "0":
                    message = "GitHub API 额度已用尽，请稍后重试。"
                elif exc.code in (403, 429) and "rate limit" in message.lower():
                    message = "GitHub 请求频率受限，请按 GitHub 的提示稍后重试。"
                raise GitHubError(message, exc.code) from exc
            except urllib.error.URLError as exc:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise GitHubError("连接 GitHub 失败：" + str(exc.reason)) from exc
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise GitHubError("GitHub 响应不完整，请重试同步") from exc
        raise GitHubError("GitHub 请求未成功")

    def rest(self, path: str, *, accept: str = "application/vnd.github+json"):
        return self._request(path, accept=accept)

    def graphql(self, query: str, variables: dict | None = None) -> dict:
        result = self._request("/graphql", method="POST", payload={"query": query, "variables": variables or {}})
        if result.get("errors"):
            raise GitHubError("; ".join(error.get("message", "GraphQL error") for error in result["errors"]))
        return result["data"]

    def viewer(self) -> dict:
        return self.rest("/user")

    def fetch_stars(self, progress: Callable[[int], None] | None = None) -> list[dict]:
        stars: list[dict] = []
        page = 1
        while True:
            result = self.rest(
                f"/user/starred?per_page=100&page={page}&sort=created&direction=desc",
                accept="application/vnd.github.star+json",
            )
            if not isinstance(result, list):
                raise GitHubError("Star 接口返回了意外的数据格式")
            stars.extend(result)
            if progress:
                progress(len(stars))
            if len(result) < 100:
                return stars
            page += 1

    def fetch_owned_repos(self, username: str,
                          progress: Callable[[int], None] | None = None) -> list[dict]:
        """List all repositories personally owned by the authenticated user."""
        repos: list[dict] = []
        page = 1
        while True:
            result = self.rest(
                f"/user/repos?affiliation=owner&visibility=all&per_page=100&page={page}&sort=updated&direction=desc"
            )
            if not isinstance(result, list):
                raise GitHubError("我的项目接口返回了意外的数据格式")
            repos.extend(item for item in result if
                         item.get("owner", {}).get("login", "").casefold() == username.casefold())
            if progress:
                progress(len(repos))
            if len(result) < 100:
                return repos
            page += 1

    def fetch_lists(self, progress: Callable[[int, int], None] | None = None) -> list[dict]:
        lists: list[dict] = []
        cursor = None
        while True:
            data = self.graphql(
                "query($cursor:String){viewer{lists(first:100,after:$cursor){nodes{id name description} pageInfo{hasNextPage endCursor}}}}",
                {"cursor": cursor},
            )
            connection = data["viewer"]["lists"]
            lists.extend(node for node in connection.get("nodes", []) if node)
            if not connection["pageInfo"]["hasNextPage"]:
                break
            cursor = connection["pageInfo"]["endCursor"]
        for index, item in enumerate(lists, 1):
            item["repos"] = []
            cursor = None
            while True:
                data = self.graphql(
                    "query($id:ID!,$cursor:String){node(id:$id){... on UserList{items(first:100,after:$cursor){nodes{... on Repository{nameWithOwner}} pageInfo{hasNextPage endCursor}}}}}",
                    {"id": item["id"], "cursor": cursor},
                )
                connection = data["node"]["items"]
                item["repos"].extend(node["nameWithOwner"] for node in connection.get("nodes", []) if node and node.get("nameWithOwner"))
                if not connection["pageInfo"]["hasNextPage"]:
                    break
                cursor = connection["pageInfo"]["endCursor"]
            if progress:
                progress(index, len(lists))
        return lists

    def fetch_readme(self, repo_id: str) -> tuple[str | None, str]:
        owner, name = repo_id.split("/", 1)
        path = "/repos/" + urllib.parse.quote(owner, safe="") + "/" + urllib.parse.quote(name, safe="") + "/readme"
        try:
            content = self._request(path, accept="application/vnd.github.raw+json", limit=750_000)
            if isinstance(content, dict):
                # GitHub may fall back to the JSON representation for some responses.
                if content.get("encoding") == "base64":
                    import base64
                    return base64.b64decode(content.get("content", "")).decode("utf-8", errors="replace"), "ready"
                raise GitHubError("README 响应格式无法识别")
            return content, "ready"
        except GitHubError as exc:
            if exc.status == 404:
                return None, "missing"
            raise
