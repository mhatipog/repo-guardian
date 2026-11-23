# Repo Guardian CLI and GitHub Action

These do **not** depend on the private controller workflow or issue scheduler. They run wherever you have Python 3.11+ and GitHub credentials available.

## Direct CLI

Install the code into a Python environment:

```bash
pip install git+https://github.com/mhatipog/repo-guardian.git
export RG_ADMIN_TOKEN="YOUR_GITHUB_TOKEN"   # local shell only; don't commit
repo-guardian inspect mhatipog/repo-guardian
repo-guardian topics mhatipog/repo-guardian chatgpt ai-agents github-automation
repo-guardian create example-private --visibility private
repo-guardian fork octocat/Hello-World --name hello-test-fork
repo-guardian private-copy octocat/Hello-World --name hello-test-private-copy
repo-guardian visibility mhatipog/example-private public
```

The equivalent command without installation is `PYTHONPATH=src python -m repoguardian ...`.

## GitHub Action

This public composite Action runs directly on the caller's runner; it does **not** install the private controller or require an external service. Its `owner` input defaults to the calling workflow's repository owner. The owner must be the personal GitHub account you intend to administer; for workflows under an organization, set `owner` explicitly to the personal account whose repositories are targeted. Repo creation currently uses GitHub's `/user/repos` endpoint and creates **personal**, not organization, repositories.

Start with a manually dispatched workflow on a **trusted default branch**. Store a narrowly scoped, expiring PAT in `RG_ADMIN_TOKEN` as an encrypted Actions secret. Use a **reviewed immutable SHA** in production rather than a mutable branch:

```yaml
name: Repo Guardian test
on:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  topics:
    runs-on: ubuntu-latest
    steps:
      - name: Update repository topics
        uses: mhatipog/repo-guardian@PIN_TO_REVIEWED_SHA
        with:
          token: ${{ secrets.RG_ADMIN_TOKEN }}
          owner: YOUR_PERSONAL_GITHUB_LOGIN
          request: >-
            {"version":1,"action":"topics","repo":"YOUR_LOGIN/YOUR_REPO",
             "names":["chatgpt","github-automation"],"mode":"add"}
```

The `request` is a literal, reviewed JSON object, not a value copied from a pull request, issue, comment or user-controlled artifact. Change it to `{"version":1,"action":"status"}` to perform a non-mutating CLI startup check; **status only confirms that a token was supplied, not that its scopes are correct**. The topics example above actually writes GitHub metadata; use it only after checking the target and permissions.

For Marketplace publication and release steps, see [docs/marketplace.md](marketplace.md). To reuse this with ChatGPT, ask the agent to prepare a trusted workflow or open a private controller issue. Ordinary PRs are better handled by native GitHub tools.

## Tokens

GitHub Actions' ordinary `GITHUB_TOKEN` cannot administer other repositories. Provide `RG_ADMIN_TOKEN` through the repository's encrypted Actions secrets. The token needs permission for each requested GitHub API operation: Administration write for topics and visibility changes, Repository creation write for new repositories, and **Contents write access to the newly created destination** for a private Git copy. If using a fine-grained PAT restricted to selected existing repositories, the token may not cover a repository it creates later; choose an appropriate repository selection or use a GitHub App with installation access to the new destination.

**A public workflow is public code:** only grant credentials to trusted default-branch jobs. Do **not** expose the admin secret via `pull_request_target`, `issue_comment`, or other untrusted event data, and do not run untrusted checkout code in a job holding the admin token. For personal usage, prefer the private controller or a private workflow on a trusted runner.

## Differences

- **CLI:** runs immediately, works without GitHub Actions, needs local token.
- **GitHub Action:** runs through any functioning Actions runner, needs an encrypted token secret.
- **Private controller:** tracks natural-language issues/schedules; waits for an available runner.
