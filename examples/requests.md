# Request examples

Submit these as **plain JSON** in the body of a **private** `RG:` issue. ChatGPT can prepare issues but **must never manually approve** its own request.

Read-only health check:
```json
{"version":1,"action":"status"}
```

Create a private repository:
```json
{"version":1,"action":"create_repo","name":"test-research-42","visibility":"private","description":"Experiment sandbox"}
```

Create a fork of a public repository:
```json
{"version":1,"action":"fork","source":"pallets/flask","name":"flask-research"}
```

Publish at a future UTC date (replace numeric repo ID after inspection):
```json
{"version":1,"action":"visibility","repo":"mhatipog/test-research-42","visibility":"public","expected_repo_id":12345678,"expected_visibility":"private","acknowledge_public_exposure":true,"at":"2026-11-10T09:00:00Z"}
```

Return to private at a future UTC date in a SECOND request:
```json
{"version":1,"action":"visibility","repo":"mhatipog/test-research-42","visibility":"private","expected_repo_id":12345678,"expected_visibility":"public","at":"2026-11-11T09:00:00Z"}
```

Do not schedule public exposure of valuable repositories unless complete-history scans, backups and manual risk reviews have been carried out separately.
