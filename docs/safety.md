# Safety properties and limitations

## Threat model

An AI assistant or third-party GitHub App can submit a controller request issue **as the human owner's GitHub user**. Identity alone does not prove manual authorization. The controller rejects GitHub App-originated approval comments even if their `user.login` equals the owner's. The human must approve on GitHub's own website. This was confirmed by inspecting the `performed_via_github_app` field on a ChatGPT-originated issue comment.

The controller workflow must be hosted in a **private** repository. Its high-privilege token belongs only in GitHub Actions Secrets, never in a checked-in file. Executable controller source is checked out from a fixed, reviewed commit SHA, not a mutable public branch. Untrusted user input is parsed as strict JSON, never executed as shell code.

## Visibility consequences

- Private → public exposes Git history and GitHub Actions history/logs, potentially revealing formerly private information. Push rulesets can be disabled. Stars/watchers are affected.
- Public → private doesn't undo external clones, public forks, or previous disclosure. Public forks can be detached and stay public. GitHub Pages and other features may change.
- Fork visibility is tied to upstream visibility; not independently configurable.
- GitHub fork-network detachment and replacement can lose issues, pull requests, stars and repository-specific metadata. This version never automatically deletes or detaches forks.

## Checks implemented

- Strict action-specific request fields and validated repo identifiers
- GitHub account owner restriction on requests and approvals
- Request hash ties approval to JSON content
- App-originated approval comments refused
- Private workflow boundary
- Explicit acknowledgement for private → public
- Live target repository ID, visibility, fork and archival guards
- Fresh post-action GET verification
- No blind replay after a recorded ambiguous API error
- Late publication deadline refusal after 20 minutes

## Not yet implemented

- Commit-history-wide secret detection
- Independent backups of Git objects, metadata, issues, PRs, and Actions artifacts
- Independent scheduler, watchdog, missed-job notification and delivery SLA
- Security review of token provisioning, cross-organization support, API error/replay edge cases
- Production integration tests against expendable repositories

**Treat v0.2 as experimental**, not a guarantee of reversible operations or private data protection.
