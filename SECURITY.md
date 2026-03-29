# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.4.x   | Yes       |
| < 0.4   | No        |

## Scope

The following areas are in scope for security reports:

- **Cryptographic operations**: Ed25519 signatures, X25519 key agreement, AES-256-GCM encryption, ECDHE forward secrecy (`hermes/crypto.py`)
- **Bus integrity**: message sequencing, write vectors, replay detection (`hermes/bus.py`, `hermes/integrity.py`)
- **Authentication**: Ed25519 challenge-response in Hub Mode (`hermes/hub.py`)
- **Key management**: keypair generation, storage, fingerprint verification
- **Protocol-level attacks**: message tampering, injection, spoofing, namespace impersonation

Out of scope:

- Denial of service via large bus files (known limitation of file-based architecture)
- Social engineering or phishing
- Issues in third-party dependencies (report upstream)
- Theoretical post-quantum attacks (PQC migration is planned but not yet implemented)

## Reporting a Vulnerability

**Do not open a public issue for security vulnerabilities.**

1. Email: danielreyesma@gmail.com with subject line `[HERMES SECURITY]`
2. Or use [GitHub Security Advisories](https://github.com/dereyesm/hermes/security/advisories/new)

Include:
- Description of the vulnerability
- Steps to reproduce
- Impact assessment
- Suggested fix (if any)

## Response Timeline

- **Acknowledgment**: within 48 hours
- **Initial assessment**: within 7 days
- **Fix for critical issues**: within 30 days
- **Fix for non-critical issues**: within 90 days

## Disclosure Policy

We follow coordinated disclosure:

1. Confirm the issue and determine its impact
2. Develop and test a fix
3. Release the fix and publish an advisory
4. Credit the reporter (unless they prefer anonymity)

## Credit

Security researchers who report vulnerabilities responsibly will be credited in the release notes and security advisory unless they request otherwise.
