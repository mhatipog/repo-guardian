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
