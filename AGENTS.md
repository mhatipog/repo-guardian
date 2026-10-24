# Instructions for ChatGPT, Codex, GitHub Copilot and other AI agents

Repo Guardian is a safety-first GitHub repository lifecycle controller, **not a blanket delegation of GitHub administration**.

If the user requests to CREATE a new repository, FORK an upstream repository, or CHANGE repository VISIBILITY:
1. Verify the connected GitHub tools' actual capabilities. If a native operation is supported, obey its approval semantics. Otherwise, use a private `repo-guardian-control` request issue when installed.
2. Inspect any existing target live and obtain its immutable numeric repository ID and visibility before planning a visibility change.
3. Construct a **single JSON object** in the issue body with the exact supported schema in `docs/chatgpt-bridge.md`. Issue title starts `RG:`. Don't wrap JSON in Markdown fences.
4. Clearly explain to the user that this is a proposal and is **NOT** execution.
5. NEVER add or edit a comment beginning `APPROVE `, NEVER infer approval from a chat message, and NEVER claim to have approved on the user's behalf. Approval requires an independent manual GitHub-web comment by the account owner.
6. Never request, display, log, store in an issue, or paste a PAT, private key, or secret value. Credentials belong in GitHub Actions encrypted secrets in a **private** repository.
7. Confirm results only from a verified controller `RG_DONE` log or live target state; don't infer success from a submitted issue or workflow run trigger.
8. Don't publish unknown/private commit histories without an explicit risk review. GitHub public-to-private is not rollback of public exposure.
9. Never automate detach/delete/recreate of upstream forks in this version.
10. For ordinary code changes and PRs, use GitHub's existing ChatGPT connector; the admin bridge is unnecessary.

Supported actions: `status`, `create_repo`, `fork`, `visibility`. Times are UTC ISO-8601. There is no exact-time scheduling guarantee. Refer to [docs/chatgpt-bridge.md](docs/chatgpt-bridge.md) for permission scopes and request examples.

Prefer user's express constraints. On unsupported permissions or unavailable private runners, report the blocker honestly without suggesting the operation succeeded.
