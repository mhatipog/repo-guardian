---
name: repo-guardian
description: Automation-first ChatGPT GitHub repository management: create repositories, fork public repos, privately copy upstream Git history, add GitHub topics, schedule public/private visibility and verify changes.
---

# Repo Guardian agent skill

This is portable instruction text, not an installed native ChatGPT plugin.

Use the existing GitHub connector to create a private `RG:` request issue for actions not exposed by the connected tools. The private controller executes the issue and verifies GitHub state using the user's separately stored Actions secret. No second manual approval comment.

Read [AGENTS.md](../../AGENTS.md), [examples/requests.md](../../examples/requests.md), and [docs/chatgpt-bridge.md](../../docs/chatgpt-bridge.md).

Never claim the request has executed until the controller reports `RG_DONE` or live GitHub state independently confirms it. For real PRs, use existing GitHub connector methods. For public upstream→private GitHub repository, use `private_copy`, not `fork`: GitHub prohibits making a public fork independently private.

Handle GitHub topic addition (`topics`, `mode:add`), private repo creation (`create_repo`), true public fork (`fork`), private standalone copy (`private_copy`), and repo visibility transitions (`visibility`). No tokens in user-facing requests. Cron reliability is best effort.

For public upstream contributions, never create draft PRs and never publish under a bot or someone else's identity. Only the owner's authenticated token may create an upstream PR; the controller does not comment/reply/review upstream. Do not include public PR links in private bot status comments, which can cause upstream GitHub cross-reference events. Show the validated upstream link directly to the user.
