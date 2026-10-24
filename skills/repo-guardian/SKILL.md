---
name: repo-guardian
description: Safely propose creation, forks, visibility transitions and scheduled changes to GitHub repositories through a private controller, with manual approval and post-action verification.
---

# Repo Guardian skill for ChatGPT and coding agents

**Not an installed ChatGPT connector:** these are portable instructions for an agent with existing GitHub issue/PR tools. The user needs to set up the separate Repo Guardian private controller.

## When to use

When the user asks in natural language for:
- "Create a new GitHub repository"
- "Fork GitHub repository X"
- "Schedule making my repo public / private"
- "Change GitHub repository visibility"
- "Get me out of this fork network" (analysis and manual guidance only)

## Operational procedure

1. Read [docs/chatgpt-bridge.md](../../docs/chatgpt-bridge.md) and [AGENTS.md](../../AGENTS.md).
2. Check whether `<user>/repo-guardian-control` is installed, private, and reachable with the GitHub connector. Do not invent missing permissions.
3. For a visibility request, inspect the exact repository ID and current visibility before writing an issue.
4. Open a controller issue titled `RG: <human summary>` with body containing ONLY validated request JSON. For public publication, include `acknowledge_public_exposure: true` only after explaining irreversible consequences.
5. Return the issue URL. This is a proposal, not the completed action.
6. Never create a GitHub `APPROVE` comment through an AI tool. The human must approve independently through GitHub's web UI.
7. Read controller status if requested, and require verification before claiming completion.
8. Native GitHub file edits and PRs should use the already connected GitHub tools directly.

Repository administration secrets must never appear in chat or tracked files. Exact-time scheduler and irreversible fork detach are unsupported by the initial release.
