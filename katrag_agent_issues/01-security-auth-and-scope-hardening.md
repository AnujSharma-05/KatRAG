# [P0][Security] Replace development auth/scope scaffolding with deny-by-default identity and authorization

> **Primary reference:** `KatRAG_Perfection_Playbook_README.md`
>
> **Repository:** `AnujSharma-05/KatRAG`
>
> **Agent rule:** Inspect the current repository before editing. Paths/signatures may evolve. Treat the invariants and acceptance criteria in this issue as authoritative; implementation suggestions are guidance.
>
> **Read first**
> - `docs/architecture/categorag-engineering-bible.md`
> - `docs/architecture/KatRAG_System_Design.md`
> - `docs/architecture/KatRAG_Verdict_And_Issues.md`
> - root `README.md`
>
> **Global constraints**
> - Do not add frameworks/infrastructure/models unless required by acceptance criteria.
> - Do not weaken tenant isolation, temporal correctness, provenance, or observability.
> - Prefer typed contracts and deterministic tests over prompt-only behavior.
> - Every reliability/security claim must be backed by a test or reproducible benchmark.
> - Preserve compatibility where reasonable; document intentional breaking changes.
> - Never invent benchmark numbers.


## Problem

The Go gateway currently contains development-grade auth/scope behavior, including a hard-coded HMAC JWT secret and mocked/default scope resolution. This directly conflicts with strong multi-tenant security claims.

An untrusted client may choose a question, but it must never choose the authorization scope used to retrieve evidence.

## Current areas to inspect

Start with:
- `live/backend/internal/**`
- auth/JWT code under `live/backend/internal/auth/`
- scope resolution under Go gateway internals
- `live/backend/cmd/api/`
- middleware that forwards organization/group scope to Python
- `core_backend/src/main.py`
- `core_backend/src/schemas.py`
- `core_backend/src/services.py`

Repository-wide search terms: JWT secret literals, `DEFAULT_ORG`, default org/group values, `X-Scope-`, issuer/audience checks.

## Required behavior / implementation

### Authentication
Introduce a verifier abstraction supporting production asymmetric JWT verification.

Verify at minimum:
- signature
- allowed algorithm
- issuer
- audience
- expiry
- not-before when present

Prefer environment/config keys such as:
`AUTH_ISSUER`, `AUTH_AUDIENCE`, `AUTH_JWKS_URL`.

A clearly separate local-dev identity provider is acceptable, but it must not silently become the production default.

### Canonical authorization scope
Resolve immutable server-side scope:

```text
Scope {
  principal_id
  organization_id
  permitted_group_ids
  role
}
```

Rules:
- unknown principal => deny;
- missing org/group membership => deny;
- membership is server-derived;
- no fallback organization/group;
- user-supplied org/group is never authoritative.

### Internal forwarding
If scope is forwarded to Python:
- strip incoming external `X-Scope-*`;
- overwrite with gateway-generated values;
- document Core as internal-only;
- keep a path for workload-authenticated gateway→Core communication.



## Required tests

- valid JWT accepted
- expired JWT rejected
- wrong issuer rejected
- wrong audience rejected
- unexpected algorithm rejected
- malformed/missing token rejected
- known membership resolves correctly
- unknown user denied
- user cannot choose unauthorized org/group
- caller-supplied scope header cannot override canonical scope

## Acceptance criteria

- [ ] No hard-coded production JWT secret remains in tracked source.
- [ ] Unknown users do not receive fallback scope.
- [ ] Org/group scope is derived server-side.
- [ ] JWT verifier validates issuer, audience, expiry and allowed algorithm.
- [ ] Incoming scope headers cannot override authorization.
- [ ] Positive and negative auth/scope tests exist.
- [ ] Secure production mode and explicit local-dev mode are documented.

## Non-goals

- Building a full IAM product.
- Supporting many SSO vendors.
- UI for membership administration.

## Invariant

> **No authorization decision is based solely on caller-controlled request fields or headers.**
