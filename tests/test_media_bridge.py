"""Small boundary tests for the ephemeral private MP3 relay."""
import base64
import hashlib
import unittest
from unittest.mock import patch

from repoguardian.controller import Control, parse_intent, Refused, digest
from repoguardian.media_bridge import MediaPending, MediaRefused, assemble, stage, verify_staged


def fixture(data=b"ID3" + b"original-audio-bytes" * 64):
    command = {"version": 1, "action": "stage_social_audio",
               "repo": "mhatipog/web-operations", "brand": "gratistools",
               "sha256": hashlib.sha256(data).hexdigest(),
               "size_bytes": len(data), "chunks": 2}
    encoded = base64.b64encode(data).decode()
    mid = len(encoded) // 2
    mid -= mid % 4
    chunks = [
        {"id": 101, "user": {"login": "mhatipog"},
         "body": "RG_MEDIA_CHUNK 1/2\n" + encoded[:mid]},
        {"id": 102, "user": {"login": "mhatipog"},
         "body": "RG_MEDIA_CHUNK 2/2\n" + encoded[mid:]},
    ]
    return command, chunks


class MediaRelayTests(unittest.TestCase):
    def test_strict_destination_and_sha(self):
        v, chunks = fixture()
        self.assertEqual(parse_intent(__import__("json").dumps(v))["brand"], "gratistools")
        for bad in (
            {**v, "repo": "mhatipog/repo-guardian"},
            {**v, "brand": "other"},
            {**v, "sha256": "xyz"},
            {**v, "shell": "sh -c whoami"},
        ):
            with self.assertRaises(Refused):
                parse_intent(__import__("json").dumps(bad))

    def test_chunk_completion_and_hash(self):
        v, chunks = fixture()
        with self.assertRaises(MediaPending):
            assemble(v, chunks[:1], "mhatipog")
        data, ids = assemble(v, chunks, "mhatipog")
        self.assertEqual(hashlib.sha256(data).hexdigest(), v["sha256"])
        self.assertEqual(ids, [101, 102])
        with self.assertRaises(MediaRefused):
            assemble(v, [chunks[0], chunks[0]], "mhatipog")
        tampered = [dict(chunks[0]), chunks[1]]
        tampered[0]["body"] = tampered[0]["body"].replace("SUQz", "AAAA")
        with self.assertRaises(MediaRefused):
            assemble(v, tampered, "mhatipog")
        tampered = [dict(chunks[0]), chunks[1]]
        tampered[0]["user"] = {"login": "stranger"}
        with self.assertRaises(MediaRefused):
            assemble(v, tampered, "mhatipog")

    def test_stage_is_private_only_and_verifies_asset(self):
        v, chunks = fixture()
        data, _ = assemble(v, chunks, "mhatipog")
        asset_id = 345678
        calls = []
        def fake_admin(method, path, payload=None):
            calls.append((method, path))
            if path == "/repos/mhatipog/web-operations":
                return {"id": 1, "full_name": v["repo"], "private": True,
                        "fork": False, "archived": False, "default_branch": "main"}
            if path.endswith("/releases/tags/social-audio-inputs"):
                return {"tag_name": "social-audio-inputs", "id": 12}
            if path.endswith("/releases/12/assets?per_page=100&page=1"):
                return []
            if path.endswith("/releases/assets/" + str(asset_id)):
                return {"id": asset_id, "name": "gratistools-" + v["sha256"] + ".mp3",
                        "size": len(data), "state": "uploaded"}
            raise AssertionError(path)
        uploaded = []
        def uploader(token, repo, release, filename, data):
            uploaded.append((repo, release, filename, len(data)))
            return {"id": asset_id}
        result = stage(v, data, fake_admin, "test-token", "mhatipog", uploader)
        self.assertEqual(result["assetId"], asset_id)
        self.assertEqual(len(uploaded), 1)
        self.assertEqual(verify_staged(v, result, fake_admin, "mhatipog"), result)
        def public_admin(method, path, payload=None):
            if path == "/repos/mhatipog/web-operations":
                return {**fake_admin(method, path), "private": False}
            return fake_admin(method, path, payload)
        with self.assertRaises(MediaRefused):
            stage(v, data, public_admin, "test-token", "mhatipog", uploader)

    def test_controller_waits_for_chunks_without_failing(self):
        v, chunks = fixture()
        c = Control("issue-token", "admin-token")
        issue = {"state": "open", "number": 42, "title": "RG: stage",
                 "body": __import__("json").dumps(v), "user": {"login": "mhatipog"}}
        with patch.object(c, "issue_get", return_value=issue), patch.object(c, "comments", return_value=chunks[:1]), patch.object(c, "comment") as comment:
            c.process_issue(42)
            comment.assert_not_called()

    def test_checkpoint_scrubs_and_recovers(self):
        v, chunks = fixture()
        c = Control("issue-token", "admin-token")
        staged = {"assetId": 345678, "sha256": v["sha256"], "startSeconds": 0}
        checkpoint = {"id": 103, "user": {"login": "github-actions[bot]"},
                      "body": "RG_STAGED " + digest(v) + "\n" + __import__("json").dumps(staged)}
        deleted = []
        def fake_issue(path, method="GET", payload=None):
            if method == "DELETE":
                deleted.append(path)
                return {}
            raise AssertionError(path)
        with patch.object(c, "issue_get", side_effect=fake_issue), patch.object(c, "admin") as admin:
            admin.return_value = {"id": staged["assetId"], "size": v["size_bytes"],
                                  "name": "gratistools-" + v["sha256"] + ".mp3"}
            result = c.stage_from_issue(v, 42, chunks + [checkpoint], digest(v))
        self.assertIn("audioTrack", result)
        self.assertEqual(deleted, ["/issues/comments/101", "/issues/comments/102"])


if __name__ == "__main__":
    unittest.main()
