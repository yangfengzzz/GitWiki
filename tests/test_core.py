import tempfile
import unittest
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

from gitwiki.classifier import classify_locally, classify_with_codex, reclassify_all_with_codex, review_unclassified_with_codex, review_owned_with_codex
from gitwiki.github import GitHubClient
from gitwiki.store import Store, now
from gitwiki.sync import SyncManager


def star(name, description="", topics=None, starred_at="2026-01-01T00:00:00Z", pushed_at="2026-01-02T00:00:00Z"):
    return {"starred_at": starred_at, "repo": {"full_name": name, "id": abs(hash(name)) % 1000000,
            "description": description, "language": "Python", "stargazers_count": 7,
            "pushed_at": pushed_at, "topics": topics or [], "default_branch": "main"}}


def owned(name, description="", pushed_at="2026-01-02T00:00:00Z", private=False):
    return {"full_name": name, "id": abs(hash(name)) % 1000000,
            "description": description, "language": "Python", "stargazers_count": 7,
            "pushed_at": pushed_at, "created_at": "2025-12-01T00:00:00Z",
            "topics": [], "default_branch": "main", "private": private}


class StoreFlowTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Store(Path(self.directory.name) / "test.sqlite3")

    def test_sync_preserves_annotations_and_detects_new_and_removed_stars(self):
        store = self.store
        store.replace_stars([star("owner/one")])
        category = store.create_category("My category")
        store.set_categories(["owner/one"], [category["id"]])
        store.set_tags("owner/one", ["useful"])
        store.set_note("owner/one", "Try this later")
        store.set_readme("owner/one", "# One", "ready")
        store.set_setting("last_sync", "2026-01-01T00:00:00Z")
        result = store.replace_stars([star("owner/one", "Updated"), star("owner/two")])
        self.assertEqual(result, {"total": 2, "new": 1, "removed": 0})
        one = next(item for item in store.repos() if item["id"] == "owner/one")
        two = next(item for item in store.repos() if item["id"] == "owner/two")
        self.assertEqual(one["categories"], [category["id"]])
        self.assertEqual(one["tags"], ["useful"])
        self.assertEqual(one["notes"], "Try this later")
        self.assertEqual(one["readme_status"], "ready")
        self.assertEqual(one["description"], "Updated")
        self.assertTrue(two["new_since_sync"])
        store.replace_stars([star("owner/one", pushed_at="2026-02-01T00:00:00Z"), star("owner/two")])
        self.assertEqual(store.repo("owner/one")["readme_status"], "pending")
        removed = store.replace_stars([star("owner/two")])
        self.assertEqual(removed["removed"], 1)
        self.assertEqual([item["id"] for item in store.repos()], ["owner/two"])

    def test_owned_sync_merges_starred_repos_without_losing_annotations(self):
        store = self.store
        store.replace_stars([star("me/shared")])
        category = store.create_category("Robotics")
        store.set_categories(["me/shared"], [category["id"]])
        store.set_note("me/shared", "keep my note")
        store.set_readme("me/shared", "# Shared", "ready")
        result = store.replace_owned_repos([owned("me/shared"), owned("me/private", private=True)])
        self.assertEqual(result, {"total": 2, "new": 2, "added": 1, "removed": 0, "overlap": 1})
        repos = {item["id"]: item for item in store.repos()}
        self.assertEqual(len(repos), 2)
        self.assertTrue(repos["me/shared"]["is_starred"] and repos["me/shared"]["is_owned"])
        self.assertEqual(repos["me/shared"]["categories"], [category["id"]])
        self.assertEqual(repos["me/shared"]["notes"], "keep my note")
        self.assertEqual(repos["me/shared"]["readme_status"], "ready")
        self.assertTrue(repos["me/private"]["private"])
        self.assertFalse(repos["me/private"]["is_starred"])
        store.set_note("me/private", "private note")
        store.replace_owned_repos([owned("me/shared")])
        self.assertEqual([item["id"] for item in store.repos()], ["me/shared"])
        store.replace_stars([])
        self.assertEqual([item["id"] for item in store.repos()], ["me/shared"])
        self.assertFalse(store.repos()[0]["is_starred"])
        store.replace_owned_repos([owned("me/shared", pushed_at="2026-02-01T00:00:00Z")])
        self.assertEqual(store.repo("me/shared")["readme_status"], "pending")

    def test_owned_review_migration_keeps_completed_readme_review(self):
        self.store.replace_owned_repos([owned("me/project")])
        self.store.set_readme("me/project", "# Project", "ready")
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO owned_reviews(repo_id,run_id,pushed_at,readme_status,reviewed_at) "
                "VALUES(?,?,?,?,?)",
                ("me/project", "previous", "2026-01-02T00:00:00Z", "", now()),
            )
        reopened = Store(self.store.path)
        self.assertEqual(reopened.begin_owned_review(), "")

    def test_owned_api_paginates_and_excludes_organization_repos(self):
        client = GitHubClient(token="test")
        pages = []

        def rest(path):
            pages.append(path)
            if "page=1&" in path:
                return [{"owner": {"login": "me"}, "full_name": f"me/repo-{i}"} for i in range(99)] + [
                    {"owner": {"login": "an-org"}, "full_name": "an-org/repo"}]
            return [{"owner": {"login": "me"}, "full_name": "me/last"}]

        client.rest = rest
        result = client.fetch_owned_repos("me")
        self.assertEqual(len(result), 100)
        self.assertEqual(len(pages), 2)
        self.assertTrue(all(repo["full_name"].startswith("me/") for repo in result))

    def test_old_lists_are_reference_only_and_new_stars_stay_in_inbox(self):
        store = self.store
        store.replace_stars([star("owner/vla-tool", "An openvla robot policy", ["vla"])])
        store.import_lists([{"id": "legacy1", "name": "Old robotics", "repos": ["owner/vla-tool"]}])
        store.replace_taxonomy([{"name": "Robot learning", "children": ["视觉语言动作模型"]}])
        self.assertEqual(store.repos()[0]["categories"], [])
        self.assertEqual(store.reference_summary()[0]["count"], 1)
        result = classify_locally(store)
        self.assertEqual(result["assigned"], 1)
        self.assertEqual(len(store.repos()[0]["categories"]), 1)
        store.set_setting("last_sync", "2026-01-01T00:00:00Z")
        store.replace_stars([star("owner/vla-tool"), star("owner/new-vla", "New vla project", ["vla"])])
        classify_locally(store)
        new = next(item for item in store.repos() if item["id"] == "owner/new-vla")
        self.assertEqual(new["categories"], [])

    def test_category_management_preserves_tree_and_removes_membership(self):
        store = self.store
        store.replace_stars([star("owner/one")])
        root = store.create_category("Root")
        child = store.create_category("Child", root["id"])
        store.set_categories(["owner/one"], [child["id"]])
        with self.assertRaises(ValueError):
            store.update_category(root["id"], "Root", child["id"])
        renamed = store.update_category(child["id"], "Renamed", root["id"])
        self.assertEqual((renamed["name"], renamed["parent"]), ("Renamed", root["id"]))
        result = store.delete_category(root["id"])
        self.assertEqual(result, {"deleted_ids": [root["id"]], "moved_children": [child["id"]]})
        self.assertIsNone(next(cat for cat in store.categories() if cat["id"] == child["id"])["parent"])
        self.assertEqual(store.repos()[0]["categories"], [child["id"]])
        store.delete_category(child["id"])
        self.assertEqual(store.repos()[0]["categories"], [])

    def test_delete_category_subtree_orphans_only_projects_without_other_categories(self):
        store = self.store
        store.replace_stars([star("owner/one"), star("owner/two")])
        root = store.create_category("Root")
        child = store.create_category("Child", root["id"])
        grandchild = store.create_category("Grandchild", child["id"])
        other = store.create_category("Other")
        store.set_categories(["owner/one", "owner/two"], [grandchild["id"]])
        store.set_categories(["owner/two"], [other["id"]], "add")
        result = store.delete_category(root["id"], "subtree")
        self.assertEqual(set(result["deleted_ids"]), {root["id"], child["id"], grandchild["id"]})
        repos = {item["id"]: item for item in store.repos()}
        self.assertEqual(repos["owner/one"]["categories"], [])
        self.assertEqual(repos["owner/two"]["categories"], [other["id"]])

    def test_readme_cache_processes_all_pending_repositories(self):
        store = self.store
        store.replace_stars([star(f"owner/repo-{index}") for index in range(12)])

        class FakeClient:
            def fetch_readme(self, repo_id):
                return f"# {repo_id}", "ready"

        manager = SyncManager(store, FakeClient())
        manager._cache_readmes()
        self.assertEqual(manager.readmes.phase, "complete")
        self.assertEqual(manager.readmes.current, 12)
        self.assertEqual(store.readme_pending(), [])

    def test_codex_receives_readme_for_blank_description(self):
        store = self.store
        store.replace_stars([star("owner/opaque-name")])
        store.replace_taxonomy([{"name": "机器人导航", "children": ["视觉SLAM"]}])
        category_id = next(cat["id"] for cat in store.categories() if cat["name"] == "视觉SLAM")
        prompts = []

        class FakeClient:
            def fetch_readme(self, repo_id):
                self_id = repo_id
                assert self_id == "owner/opaque-name"
                return "# Visual SLAM\nCamera localization and mapping.", "ready"

        class FakeThread:
            def run(self, prompt):
                prompts.append(prompt)
                return types.SimpleNamespace(final_response=json.dumps({"owner/opaque-name": [category_id]}))

        class FakeCodex:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def thread_start(self, sandbox): return FakeThread()

        fake_module = types.SimpleNamespace(Codex=FakeCodex, Sandbox=types.SimpleNamespace(read_only="read_only"))
        with patch.dict(sys.modules, {"openai_codex": fake_module}):
            self.assertEqual(classify_with_codex(store, FakeClient()), 1)
        self.assertIn("Visual SLAM", prompts[0])
        self.assertEqual(store.repos()[0]["categories"], [category_id])

    def test_auto_category_does_not_change_manual_assignment(self):
        store = self.store
        store.replace_stars([star("owner/one")])
        manual = store.create_category("Manual")
        suggested = store.create_category("Suggested")
        store.set_categories(["owner/one"], [manual["id"]])
        self.assertFalse(store.auto_categorize_if_empty("owner/one", [suggested["id"]]))
        self.assertEqual(store.repos()[0]["categories"], [manual["id"]])

    def test_full_reclassification_replaces_old_labels_and_resumes(self):
        store = self.store
        ids = ["owner/one", "owner/two", "owner/three"]
        store.replace_stars([star(repo_id) for repo_id in ids])
        root = store.create_category("Tools")
        old = store.create_category("Old", root["id"])
        robot = store.create_category("Robots", root["id"])
        simulation = store.create_category("Simulation", root["id"])
        store.set_categories(ids, [old["id"]])
        store.set_note(ids[0], "keep this note")
        store.set_tags(ids[0], ["favorite"])
        for repo_id in ids:
            store.set_readme(repo_id, "# Robot simulator\nA robotics platform with a physics simulation environment.", "ready")
        run_id = store.begin_full_reclassification()
        prompts = []

        class FakeThread:
            def run(self, prompt):
                prompts.append(prompt)
                repo_ids = [repo_id for repo_id in ids if f'"id": "{repo_id}"' in prompt]
                return types.SimpleNamespace(final_response=json.dumps(
                    {repo_id: [robot["id"], simulation["id"]] for repo_id in repo_ids}))

        class FakeCodex:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def thread_start(self, sandbox): return FakeThread()

        fake_module = types.SimpleNamespace(Codex=FakeCodex, Sandbox=types.SimpleNamespace(read_only="read_only"))
        with patch.dict(sys.modules, {"openai_codex": fake_module}):
            self.assertEqual(reclassify_all_with_codex(store, batch_size=2, max_items=2), 2)
            self.assertEqual(len(store.full_classification_candidates(run_id)), 1)
            self.assertEqual(reclassify_all_with_codex(store, batch_size=2), 3)
        self.assertIn("Robot simulator", prompts[0])
        self.assertNotIn(old["id"], prompts[0].split("仓库资料：", 1)[1])
        for item in store.repos():
            self.assertEqual(set(item["categories"]), {robot["id"], simulation["id"]})
        first = next(item for item in store.repos() if item["id"] == ids[0])
        self.assertEqual(first["notes"], "keep this note")
        self.assertEqual(first["tags"], ["favorite"])
        self.assertEqual(store.setting("full_classification_run"), "")

    def test_manual_category_edit_during_full_run_is_preserved(self):
        store = self.store
        store.replace_stars([star("owner/one")])
        root = store.create_category("Tools")
        manual = store.create_category("Manual", root["id"])
        proposed = store.create_category("Proposed", root["id"])
        run_id = store.begin_full_reclassification()
        store.set_categories(["owner/one"], [manual["id"]])
        store.apply_full_classification_batch(run_id, {"owner/one": [proposed["id"]]})
        self.assertEqual(store.repos()[0]["categories"], [manual["id"]])

    def test_unclassified_review_assigns_only_supported_items_and_resumes(self):
        store = self.store
        ids = ["owner/robot-sim", "owner/geometry", "owner/opaque"]
        store.replace_stars([star(repo_id) for repo_id in ids])
        root = store.create_category("New topics")
        geometry = store.create_category("Geometry", root["id"])
        simulation = store.create_category("Simulation", root["id"])
        store.set_readme(ids[0], "# Robot simulator\nGeometry and physics simulation.", "ready")
        store.set_readme(ids[1], "# Geometry\nA library for mesh processing.", "ready")
        store.set_readme(ids[2], None, "missing")
        store.set_note(ids[0], "keep")
        run_id = store.begin_unclassified_review()
        prompts = []

        class FakeThread:
            def run(self, prompt):
                prompts.append(prompt)
                choices = {}
                for repo_id in ids:
                    if f'"id": "{repo_id}"' in prompt:
                        choices[repo_id] = ([geometry["id"], simulation["id"]] if repo_id == ids[0]
                                            else [geometry["id"]] if repo_id == ids[1] else [])
                return types.SimpleNamespace(final_response=json.dumps(choices))

        class FakeCodex:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def thread_start(self, sandbox): return FakeThread()

        fake_module = types.SimpleNamespace(Codex=FakeCodex, Sandbox=types.SimpleNamespace(read_only="read_only"))
        with patch.dict(sys.modules, {"openai_codex": fake_module}):
            self.assertEqual(review_unclassified_with_codex(store, batch_size=2, max_items=2), 2)
            self.assertEqual(len(store.unclassified_review_candidates(run_id)), 1)
            self.assertEqual(review_unclassified_with_codex(store, batch_size=2), 3)
        self.assertTrue(any("Robot simulator" in prompt for prompt in prompts))
        repo_map = {item["id"]: item for item in store.repos()}
        self.assertEqual(set(repo_map[ids[0]]["categories"]), {geometry["id"], simulation["id"]})
        self.assertEqual(repo_map[ids[1]]["categories"], [geometry["id"]])
        self.assertEqual(repo_map[ids[2]]["categories"], [])
        self.assertEqual(repo_map[ids[0]]["notes"], "keep")
        self.assertEqual(store.setting("unclassified_review_run"), "")

    def test_unclassified_review_keeps_category_added_during_run(self):
        store = self.store
        store.replace_stars([star("owner/one")])
        root = store.create_category("Topics")
        manual = store.create_category("Manual", root["id"])
        proposed = store.create_category("Proposed", root["id"])
        run_id = store.begin_unclassified_review()
        store.set_categories(["owner/one"], [manual["id"]])
        self.assertEqual(store.apply_unclassified_review_batch(run_id, {"owner/one": [proposed["id"]]}), 0)
        self.assertEqual(store.repos()[0]["categories"], [manual["id"]])

    def test_owned_review_uses_readme_and_adds_to_existing_categories(self):
        store = self.store
        store.replace_stars([star("me/shared")])
        store.replace_owned_repos([owned("me/shared"), owned("me/robot")])
        root = store.create_category("Robotics")
        platform = store.create_category("Platform", root["id"])
        navigation = store.create_category("Navigation", root["id"])
        store.set_categories(["me/shared"], [platform["id"]])
        store.set_readme("me/shared", "# Robot platform\nSupports autonomous navigation.", "ready")
        store.set_readme("me/robot", "# Navigation\nAutonomous robot navigation.", "ready")
        run_id = store.begin_owned_review()
        prompts = []

        class FakeThread:
            def run(self, prompt):
                prompts.append(prompt)
                choices = {}
                for repo_id in ("me/shared", "me/robot"):
                    if f'"id": "{repo_id}"' in prompt:
                        choices[repo_id] = [navigation["id"]]
                return types.SimpleNamespace(final_response=json.dumps(choices))

        class FakeCodex:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def thread_start(self, sandbox): return FakeThread()

        fake_module = types.SimpleNamespace(Codex=FakeCodex, Sandbox=types.SimpleNamespace(read_only="read_only"))
        with patch.dict(sys.modules, {"openai_codex": fake_module}):
            self.assertEqual(review_owned_with_codex(store, batch_size=1, max_items=1), 1)
            self.assertEqual(len(store.owned_review_candidates(run_id)), 1)
            self.assertEqual(review_owned_with_codex(store, batch_size=1), 2)
        repos = {item["id"]: item for item in store.repos()}
        self.assertEqual(set(repos["me/shared"]["categories"]), {platform["id"], navigation["id"]})
        self.assertEqual(repos["me/robot"]["categories"], [navigation["id"]])
        self.assertIn("Supports autonomous navigation", "\n".join(prompts))
        self.assertEqual(store.setting("owned_review_run"), "")
        self.assertEqual(store.begin_owned_review(), "")
        store.set_readme("me/robot", None, "missing")
        self.assertTrue(store.begin_owned_review())


if __name__ == "__main__":
    unittest.main()
