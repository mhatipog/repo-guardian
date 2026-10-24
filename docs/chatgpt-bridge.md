# Use Repo Guardian from ChatGPT

**ChatGPT cannot automatically acquire GitHub repository administration permissions.** Its connected GitHub App can read repositories, create files, PRs, and issues, but does not expose new repository, fork, or visibility write methods in every environment. Repo Guardian bridges that gap through a private GitHub controller. It is **not an official ChatGPT app or plugin** and requires deliberate initial setup.

## Personal setup for mhatipog

- Public code: [mhatipog/repo-guardian](https://github.com/mhatipog/repo-guardian)
- Private controller: [mhatipog/repo-guardian-control](https://github.com/mhatipog/repo-guardian-control)
- Private workflow: `.github/workflows/controller.yml` (pin code checkout to a reviewed public SHA)
- [Create a limited 30-day fine-grained PAT](https://github.com/settings/personal-access-tokens/new?name=RepoGuardianController&description=Private%20GitHub%20controller%20for%20approved%20repository%20operations&target_name=mhatipog&expires_in=30&repository_creation=write&administration=write&contents=read)
- [Store the secret in the private controller](https://github.com/mhatipog/repo-guardian-control/settings/secrets/actions/new): exact secret name **RG_ADMIN_TOKEN**

**Verify the permissions in GitHub's token form before generating.** Repository creation requires *Repository creation: write* (or *Administration: write*). Visibility writes need *Administration: write*. Creating a fork requires *Repository creation: write* + *Contents: read*, or *Administration: write* + *Contents: read*. The token must be able to see both the source and destination where needed. Selecting all repositories for a personal-account administration token is powerful and risky; start with disposable test repositories, choose the narrowest selection that works, rotate/expire the token, and prefer a narrowly scoped GitHub App for production. Never paste the token into ChatGPT, code or issues.

**GitHub Actions must actually start runners**. If jobs fail in ~3 seconds, `runner_id=0` and `steps=[]`, inspect your GitHub account Actions billing/minute budget and runner availability. The controller is **not operational** until a health issue is processed successfully and a disposable test mutation passes.

## What you say to ChatGPT

Use any of these natural-language prompts:

> In my private GitHub repo-guardian-control, create an issue titled RG: create research-r82. Put exactly this JSON in the body: `{"version":1,"action":"create_repo","name":"research-r82","visibility":"private"}`. Do not add an approval comment.

> Inspect the exact current ID and visibility of `mhatipog/research-r82`. Prepare a Repo Guardian issue that makes it public at 2026-11-10 09:00 UTC. Include `expected_repo_id`, `expected_visibility` and `"acknowledge_public_exposure":true`. Do not approve the request.

> Make an RG request to fork `pallets/flask` as `flask-research` in my personal GitHub account. Don't approve it.

> Create a pull request from branch `feature/x` to `main` using the connected GitHub integration. No Repo Guardian admin request is needed.

ChatGPT is permitted to *propose* requests and create PRs directly. **It must not post an `APPROVE` comment or claim that an issue request is already executed.** Approval must be your manual action in GitHub web UI. The controller ignores GitHub App-originated approval comments, including comments that appear under your own username.

## JSON request schema

### Controller status (read-only, no approval)

```json
{"version":1,"action":"status"}
```

### Create repository

```json
{"version":1,"action":"create_repo","name":"research-r82","visibility":"private","description":"Research experiment"}
```

### Fork public repository

```json
{"version":1,"action":"fork","source":"pallets/flask","name":"flask-research"}
```

### Schedule publication

Inspect the live repository to get its numeric ID and initial visibility first.

```json
{"version":1,"action":"visibility","repo":"mhatipog/research-r82","visibility":"public","expected_visibility":"private","expected_repo_id":12345678,"acknowledge_public_exposure":true,"at":"2026-11-10T09:00:00Z"}
```

### Schedule privatization

```json
{"version":1,"action":"visibility","repo":"mhatipog/research-r82","visibility":"private","expected_visibility":"public","expected_repo_id":12345678,"at":"2026-11-11T09:00:00Z"}
```

**Every request must be the entire JSON body of a private issue whose title starts with `RG:`.** Times use UTC `Z`. No arbitrary shell commands, external URLs, scripts, webhook addresses or unrecognized keys are accepted. If you schedule publication and subsequent privatization, create *two separate issues*. Review and approve them individually.

The workflow checks for approved requests when an owner manually comments and every 10 minutes by cron. No exact-time guarantee. Publication more than 20 minutes overdue is refused. Privatization remains due even if cron was delayed; confirm the state yourself after the deadline.

## Risk and approval model

1. GitHub issue submitted through ChatGPT -> proposal only.
2. Controller checks JSON, posts a **RG_REVIEW** comment with a request hash.
3. You inspect scope and risk and manually comment `APPROVE <hash>` using **GitHub's website**, not through ChatGPT.
4. Workflow verifies manual origin, request hash and expected target state.
5. Credentialed call executes and target is re-read; the controller comments `RG_DONE` or `RG_FAILED`.
6. Failures requiring manual investigation do not automatically re-run the same mutation.

The code is intentionally pinned to a reviewed SHA when the private workflow executes. Release updates should follow a review, new SHA pin, and tests. Do not modify executable code in an untrusted issue, PR or external repository and then load it with the admin token.

## Current limitations

- GitHub Actions private hosted runner availability and billing affect all execution. A second, independent scheduler and monitoring channel would be needed for meaningful schedule reliability.
- No whole-history secret scan, release artifacts backups, stars restore, issue/PR preservation, fork detachment automation, or GitHub organization support in this proof of concept.
- Creating a new fork may be asynchronous; limited verification retries are included.
- API errors after ambiguous mutations intentionally halt automatic retries.
- Forks inherit the upstream's visibility; their visibility cannot be switched independently.
- Publication may expose GitHub Actions logs, commit history and confidential data and may leave public copies even after privatization.

## Permission references

- [GitHub repository creation REST API](https://docs.github.com/en/rest/repos/repos#create-a-repository-for-the-authenticated-user)
- [GitHub forks API](https://docs.github.com/en/rest/repos/forks#create-a-fork)
- [GitHub personal access token permissions and prefilling](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- [GitHub scheduled Actions limitations](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [Repository visibility consequences](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)
