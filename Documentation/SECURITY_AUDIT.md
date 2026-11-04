# CodeRadar — Security Architecture & Vulnerability Audit

This document details the threat models, security controls, and audit findings for the CodeRadar platform.

---

## 1. Threat Modeling & Attack Vectors

| Attack Vector | Risk | Mitigation in CodeRadar |
|---|---|---|
| **Malicious Git Hooks Execution** | Remote Code Execution via poisoned `.git/hooks` in cloned repos | Clones run with `-c core.hooksPath=/dev/null` ensuring local hook scripts are completely bypassed. |
| **Local Protocol Escalation** | Arbitrary file read via `file://` or submodules | Git operations run with `-c protocol.file.allow=never` disabling local filesystem protocol access. |
| **Server-Side Request Forgery (SSRF)** | Probing internal networks or cloud metadata APIs (e.g. `169.254.169.254`) | URL scheme validation (`https`, `git` only), private IP / RFC 1918 range blocking, and pre-clone DNS resolution verification. |
| **Git Command Injection** | Shell argument injection via malicious repository URLs | Subprocesses invoke `git` as an argument array `["git", ...]` directly without shell expansion (`shell=False`). |
| **Denial of Service (Resource Exhaustion)** | Ingesting massive repositories (millions of commits or files) | Strict limits enforced: `CLONE_TIMEOUT_SECONDS=300`, `MAX_REPO_SIZE_MB=500`, `MAX_COMMITS_PER_RUN=50000`, `MAX_REPO_FILE_COUNT=50000`. |
| **Privilege Escalation** | Unauthorized users executing scans or modifying settings | PBKDF2 password hashing, HS256 JWT validation, and RBAC guards checking project memberships (`owner`, `analyst`, `viewer`). |
| **Clickjacking / MIME Sniffing** | Browser-side UI manipulation and XSS | Injected security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`). |
| **Concurrent Run Corruption** | Multiple simultaneous scans clobbering database records | Per-project threading locks prevent concurrent analysis on the same repository. |
| **Stale Crash Lockout** | Unhandled server crash leaving runs permanently stuck in `running` | Server startup routine `recover_stale_runs_on_startup()` automatically marks orphaned runs as `failed`. |

---

## 2. Authentication & Credential Storage

- **Algorithm**: PBKDF2-HMAC-SHA256
- **Work Factor**: 600,000 iterations (exceeding OWASP recommendations)
- **Salt**: 16 bytes cryptographically strong pseudo-random salt per user
- **Session Tokens**: HS256 JSON Web Tokens with embedded user claims (`sub: user_id`), valid for 7 days by default.

---

## 3. Role-Based Access Control (RBAC) Matrix

| Operation | Anonymous (Unassigned) | Viewer | Analyst | Owner / Admin |
|---|---|---|---|---|
| View Dashboard & Graph | Allowed (Legacy/Demo) | Allowed | Allowed | Allowed |
| Run Simulation | Allowed (Legacy/Demo) | Denied | Allowed | Allowed |
| Trigger Rescan | Allowed (Legacy/Demo) | Denied | Allowed | Allowed |
| Cancel Analysis Run | Denied | Denied | Allowed | Allowed |
| Update Risk Config | Denied | Denied | Allowed | Allowed |
| Update Rescan Schedule | Denied | Denied | Denied | Allowed |
| Manage Members (Add/Remove) | Denied | Denied | Denied | Allowed |
| Delete Project | Denied | Denied | Denied | Allowed |
| View Audit Logs | Denied | Denied | Allowed | Allowed |

*Note: For backwards compatibility and instant demo exploration, projects with zero registered members allow read access. As soon as a user registers or claims project ownership, strict RBAC enforcement takes effect.*

---

## 4. Audit Logging Architecture

All state-altering actions write an immutable record to the `audit_logs` table via `auth_service.log_audit`:
- **Captured Attributes**: `id`, `actor_id`, `actor_email`, `action`, `resource_type`, `resource_id`, `details` (JSON), `ip_address`, `created_at`.
- **Audited Events**:
  - `user_registered`, `user_logged_in`
  - `start_rescan`, `cancel_analysis`
  - `update_risk_config`, `update_schedule`
  - `add_project_member`, `remove_project_member`
  - `delete_project`
