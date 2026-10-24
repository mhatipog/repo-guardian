# Repo Guardian 🛡️
**Control GitHub repositories from ChatGPT — with safety checks and human approval.**

[![Tests](https://github.com/mhatipog/repo-guardian/actions/workflows/ci.yml/badge.svg)](https://github.com/mhatipog/repo-guardian/actions/workflows/ci.yml)
[MIT license](LICENSE) · [ChatGPT setup](docs/chatgpt-bridge.md) · [Agent skill](skills/repo-guardian/SKILL.md) · [Safety model](docs/safety.md)

**Repo Guardian** is an open-source GitHub repository lifecycle automation prototype for developers and AI coding assistants. Use natural language in **ChatGPT**, GitHub Copilot, Codex, or another agent to propose repository creation, forks, GitHub visibility changes, and scheduled transitions. A private GitHub Actions controller authenticates separately, checks state, requests a manual approval, executes accepted operations, and verifies the outcome.

> **Experimental:** The Python library and public CI run, but private Actions runner execution and privileged GitHub API operations still require end-to-end validation. This is not currently a managed service or ChatGPT plugin. Follow the setup guide; never point experimental automation at important repositories.

## What can I ask ChatGPT?

| Example prompt | Execution |
|---|---|
| "Create a new private GitHub repo called research-r82" | ChatGPT submits an issue to your private control repo; execute after manual approval |
| "Fork pallets/flask into my account as flask-research" | Same approval-driven fork command (public sources in v0.2) |
| "Make my GitHub repo public next Friday" | ChatGPT inspects repo ID and state, submits a scheduled request, you separately approve |
| "Make research-r82 private tomorrow" | A scheduled request attempts the visibility transition and verifies it |
| "Create a PR from my branch to main" | Use ChatGPT's native GitHub integration; Repo Guardian is not required |
| "Detach this fork from upstream" | Guided analysis only; **no automatic detach or deletion** |

**Unlike a simple `gh repo edit` script**, Repo Guardian separates *intent* from *authorization*. A GitHub issue is a request, not an executable command. Manual approval from the owner's GitHub web UI is required. **Comments created by ChatGPT or other GitHub Apps must not count as human approvals**, even when they carry the owner's username.

### Architecture

```text
ChatGPT / agent with GitHub access
    │  create RG: GitHub issue (request only)
    ▼
PRIVATE repo-guardian-control
    ├── request issues, review comments, audit history
    ├── cron (UTC, best-effort) and event workflows
    └── RG_ADMIN_TOKEN in GitHub Actions secret store
        │  after explicit GitHub-web approval
        ▼
Pinned, reviewed Repo Guardian Python controller
        │ GitHub API + target identity verification
        ▼
Repository created / forked / visibility changed
```

The **public repo contains only software and documentation**. The private control repository holds schedule/request metadata, approval trail, and the Actions secret named `RG_ADMIN_TOKEN`. Never commit or paste a token into issue bodies, repository files, or ChatGPT.

## Install for ChatGPT in five steps

1. Connect your GitHub account to ChatGPT and give it access to a **private** repository named `<your-username>/repo-guardian-control`.
2. Place [controller-template/workflow.yml](controller-template/workflow.yml) at `.github/workflows/controller.yml` in that **private** repository, setting `RG_OWNER` to your GitHub login and pinning the public code checkout to a *reviewed immutable commit SHA*.
3. Generate a short-lived, limited GitHub credential with permissions appropriate for your selected repository operations. Store it as an **Actions repository secret**, `RG_ADMIN_TOKEN`, in the **private** control repo. For personal accounts, a fine-grained PAT with repository creation write, administration write and contents read can work; review its repository selection. See [exact permissions and token link](docs/chatgpt-bridge.md).
4. In ChatGPT ask: **"Open a Repo Guardian request in my private control repo to create a private repository called research-r82."** ChatGPT creates the private issue, not the actual repository.
5. In GitHub **yourself**, review the JSON request, inspect the proposed change and add the exact `APPROVE <hash>` comment. The controller will run only after that distinct manual approval.

**Start with** `{"version":1,"action":"status"}` in an issue titled `RG: health` to test the controller *without admin credentials or writes*. Full instructions and prompts: [ChatGPT integration cookbook](docs/chatgpt-bridge.md).

## Scheduling: caveats that matter

The template reconciles requests every **10 minutes**. GitHub Actions schedules may be late or dropped; private Actions can also fail when hosted runner credits or account billing are unavailable. The controller refuses **publications >20 minutes late** rather than unexpectedly exposing code. **There is currently no exact-time or guaranteed deadline execution.** An independent scheduler/watchdog is planned.

Visibility changes are **not reversible security operations**: previously public Git history, clones, public forks, Actions logs and erased stars cannot necessarily be recovered or hidden. No automated history-wide secret scanning or backup is included in v0.2. Do not schedule sensitive publications without separate review.

## For contributors and AI agents

- [Agent instructions](AGENTS.md) · [Reusable agent skill](skills/repo-guardian/SKILL.md)
- [Security assumptions](docs/safety.md) · [Controller JSON request examples](examples/requests.md)
- [GitHub feature limitations](docs/chatgpt-bridge.md)
- Unit tests: `PYTHONPATH=src python -m unittest discover -s tests -v`.
- Python 3.11+; dependency-free runtime. MIT licensed.

### Keywords
**ChatGPT GitHub automation**, **ChatGPT create repository**, **GitHub repository visibility automation**, **private-to-public GitHub scheduler**, **GitHub fork automation**, **AI agent GitHub admin**, **GitHub repository lifecycle**, **GitHub PAT GitHub Actions**.

This project is not affiliated with GitHub or OpenAI.
