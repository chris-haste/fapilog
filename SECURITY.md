# Security Policy

## Supported Versions

The following versions of fapilog are currently supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.7.x   | :white_check_mark: |
| 0.6.x   | :white_check_mark: |
| < 0.6   | :x:                |

## Version Support Policy

- **Current release (0.7.x)**: Full security support
- **Previous minor (0.6.x)**: Security fixes only, 6 months after next minor release
- **Older versions**: No support, upgrade recommended

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### How to Report

1. **Do not** open a public GitHub issue for security vulnerabilities.
2. Email security concerns to: **security@fapilog.dev**
3. Include as much detail as possible:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### What to Expect

- **Acknowledgment**: We will acknowledge receipt of your report within 48 hours.
- **Assessment**: We will investigate and assess the vulnerability within 7 days.
- **Resolution**: We aim to release a fix within 30 days for critical vulnerabilities.
- **Disclosure**: We follow a 90-day responsible disclosure timeline.

### Disclosure Policy

- We will work with you to understand and resolve the issue.
- We will credit you in the security advisory (unless you prefer to remain anonymous).
- We request that you do not publicly disclose the vulnerability until we have released a fix.

## Security Best Practices

When using fapilog in production:

- Keep fapilog and its dependencies up to date.
- Use the `production` preset which enables appropriate security defaults.
- Configure redaction for sensitive fields (PII, credentials, etc.).
- Review the [reliability defaults](docs/user-guide/reliability-defaults.md) for production deployments.

## Known Security Considerations

- **Log content**: Fapilog processes log data which may contain sensitive information. Use redactors to mask PII and credentials.
- **Network sinks**: When using HTTP or cloud sinks, ensure TLS is enabled and credentials are properly secured.
- **Plugin security**: Only install plugins from trusted sources. Third-party plugins are not reviewed by the fapilog maintainers.
