# Private vulnerability reports

Repo Guardian can submit a researcher-initiated **private security report** to a
third-party GitHub repository that has private vulnerability reporting enabled.
It uses GitHub's distinct endpoint:

`POST /repos/{owner}/{repo}/security-advisories/reports`

Do **not** substitute the maintainer-only `/security-advisories` endpoint or
create a public issue/PR when a private report fails.

## Workflow

1. Review the target's `SECURITY.md` and search for known reports before filing.
2. Write a reproducible, narrowly scoped report with the observed result,
   required configuration, impact and outstanding verification gaps.
3. Open an owner-authored `RG:` issue in the **private** control repository,
   using the JSON command below as its entire body. **Never put a real
   vulnerability description into the public Repo Guardian repository.**
4. The pinned private controller validates the payload, authenticates
   `RG_ADMIN_TOKEN` as the owner, checks that the target is public and active,
   and POSTs the report to GitHub. `RG_DONE` includes only a GHSA identifier.
5. If it posts `RG_FAILED`, inspect manually. The controller deliberately
   does not retry an uncertain POST, which could create a duplicate report.

## Example (fictional)

```json
{
  "version": 1,
  "action": "report_vulnerability",
  "upstream": "ExampleOrg/example",
  "summary": "Example authorization behavior under review",
  "description": "## Summary\nIllustrative summary.\n\n## Details\nExplain the code path and trust boundary.\n\n## Proof of concept\nDescribe the isolated reproduction, exact inputs and observed behavior.\n\n## Impact\nExplain realistic conditions and clearly state what has not been verified.",
  "severity": "medium",
  "cwe_ids": ["CWE-863"],
  "vulnerabilities": [{"package": {"ecosystem": "pip", "name": "example"}}],
  "acknowledge_private_submission": true
}
```

The illustration omits enough detail that it is **not** a valid submission.
The report description must be at least 300 characters and contain the exact
headings `## Summary`, `## Details`, `## Proof of concept`, and `## Impact`.

The action supports an omitted severity/CWE/package when unverified. Never
invent affected versions, a CVSS vector, or patched versions.

## Security / operational constraints

- Only an issue in the dedicated private control repository, created by the
  configured owner, can invoke this action.
- `RG_ADMIN_TOKEN` must authenticate as the owner, not a bot.
- Use a private GitHub Action secret; never paste a token in the issue.
- The target must be a third-party public, active repository.
- The API may return 403/404 if private reporting is disabled or the token
  lacks sufficient permission. The report remains unsubmitted; use the target's
  private web form in that case.
- Upgrade the private controller's **reviewed pinned commit SHA** before using
  a new engine action. Updating the public engine alone does not deploy it.
- The private controller's issues hold the report body, which can be sensitive.
  Restrict repository collaborators and GitHub Actions log visibility.
- The API does not expose the web form's AI-assistance checkbox in this
  payload. State AI assistance explicitly in the report description when used.
