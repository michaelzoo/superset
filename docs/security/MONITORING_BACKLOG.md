# Security Monitoring Backlog

Planned improvements to the vulnerability and CVE monitoring pipeline for this repository.

## Current State

| Tool | Status | Scope |
|---|---|---|
| GitHub CodeQL | Active | Static analysis (Python & JS) on PRs + daily cron |
| Dependency Review Action | Active | Blocks PRs introducing critical-severity deps |
| Dependabot | Active | Auto-opens PRs for outdated deps (daily npm, weekly pip) |
| FOSSA | Active | License compliance on push to master |
| `pip-audit` in CI | **In Progress** — [PR #1](https://github.com/michaelzoo/superset/pull/1) | Audits pinned Python deps against OSV/CVE databases per-PR and weekly |
| Trivy container scanning | **Removed** (compromised action, Mar 2026) | Was scanning Docker images for OS-level CVEs |

---

## Backlog

### 1. Replace Trivy with Container Image Vulnerability Scanning

**Priority:** High
**Status:** Not started
**Context:** Trivy was removed in [commit `7004369`](https://github.com/michaelzoo/superset/commit/7004369c68) after the `aquasecurity/trivy-action` GitHub Action was compromised. No replacement was added, leaving a gap in container-level vulnerability detection.

**Proposed approach:**
- Add [Grype](https://github.com/anchore/grype) (Anchore's open-source scanner) or [Docker Scout](https://docs.docker.com/scout/) as a replacement
- Run on push to `master` against the `lean` Docker image build (same trigger as the old Trivy step)
- Upload SARIF results to GitHub Security tab (same integration Trivy used)
- Pin the action by commit SHA to avoid supply-chain compromise

**Suggested workflow location:** `.github/workflows/docker.yml` (restore the removed scanning step)

**Acceptance criteria:**
- [ ] Container image scanned for OS and language-level CVEs on every push to master
- [ ] Results visible in GitHub Security → Code scanning alerts
- [ ] Action pinned by SHA, not tag
- [ ] Fails on CRITICAL/HIGH severity with `ignore-unfixed: true`

---

### 2. Weekly OSV-Scanner for Cross-Ecosystem Vulnerability Detection

**Priority:** Medium
**Status:** Not started
**Context:** [OSV-Scanner](https://github.com/google/osv-scanner) (by Google) can scan both Python and JavaScript lockfiles in a single pass against the OSV database. Running it as a weekly cron job provides a safety net that catches CVEs disclosed between Dependabot update cycles.

**Proposed approach:**
- Create a new workflow `.github/workflows/osv-scanner.yml`
- Run on a weekly schedule (e.g., Sunday night UTC)
- Scan `requirements/base.txt`, `superset-frontend/package-lock.json`, and plugin lockfiles
- Upload SARIF results to GitHub Security tab

**Suggested workflow:**
```yaml
name: OSV Vulnerability Scan
on:
  schedule:
    - cron: "0 2 * * 0"  # Sunday 2am UTC
  workflow_dispatch:
jobs:
  osv-scan:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v6
      - uses: google/osv-scanner-action/osv-scanner-action@v2
        with:
          scan-args: |-
            --lockfile=requirements/base.txt
            --lockfile=superset-frontend/package-lock.json
            --format=sarif
            --output=osv-results.sarif
      - uses: github/codeql-action/upload-sarif@v4
        with:
          sarif_file: osv-results.sarif
```

**Acceptance criteria:**
- [ ] Weekly scan covers both Python and JavaScript dependencies
- [ ] Results uploaded to GitHub Security tab
- [ ] Can also be triggered manually via `workflow_dispatch`
- [ ] Does not block PRs (informational only)
