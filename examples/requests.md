# Copyable ChatGPT → GitHub controller JSON

Use as the complete body of a private `RG:` issue. No `APPROVE` comments.

Add public GitHub discoverability topics:
```json
{"version":1,"action":"topics","repo":"mhatipog/repo-guardian","names":["chatgpt","github-automation","github-api","github-actions","ai-agents","repository-management","open-source","python"],"mode":"add"}
```

Create private research repo:
```json
{"version":1,"action":"create_repo","name":"research-r82","visibility":"private"}
```

Make a true public fork:
```json
{"version":1,"action":"fork","source":"octocat/Hello-World","name":"hello-world-public-fork"}
```

Create a **private standalone copy**, retaining Git history without upstream fork association:
```json
{"version":1,"action":"private_copy","source":"octocat/Hello-World","name":"repo-guardian-smoke-private-copy"}
```

Schedule visibility from private to public (first inspect real repo ID):
```json
{"version":1,"action":"visibility","repo":"mhatipog/research-r82","visibility":"public","expected_repo_id":12345678,"expected_visibility":"private","acknowledge_public_exposure":true,"at":"2026-11-10T09:00:00Z"}
```

Bring back to private (does not undo public exposure):
```json
{"version":1,"action":"visibility","repo":"mhatipog/research-r82","visibility":"private","expected_repo_id":12345678,"expected_visibility":"public","at":"2026-11-11T09:00:00Z"}
```


Open a PR from your reviewed public fork when the installed GitHub connector lacks upstream write permission:

```json
{"version":1,"action":"open_pr","fork":"mhatipog/example-fork","upstream":"upstream/project","head":"fix/example","base":"main","expected_head_sha":"0123456789abcdef0123456789abcdef01234567","title":"Fix a reproducible bug","body":"Describe the problem, tests and upgrade risks.","draft":false,"acknowledge_public_exposure":true}
```

The controller verifies the fork/upstream relationship and the exact head commit before publication, rejects arbitrary upstream repositories and stale branches, and verifies the created PR.


Update the description of an existing, owner-authored upstream PR without posting comments. Copy the exact current PR body into `expected_body` so a concurrent edit is refused, and set `body` to the reviewed replacement. Keep the same verified fork and head SHA:

```json
{"version":1,"action":"update_pr_body","fork":"mhatipog/example-fork","upstream":"upstream/project","pr_number":123,"expected_head_sha":"0123456789abcdef0123456789abcdef01234567","expected_body":"Current PR description from GitHub","body":"Reviewed replacement PR description","acknowledge_public_exposure":true}
```

The controller verifies the owner's personal token, upstream/fork relationship, PR author and state, exact head SHA, and exact old body before editing; it re-reads the result and never posts a public comment.

Update an existing repo description/homepage (no visibility change):
```json
{"version":1,"action":"metadata","repo":"mhatipog/umig6-metering-quality","expected_repo_id":1435626896,"description":"PySpark metering data quality, source provenance, quarantine and legacy MIG6 migration readiness for Belgian energy pipelines","homepage":"https://github.com/mhatipog/umig6-metering-quality/tree/main/docs/HANDOFF.md"}
```

Repo Guardian creates upstream PRs **ready for review**. Omit `draft` or supply `"draft":false`; requests with `"draft":true` are rejected. It authenticates the publishing PAT as the account owner, never posts on upstream conversations using the GitHub Actions bot, and avoids linkable public PR URLs in private controller result comments.
