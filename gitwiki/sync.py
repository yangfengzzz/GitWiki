"""Background import, enrichment, and first-run classification."""

from __future__ import annotations

import threading
import json
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, asdict
from pathlib import Path

from .classifier import classify_locally, classify_with_codex, reclassify_all_with_codex, review_unclassified_with_codex, review_owned_with_codex
from .github import GitHubClient, GitHubError
from .store import Store, now


@dataclass
class Job:
    running: bool = False
    phase: str = "idle"
    current: int = 0
    total: int = 0
    error: str = ""
    message: str = ""


class SyncManager:
    def __init__(self, store: Store, client: GitHubClient):
        self.store = store
        self.client = client
        self.lock = threading.RLock()
        self.sync = Job()
        self.readmes = Job()
        self.classification = Job()

    def status(self) -> dict:
        with self.lock:
            return {"sync": asdict(self.sync), "readmes": asdict(self.readmes), "classification": asdict(self.classification)}

    def start(self) -> bool:
        with self.lock:
            if self.sync.running:
                return False
            self.sync = Job(True, "connecting", message="正在连接 GitHub")
        threading.Thread(target=self._run, daemon=True, name="gitwiki-sync").start()
        return True

    def start_owned(self) -> bool:
        with self.lock:
            if self.sync.running:
                return False
            self.sync = Job(True, "owned", message="正在读取我的项目")
        threading.Thread(target=self._run_owned, daemon=True, name="gitwiki-owned-sync").start()
        return True

    def _set(self, which: str, **changes) -> None:
        with self.lock:
            job = getattr(self, which)
            for key, value in changes.items():
                setattr(job, key, value)

    def _run(self) -> None:
        try:
            first_import = not self.store.setting("last_sync")
            viewer = self.client.viewer()
            self.store.set_setting("username", viewer["login"])
            self._set("sync", phase="stars", message="正在读取全部 Star")
            stars = self.client.fetch_stars(lambda n: self._set("sync", current=n, message=f"已读取 {n} 个 Star"))
            result = self.store.replace_stars(stars)
            if first_import:
                self._set("sync", phase="lists", current=0, total=0, message="正在读取 GitHub Lists")
                lists = self.client.fetch_lists(lambda n, total: self._set("sync", current=n, total=total, message=f"已读取 {n}/{total} 个 List"))
                self.store.import_lists(lists)
            if not self.store.setting("taxonomy_version"):
                taxonomy = json.loads((Path(__file__).resolve().parent.parent / "taxonomy.json").read_text())
                self.store.replace_taxonomy(taxonomy["groups"])
            self._set("sync", phase="owned", current=0, total=0, message="正在读取我的项目")
            owned = self.client.fetch_owned_repos(
                viewer["login"], lambda n: self._set("sync", current=n, message=f"已读取 {n} 个我的项目"))
            owned_result = self.store.replace_owned_repos(owned)
            self.store.set_setting("last_owned_sync", now())
            self.store.begin_owned_review()
            self.store.set_setting("last_sync", now())
            self._set("sync", running=False, phase="complete", current=result["total"] + owned_result["total"],
                      total=result["total"] + owned_result["total"],
                      message=f"同步完成：{result['total']} 个 Star、{owned_result['total']} 个我的项目")
            self.start_readmes()
            if (not self.store.setting("owned_review_run") and
                    (self.store.setting("unclassified_review_run") or self.store.setting("full_classification_run")
                     or not self.store.setting("initial_classified"))):
                self.start_classification()
        except Exception as exc:
            self._set("sync", running=False, phase="error", error=str(exc), message="同步失败")

    def _run_owned(self) -> None:
        try:
            viewer = self.client.viewer()
            username = viewer["login"]
            self.store.set_setting("username", username)
            repos = self.client.fetch_owned_repos(
                username, lambda n: self._set("sync", current=n, message=f"已读取 {n} 个我的项目"))
            result = self.store.replace_owned_repos(repos)
            self.store.set_setting("last_owned_sync", now())
            self.store.begin_owned_review()
            self._set("sync", running=False, phase="complete", current=result["total"], total=result["total"],
                      message=f"我的项目同步完成：{result['total']} 个，资料库新增 {result['added']} 个，合并已有 Star {result['overlap']} 个")
            self.start_readmes()
        except Exception as exc:
            self._set("sync", running=False, phase="error", error=str(exc), message="我的项目同步失败")

    def start_readmes(self) -> bool:
        with self.lock:
            if self.readmes.running:
                return False
            self.readmes = Job(True, "readmes", message="正在缓存 README")
        threading.Thread(target=self._run_readmes, daemon=True, name="gitwiki-readmes").start()
        return True

    def _run_readmes(self) -> None:
        try:
            self._cache_readmes()
            if self.readmes.phase == "complete" and self.store.setting("owned_review_run"):
                self.start_classification()
        except Exception as exc:
            self._set("readmes", running=False, phase="error", error=str(exc),
                      message="README 缓存出错，可重新启动")

    def _cache_readmes(self) -> None:
        pending = self.store.readme_pending()
        completed = 0
        total = len(pending)
        self._set("readmes", total=total)
        while pending:
            queue = iter(pending)
            with ThreadPoolExecutor(max_workers=4, thread_name_prefix="gitwiki-readme") as pool:
                futures = {}

                def submit_next():
                    try:
                        repo_id = next(queue)
                    except StopIteration:
                        return
                    futures[pool.submit(self.client.fetch_readme, repo_id)] = repo_id

                for _ in range(4):
                    submit_next()
                paused = None
                while futures and not paused:
                    done, _ = wait(futures, return_when=FIRST_COMPLETED)
                    for future in done:
                        repo_id = futures.pop(future)
                        try:
                            content, status = future.result()
                            self.store.set_readme(repo_id, content, status)
                        except GitHubError as exc:
                            if exc.status in (401, 403, 429):
                                paused = exc
                                break
                            self.store.set_readme(repo_id, None, "error")
                        completed += 1
                        self._set("readmes", current=completed, message=f"已缓存 {completed}/{total} 个 README")
                        submit_next()
                if paused:
                    for future in futures:
                        future.cancel()
                    self._set("readmes", running=False, phase="paused", current=completed,
                              error=str(paused), message="README 缓存已暂停")
                    return
            # A Star sync can invalidate README data while this worker runs.
            pending = self.store.readme_pending(retry_errors=False)
            total += len(pending)
            self._set("readmes", total=total)
        self._set("readmes", running=False, phase="complete", message="README 缓存完成")

    def start_classification(self) -> bool:
        with self.lock:
            if self.classification.running:
                return False
            targeted = bool(self.store.setting("unclassified_review_run"))
            full = bool(self.store.setting("full_classification_run"))
            owned = bool(self.store.setting("owned_review_run"))
            phase = "owned-review" if owned else "unclassified-review" if targeted else "full-codex" if full else "local"
            message = ("正在分类我的项目" if owned else "正在复核未分类项目" if targeted else
                       "正在重新阅读全部 README 并分类" if full else "正在整理初始收藏")
            self.classification = Job(True, phase, message=message)
        threading.Thread(target=self._run_classification, daemon=True, name="gitwiki-classify").start()
        return True

    def _run_classification(self) -> None:
        try:
            if self.store.setting("owned_review_run"):
                count = review_owned_with_codex(
                    self.store,
                    lambda n, total: self._set("classification", current=n, total=total,
                                               message=f"已分类我的项目 {n}/{total}"),
                )
                self._set("classification", running=False, phase="complete", current=count, total=count,
                          message=f"我的项目分类完成：已检查 {count} 个项目")
                return
            if self.store.setting("unclassified_review_run"):
                count = review_unclassified_with_codex(
                    self.store,
                    lambda n, total: self._set("classification", current=n, total=total,
                                               message=f"已复核未分类项目 {n}/{total}"),
                )
                self._set("classification", running=False, phase="complete", current=count, total=count,
                          message=f"未分类复核完成：已检查 {count} 个项目")
                return
            if self.store.setting("full_classification_run"):
                count = reclassify_all_with_codex(
                    self.store,
                    lambda n, total: self._set("classification", current=n, total=total,
                                               message=f"已重新分类 {n}/{total} 个项目"),
                )
                self._set("classification", running=False, phase="complete", current=count, total=count,
                          message=f"全量分类完成：已检查 {count} 个项目")
                return
            local = classify_locally(
                self.store,
                lambda n, total: self._set("classification", current=n, total=total,
                                           message=f"已扫描 {n}/{total} 个项目"),
            )
            self._set("classification", phase="codex", current=0, total=local["unresolved"],
                      message=f"正在整理剩余 {local['unresolved']} 个项目")
            count = classify_with_codex(
                self.store, self.client,
                lambda n, total: self._set("classification", current=n, total=total,
                                           message=f"已整理 {n}/{total} 个项目"),
            )
            self.store.set_setting("initial_classified", now())
            self._set("classification", running=False, phase="complete", current=count,
                      message=f"初始分类完成：规则 {local['assigned']} 个，Codex 检查 {count} 个")
        except Exception as exc:
            self._set("classification", running=False, phase="error", error=str(exc),
                      message="Codex 分类暂停，可稍后重试")
