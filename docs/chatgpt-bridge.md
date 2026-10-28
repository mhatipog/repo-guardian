# ChatGPT ↔ Repo Guardian

Repo Guardian is open-source software, not an officially registered ChatGPT app. It works with the existing GitHub connector by letting ChatGPT create request issues in a private repository. The external controller performs actual GitHub API operations using a token stored in GitHub Actions secrets.

## Your installation

- Public engine: [mhatipog/repo-guardian](https://github.com/mhatipog/repo-guardian)
- Private controller: [mhatipog/repo-guardian-control](https://github.com/mhatipog/repo-guardian-control)
- [Private Actions](https://github.com/mhatipog/repo-guardian-control/actions)
- [Private Actions secrets](https://github.com/mhatipog/repo-guardian-control/settings/secrets/actions) — **RG_ADMIN_TOKEN** lives here, not in source code or chat.
- [GitHub Actions runners](https://github.com/mhatipog/repo-guardian-control/settings/actions/runners) — must have a working runner. The new private repository's `ubuntu-latest` job failed before runner allocation, even for a one-line `echo`. The existing `web-operations` self-hosted `oci-ams-2` runner is not automatically accessible to this repository.
- [Private runner test](https://github.com/mhatipog/repo-guardian-control/actions/workflows/runner-diagnostic.yml)

### Automation-first commands

ChatGPT can directly submit an authorized JSON request by opening an issue with title `RG: <summary>` in the **private** controller. No second approval comment is required. Only issues opened under the configured owner GitHub identity are processed. You can later request status by reading the same issue, and the controller writes `RG_DONE` or `RG_FAILED`.

#### Add GitHub repository topics

```json
{"version":1,"action":"topics","repo":"mhatipog/repo-guardian","names":["chatgpt","github-automation","ai-agents"],"mode":"add"}
```

Modes: `add` (default), `remove`, `replace`. `add` merges into current topics; `replace` overwrites the list. No GitHub App connector administration permission is needed by ChatGPT itself; it just submits the issue.

#### Make a private repo

```json
{"version":1,"action":"create_repo","name":"research-r82","visibility":"private"}
```

#### Fork a public repo (stays PUBLIC)

```json
{"version":1,"action":"fork","source":"octocat/Hello-World","name":"my-public-fork"}
```

#### Make a private standalone copy of a public repo

```json
{"version":1,"action":"private_copy","source":"octocat/Hello-World","name":"my-private-source-copy"}
```

This creates a fresh private repo, then runs a bare clone and mirror push to preserve the upstream Git commit history, branches and tags. It does NOT create a GitHub fork, inherit upstream PRs/issues, or retain fork-network linkage. It is NOT a sync: future upstream changes require a separate sync workflow, not yet implemented.

#### Public/private visibility changes

Inspect the actual numeric GitHub repository ID and current visibility before submitting:

```json
{"version":1,"action":"visibility","repo":"mhatipog/research-r82","visibility":"public","expected_repo_id":12345678,"expected_visibility":"private","acknowledge_public_exposure":true}
```

To schedule it, add `"at":"2026-11-10T09:00:00Z"` (UTC). To turn it private again, issue a separate command with `"visibility":"private"` and `"expected_visibility":"public"`. Switching back to private doesn't retrieve copies made while public.

#### Simple status request

```json
{"version":1,"action":"status"}
```

## Execution and reliability

Your **private** `.github/workflows/controller.yml` must point to a tested public engine SHA. It runs on request creation and on a 10-minute cron. Only private GitHub Actions secrets contain the PAT. A private standalone code copy also requires **Contents: write** for its newly created destination; a fine-grained PAT limited to selected existing repositories may not cover newly created repositories. Check this before attempting a private copy. **A stored secret is not enough if GitHub cannot start a runner.** GitHub-hosted runners may be blocked by spending limits or account configuration; personal-account self-hosted runners may need separate registration on this repository. Hosted GitHub Actions cron can run late or drop runs. The controller rejects publication more than 20 minutes late but currently cannot promise exact deadlines, nor send independent failure alerts.

## Automation principles

- Don't request unnecessary manual approval comments: the authenticated private issue is the user-selected instruction channel.
- Never execute arbitrary shell supplied in the issue. Only documented action names and parameters are accepted.
- Don't change an upstream GitHub fork's visibility; public forks must remain public.
- Never expose PATs or GitHub App keys in chat. Set expiration and minimum required scopes on the repository secret.
- Identity and post-change verification are simple correctness checks, not second approval gates.
- Once a command is submitted, status remains **pending** until verified by GitHub.


#### Update existing repository description and homepage

An authenticated controller issue can update the description and HTTPS homepage of an owned repository. Supply the stable numeric repo ID from live GitHub inspection. The controller checks its identity and verifies the post-update values. No visibility changes occur.

```json
{"version":1,"action":"metadata","repo":"mhatipog/umig6-metering-quality","expected_repo_id":1435626896,"description":"PySpark metering data quality, source provenance, quarantine and legacy MIG6 migration readiness for Belgian energy pipelines","homepage":"https://github.com/mhatipog/umig6-metering-quality/tree/main/docs/HANDOFF.md"}
```

## Upstream PR identity and review readiness

`open_pr` always submits `draft:false`; `draft:true` is rejected. Before publishing, the controller checks the authenticated GitHub identity of `RG_ADMIN_TOKEN` via `GET /user`. It refuses service accounts, bots, and identities other than the configured owner, and verifies the final PR is non-draft and authored by that owner. If the PAT lacks permission for `GET /user` or publishing to that upstream, it fails closed.

The controller **does not comment or review upstream PRs**. It reports execution only in private control issues, intentionally omitting public PR URLs and `owner/repo#number` references from the GitHub Actions bot's status comments to avoid an upstream cross-reference. ChatGPT may separately show the independently verified PR URL to the user. GitHub's own platform-generated workflow activity is outside this control.
