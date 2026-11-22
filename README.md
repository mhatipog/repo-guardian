# Repo Guardian

**Manage GitHub repositories through ChatGPT: create repos, fork public projects, make private copies, edit topics and schedule visibility changes.**

[![CI](https://github.com/mhatipog/repo-guardian/actions/workflows/ci.yml/badge.svg)](https://github.com/mhatipog/repo-guardian/actions/workflows/ci.yml)
[ChatGPT setup](docs/chatgpt-bridge.md) · [Downstream impact proof](docs/vulnerability-to-impact.md) · [Agent instructions](AGENTS.md) · [Agent skill](skills/repo-guardian/SKILL.md) · [MIT license](LICENSE)

Repo Guardian is an open-source, *experimental* GitHub repository controller designed for ChatGPT, Codex, Copilot and other AI agents. It bridges admin capabilities missing from the standard ChatGPT GitHub connector using a private control repository, a stored GitHub token and scheduled GitHub Actions.

## Ask ChatGPT

- “Add `chatgpt`, `ai-agents`, `github-automation` topics to my public Repo Guardian repository.”
- “Create a private repository called research-r82.”
- “Fork octocat/Hello-World to my account.” **True forks of public repositories stay public.**
- “Copy octocat/Hello-World into a private standalone repo called my-private-source.”
- “Make my standalone GitHub repository public on Friday at 10:00.”
- “Make it private on Saturday.”
- “Create a PR from feature/experiment to main.” **Already supported by the native ChatGPT GitHub connector.**

In the private control repo ChatGPT creates an issue titled `RG: ...` with a strict JSON command. **No extra approval comment is required** for account-owner requests; the controller processes the request immediately or at the specified UTC schedule. Code and token are separated. Publication requires a simple `acknowledge_public_exposure: true` field in the requested JSON.


- **Upstream pull requests (connector fallback):** publish a reviewed branch from your own public fork to its actual upstream repository with a strict `open_pr` request. Requires an exact expected head SHA and explicit public-exposure acknowledgement. Verify the resulting PR on GitHub.
- **User-approved PR conversation replies:** `comment_pr` posts only on your own open upstream PR, pinned to an exact head SHA and an existing comment's author, ID and SHA-256. The user must explicitly approve the text. Identity and duplicate checks run before posting; public review submissions remain unsupported. The existing GitHub connector remains the first choice.

Repo Guardian also supports **private researcher vulnerability reports** via the authenticated private controller. Use `report_vulnerability` to submit directly to GitHub's private `/security-advisories/reports` endpoint without opening a public issue. This requires a private controller running a reviewed commit and a suitable owner token. See [Private vulnerability reports](docs/private-security-reports.md). No vulnerability descriptions belong in this public repository.

## Features

| Action | How it works |
| --- | --- |
| GitHub topics | Add (default), remove or replace topics with REST API; verify result |
| Create repository | Create a new public/private GitHub repository |
| Public upstream fork | GitHub native fork operation; fork stays public |
| Public source → private | Standalone private Git copy, preserving branch history and tags; **not a GitHub fork** |
| Visibility | Change public/private on **standalone** repos and verify target ID/state |
| Scheduling | Private Actions cron reconciler runs every 10 min; GitHub cron is best-effort |
| PRs | Use existing ChatGPT GitHub tools directly |
| Fork network detachment | Not automated; GitHub's native feature has restrictions |

**Important:** Published code cannot be made secret retroactively. A private copy doesn't preserve upstream issues, PRs, stars or fork association. GitHub Actions cannot guarantee exact-time execution. Important repositories should be reviewed before first publication.

## Execute immediately without the private scheduler

Repo Guardian v0.4 also ships a **Python CLI** and a reusable **GitHub composite Action** that do not require a private controller runner. On a trusted shell, supply an appropriately scoped `RG_ADMIN_TOKEN`, then run:

```bash
pip install git+https://github.com/mhatipog/repo-guardian.git
repo-guardian inspect mhatipog/repo-guardian
repo-guardian topics mhatipog/repo-guardian chatgpt github-automation ai-agents
repo-guardian private-copy octocat/Hello-World --name hello-test-private-copy
```

For GitHub Actions, use `mhatipog/repo-guardian@<reviewed SHA>` with inputs `token` (an Actions secret) and `request` (strict JSON). See [CLI and reusable GitHub Action](docs/cli-and-action.md). This also makes the project discoverable as a GitHub Action without requiring a ChatGPT-specific plugin.

### Deployment verification

The public engine has unit tests and GitHub Action smoke tests. For a new private-controller installation, confirm that a runner can start, check the controller's `status` response, and verify a low-risk topics update before granting broader permissions. Runner availability and token permissions vary between installations.

## Two-repository setup

```
ChatGPT GitHub connector
  → issue with JSON command in your PRIVATE repo-guardian-control
  → GitHub Actions (admin PAT only in private Actions secrets)
  → GitHub REST API / git copy
  → confirmation posted to private issue
```

1. Create `<owner>/repo-guardian-control` as **private**.
2. Install [controller-template/workflow.yml](controller-template/workflow.yml) as private `.github/workflows/controller.yml`; pin the checkout to a reviewed public SHA and set `RG_OWNER`.
3. Add a narrowly scoped GitHub PAT as **RG_ADMIN_TOKEN** in the private repository's **GitHub Actions secrets**. Never commit or share the token in chat.
4. Confirm a private workflow can actually start a runner. GitHub-hosted runner minutes/billing or self-hosted runner registration can prevent startup.
5. Ask ChatGPT to create the JSON issue. See [copyable requests](examples/requests.md) and [agent instructions](AGENTS.md).

[Full ChatGPT deployment guide](docs/chatgpt-bridge.md) · [Security and limitations](docs/safety.md)

**Search terms:** ChatGPT GitHub repository management, GitHub topic automation, GitHub fork to private copy, automate GitHub repository visibility, scheduled GitHub private public, AI agent repository administration, GitHub Actions automation.

### Publishing PRs as the owner

Repo Guardian's `open_pr` action only publishes **ready-for-review** upstream PRs (`draft:false`) and checks that the publishing token authenticates as the GitHub owner. Draft requests, bot accounts, and other users are rejected. Repo Guardian never posts comments/reviews on public PRs and avoids cross-referencing PR links in its private GitHub Actions bot status messages. See [AGENTS.md](AGENTS.md) for the policy.
