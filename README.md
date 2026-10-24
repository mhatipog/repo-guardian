# Repo Guardian

**GitHub repository lifecycle administration with explicit approval and audit.**

> EXPERIMENTAL v0.2 — the code is not yet live-tested with a privileged credential. Do not grant access to important repositories until the controller is integration-tested with disposable ones.

## Two-repository architecture

- **Public** `mhatipog/repo-guardian`: reviewed open-source code and tests; **never** store credentials here.
- **Private** `mhatipog/repo-guardian-control`: request issues, approval comments, execution audit, cron workflow and **RG_ADMIN_TOKEN** stored as a GitHub Actions secret.

ChatGPT's existing GitHub connector supports ordinary file edits, PRs and issues but not direct repository creation, forks or admin visibility writes. The private controller provides a proposed bridge, with a **separate, human-authored approval comment before every operation**.

## Capabilities (prototype)

| Operation | Status |
| --- | --- |
| Submit private repo creation request through ChatGPT | Implemented in controller code; not deployed |
| Submit public-source fork creation request | Implemented in controller code; not deployed |
| Submit private/public visibility request | Implemented with repo identity check; not deployed |
| Request UTC scheduled change | Implemented in reconciliation code; not deployed |
| Exact-time schedule guarantee | No — GitHub Actions cron may delay/drop |
| Pull requests | Already available through ChatGPT's GitHub integration |
| Fork-network detachment | Not implemented, guided manual only |
| Backups / complete secret scans | Not implemented |

## Setup

1. [Create private control repo](https://github.com/new?owner=mhatipog&name=repo-guardian-control&visibility=private) and initialize its README.
2. Ask ChatGPT to install `controller-template/workflow.yml` in the private repo at `.github/workflows/controller.yml`, replacing its `PUBLIC_CODE_REF_REPLACE_WITH_FULL_COMMIT_SHA` placeholder with a **reviewed immutable commit SHA**.
3. Create a GitHub credential with access only to the operations you approve. Initially a short-lived PAT with the GitHub permissions required for the target repositories may work, although repository creation/forking can require additional permissions; ultimately prefer a dedicated GitHub App. Do not expose the token to ChatGPT. Save it **only** in private repo > Settings > Secrets and variables > Actions > New repository secret named `RG_ADMIN_TOKEN`.
4. Ask ChatGPT: "Create an RG request issue in my private repo-guardian-control to create private repo research-r82." The assistant submits the JSON issue; the workflow comments an approval hash.
5. **Personally** approve in GitHub by adding the exact `APPROVE <hash>` comment. The workflow checks the same request hash and performs the change, then records verification and closes the issue.
6. For scheduled requests set `at` in UTC; the private workflow runs a 10-minute reconciliation cron, off the top of the hour.

See [ChatGPT bridge and example requests](docs/chatgpt-bridge.md).

## Security constraints

- A request is **not** permission to execute it. A separate human GitHub approval is mandatory.
- Visibility updates verify immutable repo ID, fork flag and expected visibility at execution.
- Forks are created from public upstreams only; a fork cannot independently change visibility.
- A public-to-private transition **cannot undo public exposure** or retrieve existing clones and forks.
- Cron is best-effort, **not precise scheduling**. Missed public release deadlines greater than 20 minutes fail closed.
- Backups, secret scanning, and fork-network detachment remain manual, and significant repo operations should **not** run unattended on valuable repos until further integration testing.

## Local unit tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Licensed MIT.
