# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly.

**Do NOT open a public issue for security vulnerabilities.**

Instead, please email the maintainers directly or use [GitHub's private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability).

### What to include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response timeline

- We will acknowledge your report within 48 hours
- We will provide an initial assessment within 1 week
- We will work with you to understand and resolve the issue

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| latest  | Yes                |

## Security Best Practices for Users

- **Never commit `.env` files** — use `env.example` as a template
- **Rotate credentials** if you suspect they have been exposed
- **Use strong passwords** for database connections
- **Keep dependencies updated** — run `pip install --upgrade -r requirements.txt` regularly
