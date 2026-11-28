# 0009. Email domains are ASCII only (no IDN) for now

- Status: Accepted
- Date: 2026-11-27

## Context

`app/core/emails.py` accepts only ASCII domains, so `grace@exämple.com` is refused (step 2
review R1-18). Internationalised domain names (IDN) can be accepted by converting them to
their ASCII form (IDNA / punycode, `xn--exmple-cua.com`) before storing. Doing that well has
costs: Python's built-in `idna` codec implements the outdated IDNA 2003 rules (wrong for some
scripts), the correct IDNA 2008 rules need the third-party `idna` package (a new runtime
dependency), and look-alike (homograph) domains need a policy for display. Internationalised
*local parts* (SMTPUTF8) are rarer still and many mail servers refuse them.

## Decision

Keep refusing non-ASCII domains and local parts. The error is the normal
`user.email_invalid` (422). Users with an IDN domain can register with its ASCII form
(`xn--…`), which every mail system accepts.

## Consequences

- Simple, predictable matching (`citext` compares ASCII case-insensitively).
- A small number of users must type the punycode form. If a product needs IDN, add the
  `idna` package (owner approval: new runtime dependency), convert to ASCII in
  `normalize_email`, store the ASCII form, and add a homograph display rule; existing rows
  need no migration.
