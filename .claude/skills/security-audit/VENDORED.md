# Vendored skill: security-audit

This folder is a pinned, reviewed copy of Cloudflare's security audit skill. It lives in the
repository so every developer and every Claude Code session uses exactly the same version.

| | |
| --- | --- |
| Source | https://github.com/cloudflare/security-audit-skill (official Cloudflare repository only; copies under other names exist, don't use them) |
| Path in source | `skills/security-audit/` |
| Pinned commit | `c1c8a8c1471069fb0e188eeaff69b8e8db6564a8` (2026-09-14) |
| License | MIT, Cloudflare, Inc. (`LICENSE` in this folder) |
| Added | 2026-11-27 |

## Review done before adding

- The files are byte-for-byte the upstream files at the pinned commit, plus `LICENSE` and this note.
- The two scripts (`validate-findings.cjs`, `validate-coverage-ledger.cjs`) only read local JSON
  files with Node's `fs`, `path` and `util`. They make no network calls and run no commands.
- `SKILL.md` is defensive: it requires an OS-enforced sandbox before running any target code,
  forbids probing deployed systems, and writes audit output **outside** the repository by default.

## How it is used here

See "Security audit" in `CLAUDE.md` and `docs/milestones/README.md`. In short: at the end of every
security-relevant roadmap step (3, 4, 5, 6, 7, 9), run it in full audit mode. Any confirmed
Critical or High finding fails the step's gate.

## Updating

Never edit these files in place. To update:

1. Read the upstream changes between the pinned commit and the new one.
2. Replace the folder's upstream files with the new commit's `skills/security-audit/`.
3. Update the pinned commit above, and say in the pull request what changed and why it is safe.
