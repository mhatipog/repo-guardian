import datetime as dt
import json
import unittest
from repoguardian.controller import Refused, digest, parse_intent, review_status, safe_repo


class GuardianTests(unittest.TestCase):
    def parse(self, value):
        return parse_intent(json.dumps(value))

    def test_create_private(self):
        v = self.parse({'version': 1, 'action': 'create_repo', 'name': 'test-42', 'visibility': 'private'})
        self.assertEqual(v['name'], 'test-42')

    def test_reject_untrusted_fields(self):
        with self.assertRaises(Refused):
            self.parse({'version': 1, 'action': 'create_repo', 'name': 'test',
                        'visibility': 'private', 'shell': 'curl bad'})

    def test_visibility_identity_required(self):
        with self.assertRaises(Refused):
            self.parse({'version': 1, 'action': 'visibility', 'repo': 'mhatipog/example',
                        'visibility': 'public', 'expected_visibility': 'private'})

    def test_prevent_other_owner(self):
        with self.assertRaises(Refused):
            self.parse({'version': 1, 'action': 'visibility', 'repo': 'someone/example',
                        'visibility': 'public', 'expected_visibility': 'private',
                        'expected_repo_id': 123})

    def test_reject_path_or_api_injection(self):
        for r in ['x/y/z', '../repo', 'user/../admin', 'user/%2F',
                  'https://example.com/x']:
            with self.assertRaises(Refused):
                safe_repo(r)

    def test_hash_independent_of_json_key_order(self):
        self.assertEqual(digest({'name': 'x', 'action': 'fork'}),
                         digest({'action': 'fork', 'name': 'x'}))

    def test_missing_deadline(self):
        now = dt.datetime(2026, 11, 10, 10, tzinfo=dt.timezone.utc)
        intent = {'version': 1, 'action': 'visibility', 'repo': 'mhatipog/test',
                  'visibility': 'public', 'expected_repo_id': 1,
                  'expected_visibility': 'private', 'at': '2026-11-10T09:00:00Z'}
        self.assertEqual(review_status(intent, now), 'missed')
        intent['visibility'] = 'private'
        self.assertEqual(review_status(intent, now), 'ready')

    def test_future(self):
        now = dt.datetime(2026, 11, 10, 7, tzinfo=dt.timezone.utc)
        self.assertEqual(review_status({
            'at': '2026-11-10T09:00:00Z', 'action': 'visibility',
            'visibility': 'public'}, now), 'waiting')

    def test_invalid_date(self):
        with self.assertRaises(Refused):
            self.parse({'version': 1, 'action': 'create_repo', 'name': 'test',
                        'visibility': 'private', 'at': '2026-13-10T09:00:00Z'})


if __name__ == '__main__':
    unittest.main()
