# ChatGPT / Codex / GitHub Copilot agent instructions for Repo Guardian

Repo Guardian is a GitHub repository lifecycle command bridge. The user wants low-friction **automation**, not repeated approval prompts.

1. For PR creation and ordinary code edits, call the connected GitHub tools directly.
2. For repository creation, public forks, private standalone copies, GitHub topic updates, and scheduled visibility changes, open an **issue** titled `RG: <summary>` in the user's PRIVATE `repo-guardian-control` repository.
3. Issue body must be a SINGLE JSON object matching [examples/requests.md](examples/requests.md); don't wrap it in Markdown fences. No code, shell commands or secrets in the issue.
4. No second manual approval comment is required. User-authorized issue creation is the trigger.
5. For visibility changes, inspect numeric GitHub repository ID and current visibility first; for publication include `"acknowledge_public_exposure":true` after informing the user that public copies persist.
6. Forks of public GitHub repos are public and cannot independently be made private. To satisfy "private fork", propose the `private_copy` action and explain that the result is a standalone private Git mirror with no upstream fork association.
7. Reconcile result from GitHub: `RG_DONE` means the controller verified the operation; an issue being opened is not success. If private Actions can't allocate a runner or RG_ADMIN_TOKEN isn't configured, say so plainly.
8. Never obtain or reveal the PAT value; it belongs in private GitHub Actions secrets.
9. Scheduling uses best-effort Actions cron; do not promise an exact publication/privatization time.

Actions: `status`, `topics`, `create_repo`, `fork`, `private_copy`, `visibility`. Details at [docs/chatgpt-bridge.md](docs/chatgpt-bridge.md).

## Upstream PR identity and review policy

- Always open upstream PRs **ready for review**, not in draft. Repo Guardian rejects `"draft":true` and submits `draft:false`. An existing draft is not treated as ready.
- Publish with the owner's personal GitHub token, validated through GitHub `GET /user`. Never impersonate the account owner, another person, or a bot.
- Do not autonomously post upstream PR comments, review replies, or reviews. Draft suggested maintainer responses for the user to review and post personally.
- Keep private controller's GitHub Actions bot status messages private and **free of upstream PR URLs or `owner/repo#number` references**. Linkable references create unwanted bot events on the public PR. Present verified upstream PR links directly in ChatGPT, not in automation issue comments.
- Platform-generated GitHub checks and events still display GitHub's own bot identity; this policy controls only messages authored by Repo Guardian.
