"""SQLite persistence for GitWiki. Tokens are deliberately never stored here."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self.connection() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS settings (
                  key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS repos (
                  id TEXT PRIMARY KEY,
                  github_id INTEGER,
                  description TEXT NOT NULL DEFAULT '',
                  language TEXT NOT NULL DEFAULT '',
                  stars INTEGER NOT NULL DEFAULT 0,
                  pushed_at TEXT NOT NULL DEFAULT '',
                  starred_at TEXT NOT NULL DEFAULT '',
                  topics TEXT NOT NULL DEFAULT '[]',
                  default_branch TEXT NOT NULL DEFAULT 'main',
                  archived INTEGER NOT NULL DEFAULT 0,
                  readme TEXT,
                  readme_status TEXT NOT NULL DEFAULT 'pending',
                  readme_fetched_at TEXT,
                  note TEXT NOT NULL DEFAULT '',
                  is_starred INTEGER NOT NULL DEFAULT 1,
                  is_owned INTEGER NOT NULL DEFAULT 0,
                  is_private INTEGER NOT NULL DEFAULT 0,
                  created_at TEXT NOT NULL DEFAULT '',
                  new_since_sync INTEGER NOT NULL DEFAULT 0,
                  updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS repos_starred ON repos(is_starred, starred_at DESC);
                CREATE TABLE IF NOT EXISTS categories (
                  id TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  parent_id TEXT REFERENCES categories(id) ON DELETE SET NULL,
                  color TEXT NOT NULL DEFAULT '#6b8a78',
                  source TEXT NOT NULL DEFAULT 'local',
                  github_id TEXT UNIQUE,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS repo_categories (
                  repo_id TEXT NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
                  category_id TEXT NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                  PRIMARY KEY(repo_id, category_id)
                );
                CREATE INDEX IF NOT EXISTS category_repos ON repo_categories(category_id);
                CREATE TABLE IF NOT EXISTS repo_tags (
                  repo_id TEXT NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
                  tag TEXT NOT NULL,
                  PRIMARY KEY(repo_id, tag)
                );
                CREATE TABLE IF NOT EXISTS ai_classification (
                  repo_id TEXT PRIMARY KEY REFERENCES repos(id) ON DELETE CASCADE,
                  classified_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS full_classification (
                  repo_id TEXT PRIMARY KEY REFERENCES repos(id) ON DELETE CASCADE,
                  run_id TEXT NOT NULL,
                  classified_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS unclassified_reviews (
                  repo_id TEXT PRIMARY KEY REFERENCES repos(id) ON DELETE CASCADE,
                  run_id TEXT NOT NULL,
                  reviewed_at TEXT NOT NULL,
                  suggested_categories TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS owned_reviews (
                  repo_id TEXT PRIMARY KEY REFERENCES repos(id) ON DELETE CASCADE,
                  run_id TEXT NOT NULL,
                  pushed_at TEXT NOT NULL,
                  readme_status TEXT NOT NULL DEFAULT '',
                  reviewed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS manual_category_edits (
                  repo_id TEXT PRIMARY KEY REFERENCES repos(id) ON DELETE CASCADE,
                  edited_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reference_lists (
                  id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS reference_membership (
                  repo_id TEXT NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
                  list_id TEXT NOT NULL REFERENCES reference_lists(id) ON DELETE CASCADE,
                  PRIMARY KEY(repo_id,list_id)
                );
                """
            )
            columns = {row["name"] for row in db.execute("PRAGMA table_info(repos)")}
            for name, definition in (
                ("is_owned", "INTEGER NOT NULL DEFAULT 0"),
                ("is_private", "INTEGER NOT NULL DEFAULT 0"),
                ("created_at", "TEXT NOT NULL DEFAULT ''"),
            ):
                if name not in columns:
                    db.execute(f"ALTER TABLE repos ADD COLUMN {name} {definition}")
            review_columns = {row["name"] for row in db.execute("PRAGMA table_info(owned_reviews)")}
            if "readme_status" not in review_columns:
                db.execute("ALTER TABLE owned_reviews ADD COLUMN readme_status TEXT NOT NULL DEFAULT ''")
            db.execute(
                """UPDATE owned_reviews SET readme_status=(
                     SELECT r.readme_status FROM repos r WHERE r.id=owned_reviews.repo_id
                   ) WHERE readme_status='' AND EXISTS (
                     SELECT 1 FROM repos r WHERE r.id=owned_reviews.repo_id
                       AND (r.readme_status<>'ready' OR r.readme_fetched_at IS NULL
                            OR datetime(r.readme_fetched_at)<=datetime(owned_reviews.reviewed_at))
                   )"""
            )

    @contextmanager
    def connection(self):
        with self.lock:
            db = sqlite3.connect(self.path, timeout=30)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

    def setting(self, key: str, default: str = "") -> str:
        with self.connection() as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.connection() as db:
            db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def replace_stars(self, stars: list[dict]) -> dict:
        """Commit a complete REST pagination result without losing local annotations."""
        timestamp = now()
        with self.connection() as db:
            previously_synced = bool(db.execute("SELECT value FROM settings WHERE key='last_sync'").fetchone())
            old_ids = {r[0] for r in db.execute("SELECT id FROM repos WHERE is_starred=1")}
            seen = set()
            for entry in stars:
                item = entry.get("repo") or entry
                full_name = item.get("full_name")
                if not full_name or "/" not in full_name:
                    continue
                seen.add(full_name)
                db.execute(
                    """INSERT INTO repos(id,github_id,description,language,stars,pushed_at,starred_at,
                       topics,default_branch,archived,is_starred,new_since_sync,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,1,?,?)
                       ON CONFLICT(id) DO UPDATE SET
                       github_id=excluded.github_id,description=excluded.description,
                       language=excluded.language,stars=excluded.stars,pushed_at=excluded.pushed_at,
                       starred_at=excluded.starred_at,topics=excluded.topics,
                       default_branch=excluded.default_branch,archived=excluded.archived,
                       readme_status=CASE WHEN repos.pushed_at<>excluded.pushed_at THEN 'pending' ELSE repos.readme_status END,
                       is_starred=1,updated_at=excluded.updated_at""",
                    (
                        full_name, item.get("id"), item.get("description") or "",
                        item.get("language") or "", item.get("stargazers_count") or 0,
                        item.get("pushed_at") or item.get("updated_at") or "",
                        entry.get("starred_at") or "", json.dumps(item.get("topics") or []),
                        item.get("default_branch") or "main", int(bool(item.get("archived"))),
                        int(previously_synced and full_name not in old_ids), timestamp,
                    ),
                )
            # Only mark removals after every remote page succeeded.
            if seen:
                db.executemany("UPDATE repos SET is_starred=0,new_since_sync=0 WHERE id=?", [(x,) for x in old_ids - seen])
            elif old_ids:
                db.execute("UPDATE repos SET is_starred=0,new_since_sync=0")
            return {"total": len(seen), "new": len(seen - old_ids) if previously_synced else 0, "removed": len(old_ids - seen)}

    def replace_owned_repos(self, repos: list[dict]) -> dict:
        """Merge owned repositories by full name, preserving existing Stars and annotations."""
        timestamp = now()
        with self.connection() as db:
            old_ids = {row[0] for row in db.execute("SELECT id FROM repos WHERE is_owned=1")}
            existing_ids = {row[0] for row in db.execute("SELECT id FROM repos")}
            starred_ids = {row[0] for row in db.execute("SELECT id FROM repos WHERE is_starred=1")}
            seen = set()
            for item in repos:
                full_name = item.get("full_name")
                if not full_name or "/" not in full_name:
                    continue
                seen.add(full_name)
                db.execute(
                    """INSERT INTO repos(id,github_id,description,language,stars,pushed_at,starred_at,
                       topics,default_branch,archived,is_starred,is_owned,is_private,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,'',?,?,?,0,1,?,?,?)
                       ON CONFLICT(id) DO UPDATE SET
                       github_id=excluded.github_id,description=excluded.description,
                       language=excluded.language,stars=excluded.stars,pushed_at=excluded.pushed_at,
                       topics=excluded.topics,default_branch=excluded.default_branch,
                       archived=excluded.archived,is_owned=1,is_private=excluded.is_private,
                       created_at=excluded.created_at,
                       readme_status=CASE WHEN repos.pushed_at<>excluded.pushed_at THEN 'pending' ELSE repos.readme_status END,
                       updated_at=excluded.updated_at""",
                    (full_name, item.get("id"), item.get("description") or "",
                     item.get("language") or "", item.get("stargazers_count") or 0,
                     item.get("pushed_at") or item.get("updated_at") or "",
                     json.dumps(item.get("topics") or []), item.get("default_branch") or "main",
                     int(bool(item.get("archived"))), int(bool(item.get("private"))),
                     item.get("created_at") or "", timestamp),
                )
            db.executemany("UPDATE repos SET is_owned=0 WHERE id=?", [(repo_id,) for repo_id in old_ids - seen])
            return {"total": len(seen), "new": len(seen - old_ids),
                    "added": len(seen - existing_ids), "removed": len(old_ids - seen),
                    "overlap": len(seen & starred_ids)}

    def import_lists(self, lists: list[dict]) -> int:
        """Keep GitHub Lists as reference material for the new local taxonomy."""
        with self.connection() as db:
            for item in lists:
                github_id = item["id"]
                db.execute(
                    """INSERT INTO reference_lists(id,name,description) VALUES(?,?,?)
                       ON CONFLICT(id) DO UPDATE SET name=excluded.name,description=excluded.description""",
                    (github_id, item["name"], item.get("description") or ""),
                )
                db.execute("DELETE FROM reference_membership WHERE list_id=?", (github_id,))
                for repo_id in item.get("repos", []):
                    db.execute("INSERT OR IGNORE INTO reference_membership(repo_id,list_id) SELECT id,? FROM repos WHERE id=? AND is_starred=1", (github_id, repo_id))
            return len(lists)

    def migrate_imported_lists(self) -> int:
        """Move the provisional 32 GitHub categories into reference tables."""
        with self.connection() as db:
            rows = db.execute("SELECT id,github_id,name FROM categories WHERE source='github' AND github_id IS NOT NULL").fetchall()
            for row in rows:
                db.execute("INSERT OR IGNORE INTO reference_lists(id,name) VALUES(?,?)", (row["github_id"], row["name"]))
                db.execute(
                    """INSERT OR IGNORE INTO reference_membership(repo_id,list_id)
                       SELECT repo_id,? FROM repo_categories WHERE category_id=?""",
                    (row["github_id"], row["id"]),
                )
            return len(rows)

    def reference_summary(self) -> list[dict]:
        with self.connection() as db:
            lists = [dict(row) for row in db.execute("SELECT * FROM reference_lists ORDER BY name")]
            for item in lists:
                members = db.execute(
                    """SELECT r.id,r.description,r.topics FROM reference_membership m
                       JOIN repos r ON r.id=m.repo_id WHERE m.list_id=? AND r.is_starred=1
                       ORDER BY r.starred_at DESC""", (item["id"],),
                ).fetchall()
                item["count"] = len(members)
                item["sample"] = [{"id": row["id"], "description": row["description"][:120],
                                    "topics": json.loads(row["topics"])[:4]} for row in members[:8]]
        return lists

    def replace_taxonomy(self, groups: list[dict]) -> int:
        """Install a new taxonomy while keeping the old Lists as reference data."""
        with self.connection() as db:
            db.execute("DELETE FROM repo_categories")
            db.execute("DELETE FROM ai_classification")
            db.execute("DELETE FROM categories")
            name_to_id = {}
            colors = ["#62886e", "#6b8aab", "#bd9772", "#9a81a7", "#b38862", "#b87f88", "#829590", "#6d8c8f", "#a28462", "#837fb2"]
            for index, group in enumerate(groups):
                color = colors[index % len(colors)]
                parent_id = "tax-" + uuid.uuid4().hex[:12]
                db.execute("INSERT INTO categories(id,name,parent_id,color,source,created_at) VALUES(?,?,NULL,?,'auto',?)", (parent_id, group["name"], color, now()))
                name_to_id[group["name"]] = parent_id
                for child_name in group["children"]:
                    child_id = "tax-" + uuid.uuid4().hex[:12]
                    db.execute("INSERT INTO categories(id,name,parent_id,color,source,created_at) VALUES(?,?,?,?,?,?)", (child_id, child_name, parent_id, color, "auto", now()))
                    name_to_id[child_name] = child_id
            db.execute("INSERT INTO settings(key,value) VALUES('taxonomy_version','2') ON CONFLICT(key) DO UPDATE SET value='2'")
            return len(name_to_id)

    def categories(self) -> list[dict]:
        with self.connection() as db:
            rows = [dict(row) for row in db.execute("SELECT id,name,parent_id AS parent,color,source,github_id FROM categories ORDER BY rowid")]
            counts = {row["category_id"]: row["n"] for row in db.execute(
                "SELECT category_id,COUNT(*) n FROM repo_categories rc JOIN repos r ON r.id=rc.repo_id WHERE r.is_starred=1 OR r.is_owned=1 GROUP BY category_id"
            )}
        for row in rows:
            row["count"] = counts.get(row["id"], 0)
        return rows

    def repos(self) -> list[dict]:
        with self.connection() as db:
            rows = [dict(row) for row in db.execute("SELECT * FROM repos WHERE is_starred=1 OR is_owned=1 ORDER BY starred_at DESC,id")]
            memberships: dict[str, list[str]] = {}
            tags: dict[str, list[str]] = {}
            for row in db.execute("SELECT rc.repo_id,rc.category_id FROM repo_categories rc JOIN repos r ON r.id=rc.repo_id WHERE r.is_starred=1 OR r.is_owned=1"):
                memberships.setdefault(row["repo_id"], []).append(row["category_id"])
            for row in db.execute("SELECT rt.repo_id,rt.tag FROM repo_tags rt JOIN repos r ON r.id=rt.repo_id WHERE r.is_starred=1 OR r.is_owned=1"):
                tags.setdefault(row["repo_id"], []).append(row["tag"])
        result = []
        for row in rows:
            full_name = row["id"]
            owner, name = full_name.split("/", 1)
            result.append({
                "id": full_name, "owner": owner, "name": name,
                "description": row["description"], "language": row["language"] or "未知",
                "stars": row["stars"], "updated": row["pushed_at"],
                "starred": row["starred_at"], "topics": json.loads(row["topics"]),
                "categories": memberships.get(full_name, []), "tags": tags.get(full_name, []),
                "notes": row["note"], "readme_status": row["readme_status"],
                "default_branch": row["default_branch"],
                "created": row["created_at"], "private": bool(row["is_private"]),
                "is_starred": bool(row["is_starred"]), "is_owned": bool(row["is_owned"]),
                "new_since_sync": bool(row["new_since_sync"]), "archived": bool(row["archived"]),
            })
        return result

    def repo(self, repo_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM repos WHERE id=? AND (is_starred=1 OR is_owned=1)", (repo_id,)).fetchone()
            return dict(row) if row else None

    def readme_pending(self, retry_errors: bool = True) -> list[str]:
        with self.connection() as db:
            statuses = "('pending','error')" if retry_errors else "('pending')"
            return [r[0] for r in db.execute(f"SELECT id FROM repos WHERE (is_starred=1 OR is_owned=1) AND readme_status IN {statuses} ORDER BY starred_at DESC")]

    def set_readme(self, repo_id: str, content: str | None, status: str) -> None:
        with self.connection() as db:
            db.execute("UPDATE repos SET readme=?,readme_status=?,readme_fetched_at=? WHERE id=?", (content, status, now(), repo_id))

    def set_note(self, repo_id: str, note: str) -> None:
        with self.connection() as db:
            if not db.execute("SELECT 1 FROM repos WHERE id=? AND (is_starred=1 OR is_owned=1)", (repo_id,)).fetchone():
                raise KeyError(repo_id)
            db.execute("UPDATE repos SET note=? WHERE id=?", (note, repo_id))

    def set_categories(self, repo_ids: list[str], category_ids: list[str], mode: str = "replace") -> None:
        with self.connection() as db:
            known = {r[0] for r in db.execute("SELECT id FROM categories")}
            if any(x not in known for x in category_ids):
                raise ValueError("未知分类")
            for repo_id in repo_ids:
                if not db.execute("SELECT 1 FROM repos WHERE id=? AND (is_starred=1 OR is_owned=1)", (repo_id,)).fetchone():
                    raise KeyError(repo_id)
                db.execute("INSERT INTO manual_category_edits(repo_id,edited_at) VALUES(?,?) "
                           "ON CONFLICT(repo_id) DO UPDATE SET edited_at=excluded.edited_at",
                           (repo_id, datetime.now(timezone.utc).isoformat(timespec="microseconds")))
                if mode == "replace":
                    db.execute("DELETE FROM repo_categories WHERE repo_id=?", (repo_id,))
                elif mode == "remove":
                    db.executemany("DELETE FROM repo_categories WHERE repo_id=? AND category_id=?", [(repo_id, cat) for cat in category_ids])
                    continue
                elif mode != "add":
                    raise ValueError("无效的分类操作")
                db.executemany("INSERT OR IGNORE INTO repo_categories(repo_id,category_id) VALUES(?,?)", [(repo_id, cat) for cat in category_ids])

    def auto_categorize_if_empty(self, repo_id: str, category_ids: list[str]) -> bool:
        """Add suggestions only while this initial-import item is still unfiled."""
        if not category_ids:
            return False
        with self.connection() as db:
            row = db.execute("SELECT is_starred,new_since_sync FROM repos WHERE id=?", (repo_id,)).fetchone()
            if not row or not row["is_starred"] or row["new_since_sync"]:
                return False
            if db.execute("SELECT 1 FROM repo_categories WHERE repo_id=?", (repo_id,)).fetchone():
                return False
            known = {r[0] for r in db.execute("SELECT id FROM categories")}
            if any(category_id not in known for category_id in category_ids):
                raise ValueError("未知分类")
            db.executemany("INSERT INTO repo_categories(repo_id,category_id) VALUES(?,?)",
                           [(repo_id, category_id) for category_id in dict.fromkeys(category_ids)])
            return True

    def set_tags(self, repo_id: str, tags: list[str]) -> None:
        clean = list(dict.fromkeys(tag.strip()[:40] for tag in tags if tag.strip()))
        with self.connection() as db:
            if not db.execute("SELECT 1 FROM repos WHERE id=? AND (is_starred=1 OR is_owned=1)", (repo_id,)).fetchone():
                raise KeyError(repo_id)
            db.execute("DELETE FROM repo_tags WHERE repo_id=?", (repo_id,))
            db.executemany("INSERT INTO repo_tags(repo_id,tag) VALUES(?,?)", [(repo_id, tag) for tag in clean])

    def create_category(self, name: str, parent: str | None = None, color: str = "#6b8a78", source: str = "local") -> dict:
        name = name.strip()
        if not name or len(name) > 50:
            raise ValueError("分类名称需为 1–50 个字符")
        with self.connection() as db:
            if parent and not db.execute("SELECT 1 FROM categories WHERE id=?", (parent,)).fetchone():
                raise ValueError("上级分类不存在")
            duplicate = db.execute("SELECT 1 FROM categories WHERE lower(name)=lower(?) AND parent_id IS ?", (name, parent)).fetchone()
            if duplicate:
                raise ValueError("同一层级已有此分类")
            category_id = "local-" + uuid.uuid4().hex[:12]
            db.execute("INSERT INTO categories(id,name,parent_id,color,source,created_at) VALUES(?,?,?,?,?,?)", (category_id, name, parent, color, source, now()))
        return {"id": category_id, "name": name, "parent": parent, "color": color, "source": source, "count": 0}

    def update_category(self, category_id: str, name: str, parent: str | None) -> dict:
        name = name.strip()
        if not name or len(name) > 50:
            raise ValueError("分类名称需为 1–50 个字符")
        with self.connection() as db:
            item = db.execute("SELECT id,color,source FROM categories WHERE id=?", (category_id,)).fetchone()
            if not item:
                raise KeyError(category_id)
            if parent:
                if not db.execute("SELECT 1 FROM categories WHERE id=?", (parent,)).fetchone():
                    raise ValueError("上级分类不存在")
                descendant = parent
                while descendant:
                    if descendant == category_id:
                        raise ValueError("分类不能移动到自己的下级")
                    row = db.execute("SELECT parent_id FROM categories WHERE id=?", (descendant,)).fetchone()
                    descendant = row["parent_id"] if row else None
            duplicate = db.execute("SELECT 1 FROM categories WHERE id<>? AND lower(name)=lower(?) AND parent_id IS ?", (category_id, name, parent)).fetchone()
            if duplicate:
                raise ValueError("同一层级已有此分类")
            db.execute("UPDATE categories SET name=?,parent_id=? WHERE id=?", (name, parent, category_id))
            return {"id": category_id, "name": name, "parent": parent,
                    "color": item["color"], "source": item["source"]}

    def delete_category(self, category_id: str, mode: str = "reparent") -> dict:
        """Delete a category, preserving direct children or deleting the whole subtree."""
        if mode not in ("reparent", "subtree"):
            raise ValueError("无效的分类删除方式")
        with self.connection() as db:
            item = db.execute("SELECT parent_id FROM categories WHERE id=?", (category_id,)).fetchone()
            if not item:
                raise KeyError(category_id)
            if mode == "reparent":
                children = [row[0] for row in db.execute("SELECT id FROM categories WHERE parent_id=?", (category_id,))]
                child_names = {row[0].casefold() for row in db.execute(
                    "SELECT name FROM categories WHERE parent_id=?", (category_id,))}
                sibling_names = {row[0].casefold() for row in db.execute(
                    "SELECT name FROM categories WHERE parent_id IS ? AND id<>?", (item["parent_id"], category_id))}
                if child_names & sibling_names:
                    raise ValueError("子分类与上级已有同名分类，请先移动或改名")
                db.execute("UPDATE categories SET parent_id=? WHERE parent_id=?", (item["parent_id"], category_id))
                db.execute("DELETE FROM categories WHERE id=?", (category_id,))
                return {"deleted_ids": [category_id], "moved_children": children}
            pending = [category_id]
            deleted = []
            while pending:
                current = pending.pop()
                deleted.append(current)
                pending.extend(row[0] for row in db.execute("SELECT id FROM categories WHERE parent_id=?", (current,)))
            db.executemany("DELETE FROM categories WHERE id=?", [(item_id,) for item_id in reversed(deleted)])
            return {"deleted_ids": deleted, "moved_children": []}

    def search_readmes(self, query: str) -> set[str]:
        if not query.strip():
            return set()
        pattern = "%" + query.lower().replace("%", "\\%").replace("_", "\\_") + "%"
        with self.connection() as db:
            return {r[0] for r in db.execute("SELECT id FROM repos WHERE (is_starred=1 OR is_owned=1) AND lower(coalesce(readme,'')) LIKE ? ESCAPE '\\'", (pattern,))}

    def clear_new_badges(self) -> None:
        with self.connection() as db:
            db.execute("UPDATE repos SET new_since_sync=0")

    def classification_candidates(self) -> list[dict]:
        with self.connection() as db:
            rows = db.execute(
                """SELECT r.id,r.description,r.language,r.topics,
                          group_concat(c.name, ', ') AS existing
                   FROM repos r LEFT JOIN repo_categories rc ON rc.repo_id=r.id
                   LEFT JOIN categories c ON c.id=rc.category_id
                   LEFT JOIN ai_classification a ON a.repo_id=r.id
                   WHERE r.is_starred=1 AND r.new_since_sync=0 AND a.repo_id IS NULL
                     AND NOT EXISTS (SELECT 1 FROM repo_categories assigned WHERE assigned.repo_id=r.id)
                   GROUP BY r.id ORDER BY r.starred_at DESC"""
            ).fetchall()
            return [{"id": row["id"], "description": row["description"],
                     "language": row["language"], "topics": json.loads(row["topics"]),
                     "existing": row["existing"] or ""} for row in rows]

    def mark_classified(self, repo_ids: list[str]) -> None:
        with self.connection() as db:
            db.executemany(
                "INSERT OR REPLACE INTO ai_classification(repo_id,classified_at) VALUES(?,?)",
                [(repo_id, now()) for repo_id in repo_ids],
            )

    def begin_full_reclassification(self) -> str:
        """Start one resumable pass over every currently starred repository."""
        run_id = uuid.uuid4().hex
        started = datetime.now(timezone.utc).isoformat(timespec="microseconds")
        with self.connection() as db:
            db.execute("INSERT INTO settings(key,value) VALUES('full_classification_run',?) "
                       "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (run_id,))
            db.execute("INSERT INTO settings(key,value) VALUES('full_classification_started',?) "
                       "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (started,))
            db.execute("INSERT INTO settings(key,value) VALUES('initial_classified',?) "
                       "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (now(),))
        return run_id

    def full_classification_candidates(self, run_id: str) -> list[dict]:
        with self.connection() as db:
            rows = db.execute(
                """SELECT r.id,r.description,r.language,r.topics,r.readme,r.readme_status
                   FROM repos r LEFT JOIN full_classification f ON f.repo_id=r.id AND f.run_id=?
                   WHERE r.is_starred=1 AND f.repo_id IS NULL
                   ORDER BY r.starred_at DESC,r.id""", (run_id,),
            ).fetchall()
        return [{**dict(row), "topics": json.loads(row["topics"])} for row in rows]

    def apply_full_classification_batch(self, run_id: str, choices: dict[str, list[str]]) -> int:
        """Replace category memberships and record progress in the same transaction."""
        with self.connection() as db:
            active = db.execute("SELECT value FROM settings WHERE key='full_classification_run'").fetchone()
            if not active or active[0] != run_id:
                raise ValueError("分类任务已被替换")
            started = db.execute("SELECT value FROM settings WHERE key='full_classification_started'").fetchone()[0]
            allowed = {row[0] for row in db.execute("SELECT id FROM categories WHERE parent_id IS NOT NULL")}
            for repo_id, categories in choices.items():
                if not isinstance(categories, list) or len(categories) > 3 or any(cat not in allowed for cat in categories):
                    raise ValueError(f"分类结果包含无效类别：{repo_id}")
                if not db.execute("SELECT 1 FROM repos WHERE id=? AND is_starred=1", (repo_id,)).fetchone():
                    raise KeyError(repo_id)
                manual = db.execute("SELECT edited_at FROM manual_category_edits WHERE repo_id=?", (repo_id,)).fetchone()
                if not manual or manual[0] <= started:
                    db.execute("DELETE FROM repo_categories WHERE repo_id=?", (repo_id,))
                    db.executemany("INSERT INTO repo_categories(repo_id,category_id) VALUES(?,?)",
                                   [(repo_id, cat) for cat in dict.fromkeys(categories)])
                db.execute("INSERT INTO full_classification(repo_id,run_id,classified_at) VALUES(?,?,?) "
                           "ON CONFLICT(repo_id) DO UPDATE SET run_id=excluded.run_id,classified_at=excluded.classified_at",
                           (repo_id, run_id, now()))
        return len(choices)

    def finish_full_reclassification(self, run_id: str) -> None:
        with self.connection() as db:
            active = db.execute("SELECT value FROM settings WHERE key='full_classification_run'").fetchone()
            if not active or active[0] != run_id:
                raise ValueError("分类任务已被替换")
            db.execute("DELETE FROM settings WHERE key='full_classification_run'")
            db.execute("INSERT INTO settings(key,value) VALUES('full_classification_completed',?) "
                       "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (now(),))

    def begin_unclassified_review(self) -> str:
        """Snapshot the size of a new, resumable review of unfiled Stars."""
        run_id = uuid.uuid4().hex
        with self.connection() as db:
            total = db.execute(
                """SELECT COUNT(*) FROM repos r WHERE r.is_starred=1 AND
                   NOT EXISTS (SELECT 1 FROM repo_categories rc WHERE rc.repo_id=r.id)"""
            ).fetchone()[0]
            db.execute("INSERT INTO settings(key,value) VALUES('unclassified_review_run',?) "
                       "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (run_id,))
            db.execute("INSERT INTO settings(key,value) VALUES('unclassified_review_total',?) "
                       "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(total),))
        return run_id

    def unclassified_review_candidates(self, run_id: str) -> list[dict]:
        with self.connection() as db:
            rows = db.execute(
                """SELECT r.id,r.description,r.language,r.topics,r.readme,r.readme_status
                   FROM repos r LEFT JOIN unclassified_reviews ur
                     ON ur.repo_id=r.id AND ur.run_id=?
                   WHERE r.is_starred=1 AND ur.repo_id IS NULL
                     AND NOT EXISTS (SELECT 1 FROM repo_categories rc WHERE rc.repo_id=r.id)
                   ORDER BY r.starred_at DESC,r.id""", (run_id,),
            ).fetchall()
        return [{**dict(row), "topics": json.loads(row["topics"])} for row in rows]

    def apply_unclassified_review_batch(self, run_id: str, choices: dict[str, list[str]]) -> int:
        """Assign only still-unfiled repos, recording empty results as reviewed."""
        assigned = 0
        with self.connection() as db:
            active = db.execute("SELECT value FROM settings WHERE key='unclassified_review_run'").fetchone()
            if not active or active[0] != run_id:
                raise ValueError("未分类复核任务已被替换")
            allowed = {row[0] for row in db.execute("SELECT id FROM categories WHERE parent_id IS NOT NULL")}
            for repo_id, category_ids in choices.items():
                if not isinstance(category_ids, list) or len(category_ids) > 3 or any(
                    not isinstance(category_id, str) or category_id not in allowed for category_id in category_ids
                ):
                    raise ValueError(f"分类结果包含无效类别：{repo_id}")
                if not db.execute("SELECT 1 FROM repos WHERE id=? AND is_starred=1", (repo_id,)).fetchone():
                    raise KeyError(repo_id)
                unfiled = not db.execute("SELECT 1 FROM repo_categories WHERE repo_id=?", (repo_id,)).fetchone()
                if unfiled and category_ids:
                    db.executemany("INSERT INTO repo_categories(repo_id,category_id) VALUES(?,?)",
                                   [(repo_id, category_id) for category_id in dict.fromkeys(category_ids)])
                    assigned += 1
                db.execute("INSERT INTO unclassified_reviews(repo_id,run_id,reviewed_at,suggested_categories) "
                           "VALUES(?,?,?,?) ON CONFLICT(repo_id) DO UPDATE SET "
                           "run_id=excluded.run_id,reviewed_at=excluded.reviewed_at,"
                           "suggested_categories=excluded.suggested_categories",
                           (repo_id, run_id, now(), json.dumps(category_ids)))
        return assigned

    def finish_unclassified_review(self, run_id: str) -> None:
        with self.connection() as db:
            active = db.execute("SELECT value FROM settings WHERE key='unclassified_review_run'").fetchone()
            if not active or active[0] != run_id:
                raise ValueError("未分类复核任务已被替换")
            db.execute("DELETE FROM settings WHERE key='unclassified_review_run'")
            db.execute("INSERT INTO settings(key,value) VALUES('unclassified_review_completed',?) "
                       "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (now(),))

    def begin_owned_review(self) -> str:
        """Queue new or changed owned repositories for a resumable classification pass."""
        with self.connection() as db:
            active = db.execute("SELECT value FROM settings WHERE key='owned_review_run'").fetchone()
            if active:
                return active[0]
            total = db.execute(
                """SELECT COUNT(*) FROM repos r LEFT JOIN owned_reviews o ON o.repo_id=r.id
                   WHERE r.is_owned=1 AND (o.repo_id IS NULL OR o.pushed_at<>r.pushed_at
                     OR o.readme_status<>r.readme_status)"""
            ).fetchone()[0]
            if not total:
                return ""
            run_id = uuid.uuid4().hex
            started = datetime.now(timezone.utc).isoformat(timespec="microseconds")
            db.execute("INSERT INTO settings(key,value) VALUES('owned_review_run',?) "
                       "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (run_id,))
            db.execute("INSERT INTO settings(key,value) VALUES('owned_review_total',?) "
                       "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(total),))
            db.execute("INSERT INTO settings(key,value) VALUES('owned_review_started',?) "
                       "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (started,))
            return run_id

    def owned_review_candidates(self, run_id: str) -> list[dict]:
        with self.connection() as db:
            rows = db.execute(
                """SELECT r.id,r.description,r.language,r.topics,r.readme,r.readme_status
                   FROM repos r LEFT JOIN owned_reviews o ON o.repo_id=r.id
                   WHERE r.is_owned=1 AND (o.repo_id IS NULL OR o.pushed_at<>r.pushed_at
                     OR o.readme_status<>r.readme_status)
                   ORDER BY r.pushed_at DESC,r.id"""
            ).fetchall()
            result = []
            for row in rows:
                item = {**dict(row), "topics": json.loads(row["topics"])}
                item["existing"] = [dict(cat) for cat in db.execute(
                    """SELECT c.id,c.name FROM repo_categories rc JOIN categories c ON c.id=rc.category_id
                       WHERE rc.repo_id=? ORDER BY c.name""", (row["id"],))]
                result.append(item)
            return result

    def apply_owned_review_batch(self, run_id: str, choices: dict[str, list[str]]) -> int:
        """Add clear new categories while preserving earlier labels and concurrent edits."""
        assigned = 0
        with self.connection() as db:
            active = db.execute("SELECT value FROM settings WHERE key='owned_review_run'").fetchone()
            if not active or active[0] != run_id:
                raise ValueError("我的项目分类任务已被替换")
            started = db.execute("SELECT value FROM settings WHERE key='owned_review_started'").fetchone()[0]
            allowed = {row[0] for row in db.execute("SELECT id FROM categories WHERE parent_id IS NOT NULL")}
            for repo_id, category_ids in choices.items():
                if not isinstance(category_ids, list) or len(category_ids) > 3 or any(
                    not isinstance(cat, str) or cat not in allowed for cat in category_ids
                ):
                    raise ValueError(f"分类结果包含无效类别：{repo_id}")
                repo = db.execute("SELECT pushed_at,readme_status FROM repos WHERE id=? AND is_owned=1", (repo_id,)).fetchone()
                if not repo:
                    raise KeyError(repo_id)
                manual = db.execute("SELECT edited_at FROM manual_category_edits WHERE repo_id=?", (repo_id,)).fetchone()
                if not manual or manual[0] <= started:
                    existing = {row[0] for row in db.execute(
                        "SELECT category_id FROM repo_categories WHERE repo_id=?", (repo_id,))}
                    additions = [cat for cat in dict.fromkeys(category_ids) if cat not in existing]
                    db.executemany("INSERT INTO repo_categories(repo_id,category_id) VALUES(?,?)",
                                   [(repo_id, cat) for cat in additions])
                    assigned += bool(additions)
                db.execute("INSERT INTO owned_reviews(repo_id,run_id,pushed_at,readme_status,reviewed_at) VALUES(?,?,?,?,?) "
                           "ON CONFLICT(repo_id) DO UPDATE SET run_id=excluded.run_id,"
                           "pushed_at=excluded.pushed_at,readme_status=excluded.readme_status,"
                           "reviewed_at=excluded.reviewed_at",
                           (repo_id, run_id, repo["pushed_at"], repo["readme_status"], now()))
        return assigned

    def finish_owned_review(self, run_id: str) -> None:
        with self.connection() as db:
            active = db.execute("SELECT value FROM settings WHERE key='owned_review_run'").fetchone()
            if not active or active[0] != run_id:
                raise ValueError("我的项目分类任务已被替换")
            db.execute("DELETE FROM settings WHERE key='owned_review_run'")
            db.execute("INSERT INTO settings(key,value) VALUES('owned_review_completed',?) "
                       "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (now(),))
