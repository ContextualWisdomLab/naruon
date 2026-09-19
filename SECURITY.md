# Security Policy

## Code Quality

- **Standard findings:** 0건
- **AI Findings:** 0건

## Vulnerability Reporting

Report suspected vulnerabilities through GitHub private vulnerability
reporting:
https://github.com/ContextualWisdomLab/naruon/security/advisories/new

If GitHub private reporting is unavailable, email `security@naruon.net` with:

- affected component and version or commit SHA
- reproducible impact and proof of concept
- whether the report affects production data, credentials, or tenant isolation

We acknowledge high and critical reports within 3 business days, keep the
reporter informed while triage is active, and coordinate disclosure after a
fix or mitigation is available. Do not publish exploit details before the
private report is resolved.

## Dependabot

- **Malware:** 0건
- **Vulnerabilities:** 0건

## Code Scanning

- **Code scanning:** 0건

## Secret Scanning

- **Secret scanning:** 잠정적으로 0건으로 만들 것

## Strix Security Scan

- **Strix Security Scan:** Medium 이상 모두 수정 (Medium 까지는 한국 법령이 요구하는 강제 사항이 포함되어 있음)
- Strix Security Scan은 `ContextualWisdomLab/.github`의 central required
  workflow가 제공합니다. 이 저장소는 repo-local Strix workflow나 전용 gate
  script를 복제하지 않습니다.
- Pull request scans that need repository secrets must use trusted-base
  `pull_request_target` execution: workflow scripts and dependencies come from
  GitHub API-materialized base commit content, while pull request head files are
  fetched as Git objects and scanned only as copied data.
- If a changed pull request file cannot be read from the PR head, the Strix gate
  fails closed and must not substitute trusted-base file contents.

## CI/CD Enforcement

- Checks가 통과되어야 Merge 가능하도록 Branch Protection Rule에 의해 강제됩니다.
- GitHub Actions는 full commit SHA pinning을 사용하고 scanner finding을
  `continue-on-error`로 숨기지 않습니다.
- Auth/key, mail relay/proxy, PostgreSQL replication, APM, gateway hardening은
  `docs/operations/` 문서의 Confirmed/Hypothesis 경계를 따릅니다.
