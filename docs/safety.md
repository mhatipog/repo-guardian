# Behavior and technical limits

**Automation is the default.** The private control issue is an execution request. Manual GitHub approval comments are not required. The default permits low-friction repository creation, topics, private standalone copies, forks and visibility changes from owner-submitted private issues, including ChatGPT-generated issues.

A user-authorized ChatGPT issue executes with a separate admin token in private GitHub Actions secrets. This is a privileged delegation. Limit access to that private repo and be cautious about automation based on untrusted content or ambiguous user instructions. Repo Guardian isn't a managed ChatGPT app.

Command parser permits only known actions, validated repository names, topics and UTC timestamps. Visibility checks identity/state; public publication requires explicit `acknowledge_public_exposure:true`. All changes are verified afterward. These checks are for correctness and GitHub network constraints, not human approval ceremonies.

## Known GitHub limitations

- Forks of public repositories must remain public. A private Git standalone copy isn't a fork network member.
- Publishing a private repo exposes full Git history and previous Actions logs. Returning to private cannot revoke external copies and stars/watchers can be lost.
- A private source mirror does NOT include GitHub issues, PRs, stars, releases, Actions history, webhook settings and all repository-level metadata; it preserves Git branches and tags.
- GitHub Actions scheduled events are not exact and can be missed. The 10-minute cron is best effort.
- The private GitHub Actions runner must be eligible and available. The controller hasn't yet completed a credentialed end-to-end test on this account.

## Not provided in v0.3

Automatic fork-network detachment, issue/PR metadata backup, all-history secret detection, production SLA monitoring, automatic private-source sync, token rotation and complex organization policies.
