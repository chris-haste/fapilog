# Security Remediation & Approval Workflows

This guide explains how security scanning and compliance validation integrate with plugin listings and how operators should remediate and approve.

## Signals surfaced
- Compatibility badges (CI-verified versions)
- Vulnerability summary (from pip-audit)
- SBOM (CycloneDX) artifact
- Compliance flags (e.g., PCI-DSS, HIPAA) from validation hooks

## Workflow
1. Review CI artifacts: `security-artifacts` (SBOM, audit).
2. If vulnerabilities exist:
   - Triage severity; create remediation tasks.
   - Update constraints/locks to mitigate if applicable.
   - Track status in issue and re-run scans.
3. Compliance validation:
   - Run organizational checklist; record outcomes.
   - Update `compliance` flags for plugins via provider integration.

## Non-blocking policy
- Scans are non-blocking for development but must pass organizational gates before promotion.
