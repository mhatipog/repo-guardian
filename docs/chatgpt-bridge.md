# ChatGPT command bridge (provisional)

ChatGPT's installed GitHub connector can create PRs, issues and files in allowed repositories, but does not expose GitHub's new repository, fork or visibility API operations. This controller makes those operations achievable *after* a distinct GitHub-account approval.

1. Create a **private** repo named mhatipog/repo-guardian-control (do not make the public project private).
2. Copy controller-template/workflow.yml to .github/workflows/controller.yml inside that private repository and pin the public source code to a reviewed full Git SHA.
3. Create an expiring GitHub credential with the permissions needed by the target action and store it as an Actions secret RG_ADMIN_TOKEN **in the private controller**: Settings > Secrets and variables > Actions. The controller repo's built-in GITHUB_TOKEN needs Issues write.
4. Ask ChatGPT to create a GitHub issue in the private controller with title beginning RG: and a JSON object as the ENTIRE issue body. Nothing executes yet.
5. Read the generated review comment. For the specific action, reply PERSONALLY using your GitHub account with the exact string APPROVE <hash>. The approval is bound to the normalized JSON content; edited requests need fresh approval.
6. The issue_comment workflow executes an immediate approved request or leaves a scheduled one pending. The cron reconciler periodically checks pending requests.

## Example requests

Private repository:

```json
{"version":1,"action":"create_repo","name":"research-r82","visibility":"private"}
```

Public fork:

```json
{"version":1,"action":"fork","source":"pallets/flask","name":"flask-research"}
```

Visibility (first inspect repository ID and current state):

```json
{"version":1,"action":"visibility","repo":"mhatipog/research-r82","visibility":"public","expected_visibility":"private","expected_repo_id":12345678,"at":"2026-11-10T09:00:00Z"}
```

A request may omit at for immediate execution. Time values MUST be UTC and end in Z.

**Safety limitations:** The controller is a prototype. Manual human approval is still required. No full-history secret scan, backup, or fork detach implemented. Scheduled Actions may delay or drop; successful publication to public cannot be undone by privatizing again. Missed public publishing deadlines of over 20 min are rejected. No exact scheduling guarantee. Do not run on important repositories until disposable-repository integration tests and a security review pass.
