# GitHub Marketplace release checklist

Repo Guardian is a **free GitHub Action**, not a GitHub App or hosted service. The existing public repository and root `action.yml` are the publishing artifact. The private `repo-guardian-control` repository, its runner and its secrets must stay private.

## Before publishing

1. Review and merge the Marketplace-preparation PR after CI passes.
2. Verify the root `action.yml` has a unique Marketplace name, valid branding, and both the `request` and `token` inputs. Its optional `owner` input defaults to the calling repository owner.
3. Verify the exact release commit with the existing unit tests and composite Action smoke workflow.
4. Confirm the release contains no credentials or private control-plane state. The public Action uses code within this repository; it never requires a copy of the private controller.
5. Choose a new semantic-version release tag. Do not reuse an existing tag or advertise a mutable tag as an immutable pin.

## Publish (GitHub account owner)

1. Open the [repository's root action.yml](https://github.com/mhatipog/repo-guardian/blob/main/action.yml) and select **Draft a release** from GitHub's Marketplace banner, or start at [Releases](https://github.com/mhatipog/repo-guardian/releases/new).
2. Enable **Publish this Action to the GitHub Marketplace**, choose the most relevant category, and review GitHub's metadata validation.
3. If required, accept the **GitHub Marketplace Developer Agreement** on the owning account. GitHub requires **two-factor authentication** to publish.
4. Select the reviewed release commit/tag, write a concise changelog, and publish the release.
5. Verify that the Marketplace page opens and its usage example points to the published tag; document the immutable release SHA for consumers.

GitHub does not review published Actions once they meet the automatic requirements, but Marketplace publication itself is an account-owner UI step. Creating a normal GitHub release without checking the Marketplace option **does not establish a listing**.

## First-use example

Put this in a trusted workflow on the default branch. Start with a non-mutating CLI startup check; it proves the composite Action starts, **not** that the token has the scopes required for a later write.

```yaml
name: Repo Guardian smoke
on:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  status:
    runs-on: ubuntu-latest
    steps:
      - uses: mhatipog/repo-guardian@PIN_REVIEWED_COMMIT_SHA
        with:
          owner: YOUR_PERSONAL_GITHUB_LOGIN
          token: ${{ secrets.RG_ADMIN_TOKEN }}
          request: '{"version":1,"action":"status"}'
```

When switching to a write request, keep `request` as **literal reviewed JSON** and use the least-privileged token compatible with that operation. The Action supports personal-account repository administration; repository creation uses GitHub's `/user/repos` API and is **not** organization repository creation. If you omit `owner`, the Action uses the calling workflow repository's owner; for organization workflows targeting a personal account, set `owner` explicitly.

Never inject pull-request, issue, comment, or other untrusted payload content into `request`, and never expose `RG_ADMIN_TOKEN` in a job that executes untrusted code. Use `workflow_dispatch` with trusted workflow contents, pin the Action to a reviewed commit SHA, and protect the secret with appropriate repository access controls. Do not use `pull_request_target` for a privileged Repo Guardian execution.

Publishing is free; GitHub-hosted Actions compute/billing and your own runner costs are separate from the Marketplace listing. Users can run this Action without creating an account with Repo Guardian or sending telemetry to a Repo Guardian service.

See [CLI and Action usage](cli-and-action.md) and [security limitations](safety.md).
