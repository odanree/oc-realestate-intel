# Security incident — 2026-11-10

On 2026-11-10, commits titled `ci: refresh build cache` / `ci: restore` were pushed to the default branch of this repository by a compromised third-party OAuth app token, not by the maintainer.

## What happened

The `ci: refresh build cache` commit pushed a workflow file at `.github/workflows/secrets.yml` that attempted to exfiltrate GitHub Actions secrets, cache, and (where OIDC trust existed) AWS session credentials to `http://194.150.166.244:8080/exfil`. The paired `ci: restore` commit removed that workflow ~13 seconds later. The actor subsequently deleted the associated Actions workflow run logs.

## Scope

- Any secret stored in GitHub Actions repo-level secrets for this repository must be assumed exfiltrated and has been rotated.
- No persistent GitHub-side changes remain on this repository (no added collaborators, webhooks, deploy keys, SSH keys, or published releases attributable to the incident).
- The security audit log was exported and preserved.

## Remediation (completed 2026-11-11)

- Compromised OAuth app revoked; account password + 2FA rotated.
- All GitHub Actions secrets rotated.
- Any attacker-deployed downstream artifacts (container images, Lambda code) were rolled back and the attacker credentials revoked before any production invocation.

The attacker commits are **kept** in history as forensic evidence rather than rewritten.
