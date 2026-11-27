# Milestone 2: Database foundation

- PR: #4
- Latest CI run (automatic report): https://github.com/Husky1711/fastapi-user-management/actions/runs/45933396263 (commit 99ae3c2; later commits change docs only)
- Verdict: **GATE IN PROGRESS** (all sections ✅)

Scenario plans below were written **before** the code (process rule). Results are filled in as
each section passes in CI. Ids map to test names `test_s2_<section>_<nn>_...`; *CI step* means a
named step in the CI workflow.

**C4 (authentication) and C5 (authorization) at the HTTP level are N/A for the whole step:** step
2 adds no endpoints. Authorization *data* (roles, permissions, memberships) is covered under
C10 data integrity; enforcement starts in step 5.

## Section log

| # | Section | Status | Scenarios (pass / total) | Notes |
| --- | --- | --- | --- | --- |
| 2.1 | Database access: engine, sessions, one unit of work per request, model base | ✅ | 11 / 11 | CI run 45926673123; review fixes: see header run |
| 2.2 | Schema: 10 tables, constraints, indexes, triggers | ✅ | 25 / 25 | CI run 45928196703; review fixes: see header run |
| 2.3 | Alembic migrations: async env, initial schema, round trip, parity with models | ✅ | 9 / 9 | CI run 45928196703; review fixes: see header run |
| 2.4 | Seed data: permissions and system roles | ✅ | 6 / 6 | CI run 45928196703 |
| 2.5 | Repositories with tenant scoping | ✅ | 14 / 14 | CI run 45928783140; review fixes: see header run |
| 2.6 | Password hashing, input rules and the `create-admin` command | ✅ | 16 / 16 | CI run 45930672394; review fixes: see header run |
| | **Total** | | **81 / 81** | 72 planned + 9 added after review round 1 |

## Design decisions for this step

- **One session per request; one unit of work per service call.** `get_db` yields the session;
  dependencies only read; the service writes inside `transaction(session)`
  (`app/infra/database.py`), which continues the transaction the dependencies' reads began
  and commits before the response is built (a failed commit is an error, never a 200).
  The first design (the service calling `session.begin()`) failed as soon as a dependency had
  read: review finding R1-01. Rule written in ARCHITECTURE §2.
- **Timestamps come from the app clock** (`app.core.clock.now()`); server defaults are only a
  fallback, and the `updated_at` trigger covers bulk updates. Every CHECK that compares two
  timestamps (`expires_at > created_at`) therefore compares values from one clock (R1-05).
- **Rule errors are client errors**: `InvalidEmail` and `WeakPassword` are `AppError`s (422,
  codes `user.email_invalid`, `user.password_weak`), so services raise only `AppError`s (R1-02).
- **Migrations take a PostgreSQL advisory lock**, so replicas starting together can't run
  them twice (R1-06).
- **Enum-like columns are `text` + `CHECK`** (SQLAlchemy `Enum(native_enum=False)`), not native
  Postgres enums: adding a value later is a one-line constraint change instead of an
  `ALTER TYPE` that can't run inside a transaction.
- **`updated_at` is maintained by a database trigger**, so bulk `UPDATE`s can't forget it.
- **A membership's role must be a system role or a role of the same organization**, enforced by
  a trigger: a composite foreign key can't express "or a system role (`organization_id IS NULL`)".
- **Role keys are unique per organization, with system roles unique too**, using
  `UNIQUE NULLS NOT DISTINCT` (PostgreSQL 15+).
- **Token hashes are `bytea` of exactly 32 bytes** (SHA-256), not text: half the size of hex,
  and a CHECK refuses anything that isn't a digest. (ARCHITECTURE §4 updated.)
- **Every foreign key has a full index** (a test checks this from the models): partial indexes
  can't serve the cascade when a user or organization is deleted.
- **Sections 2.2–2.4 were verified together**: the schema's triggers and seed exist only in the
  migrations, so schema tests (2.2) run on the database the migrations (2.3) build.
- **Audit history survives deletions**: `audit_logs` foreign keys are `ON DELETE SET NULL`.
- **Passwords are hashed with Argon2id now** (needed by `create-admin`); login, lockout and
  rehash-on-login arrive in step 3.
- **Email syntax is checked with a small built-in rule set** rather than a new dependency; full
  verification by sending mail is step 6.

## Scenario plan and results

### Section 2.1: Database access

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 2.1-01 | C1 | A request whose dependency reads, then whose unit of work writes and succeeds | Change committed before the response; the next request reads it | test | ✅ |
| 2.1-02 | C9, C10 | A request that writes and then fails | Nothing is committed (rolled back) | test | ✅ |
| 2.1-03 | C10 | Two writes in one request, the second fails a constraint | Neither is kept | test | ✅ |
| 2.1-04 | C7 | Concurrent requests | Each gets its own session; no shared state | test | ✅ |
| 2.1-05 | C1 | Model base | UUID v4 primary keys generated by the app; `created_at`/`updated_at` timezone-aware, from the (injected) app clock | test | ✅ |
| 2.1-06 | C1 | Metadata naming convention | Every constraint/index has a deterministic name (needed for migrations) | test | ✅ |
| 2.1-07 | C9 | Database unreachable when a request needs it | Generic 500 problem JSON; no DSN or password in response or log | test | ✅ |
| 2.1-08 | C8 | Session factory created twice (lifespan restart) | New factory bound to the new engine | test | ✅ |
| 2.1-09 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| 2.1-10 | C7, C10 | A dependency reads, then the unit of work writes and fails | Nothing kept; the next request starts clean (added: R1-01) | test | ✅ |
| 2.1-11 | C9 | Connection pool exhausted (one connection held) | Waits `pool_timeout`, then a generic 500; recovers when the connection is freed (added) | test | ✅ |
| — | C2, C3 | N/A: the access layer takes no user input | | | |
| — | C6 | Covered by 2.1-07 (no secret leakage on failure) | | | |
| — | C11 | Covered by 2.3-05 (migrated real stack), 2.6-12 (CLI on the real stack) and 2.6-15 (route → service) | | | |

### Section 2.2: Schema

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 2.2-01 | C1 | Insert a valid row in every table | Accepted, with defaults filled | test | ✅ |
| 2.2-02 | C10, C2 | Two users with emails differing only in case | Second rejected (`citext` unique) | test | ✅ |
| 2.2-03 | C2 | Invalid status / purpose / role values | Rejected by CHECK constraints | test | ✅ |
| 2.2-04 | C3 | Email at 254 chars accepted; 255 rejected; empty rejected | As stated | test | ✅ |
| 2.2-05 | C10 | Same user added twice to one organization | Rejected (unique membership) | test | ✅ |
| 2.2-06 | C10, C6 | Membership with a role from another organization | Rejected by trigger | test | ✅ |
| 2.2-07 | C10 | Membership with a system role, or a role of the same org | Accepted | test | ✅ |
| 2.2-08 | C10 | Two system roles with the same key; two custom roles with the same key in one org | Both rejected; the same key in different orgs is accepted | test | ✅ |
| 2.2-09 | C10 | Delete a user | Memberships, sessions, one-time tokens deleted; audit rows kept with actor set to null | test | ✅ |
| 2.2-10 | C10 | Delete an organization | Memberships, custom roles, invitations deleted; audit rows kept with org null | test | ✅ |
| 2.2-11 | C10 | Delete a role still used by a membership or invitation | Rejected (RESTRICT) | test | ✅ |
| 2.2-12 | C10 | Delete a permission granted to a role | Grant removed with it (CASCADE) | test | ✅ |
| 2.2-13 | C2 | Permission key not in `resource:action` form | Rejected | test | ✅ |
| 2.2-14 | C10 | Two pending invitations for the same email and org | Rejected; allowed again once the first is accepted or revoked | test | ✅ |
| 2.2-15 | C10, C6 | Token hashes (sessions, one-time tokens, invitations) | Unique; stored as 32-byte hashes, never the token | test | ✅ |
| 2.2-16 | C3 | Timestamps | All `timestamptz`; a naive datetime is rejected by the model layer | test | ✅ |
| 2.2-17 | C1 | `updated_at` after a bulk `UPDATE` | Changed by the trigger | test | ✅ |
| 2.2-18 | C3 | `expires_at` not after `created_at` (sessions, one-time tokens, invitations) | Rejected (CHECK) | test | ✅ |
| 2.2-19 | C3 | Negative `failed_login_count` | Rejected (CHECK) | test | ✅ |
| 2.2-20 | C1, C10 | Every foreign key has a full (non-partial) index starting with its columns and declares `ON DELETE`; every declared index exists | Checked from the models and the catalog | test | ✅ |
| 2.2-21 | C7 | Two concurrent inserts of the same email | Exactly one succeeds | test | ✅ |
| 2.2-22 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| 2.2-23 | C3 | Org name 200/201, slug 63/64, role key 2/50/51, role name 100/101; IPv6 accepted, non-IP refused | As stated (added) | test | ✅ |
| 2.2-24 | C10 | Every table with `updated_at` has the trigger (catalog); it fires on organizations and memberships too | Exact set; values move (added) | test | ✅ |
| 2.2-25 | C10 | Rows written with an injected clock far from the database's | All accepted; timestamps equal the injected time (added: R1-05) | test | ✅ |
| — | C8 | Covered by 2.2-05/08/14/21 (repeating an insert is rejected, not duplicated) | | | |
| — | C9 | N/A: schema rules are enforced inside the database itself | | | |
| — | C11 | Covered by 2.3-05 | | | |

### Section 2.3: Migrations

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 2.3-01 | C1 | `alembic upgrade head` on an empty database | All tables, constraints, triggers, `citext` created | CI step + test | ✅ |
| 2.3-02 | C10 | `downgrade base`, then `upgrade head` again | Clean round trip; nothing left behind after downgrade | CI step | ✅ |
| 2.3-03 | C10 | Models vs migrated database | No difference (Alembic compare) | test | ✅ |
| 2.3-04 | C8 | `upgrade head` run twice | Second run does nothing | CI step | ✅ |
| 2.3-05 | C11 | Developer runs `make migrate` on the Compose stack | Schema created; app ready | CI step | ✅ |
| 2.3-06 | C9 | Migration against an unreachable database | Fails with a clear error, no password in the output | CI step | ✅ |
| 2.3-07 | C7 | Two `upgrade head` runs at once on an empty database | Both exit 0; migrations run once; 3 system roles (added: R1-06) | CI step | ✅ |
| 2.3-08 | C10 | Downgrade of the seed while a membership uses a system role | Refused by the foreign key; still at head (added) | CI step | ✅ |
| 2.3-09 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| — | C2, C3, C6 | N/A: migrations take no user input | | | |

### Section 2.4: Seed data

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 2.4-01 | C1 | After migration | Every permission in `app/core/permissions.py` exists; roles owner, admin, member exist as system roles | test | ✅ |
| 2.4-02 | C1 | Role grants | owner = all; admin = all except `org:delete`, `org:transfer`, `roles:manage`; member = `org:read`, `members:read` | test | ✅ |
| 2.4-03 | C10 | Code list and database agree | No permission in one but not the other | test | ✅ |
| 2.4-04 | C8 | Seed migration re-run after downgrade | Same rows, no duplicates | CI step 2.3-02 + test | ✅ |
| 2.4-05 | C6 | Member role | Holds no write permission | test | ✅ |
| 2.4-06 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| — | C2, C3, C7, C9, C11 | N/A: fixed data shipped with the code; no input, no concurrency, no runtime dependency | | | |

### Section 2.5: Repositories

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 2.5-01 | C1 | Users: add, get by id, get by email (case-insensitive) | Found / None | test | ✅ |
| 2.5-02 | C1 | Users: soft-deleted users are not returned by default lookups | None | test | ✅ |
| 2.5-03 | C1 | Organizations: add, get by id, get by slug | Found / None | test | ✅ |
| 2.5-04 | C1 | Roles: system roles; role by key for an org (custom first, then system) | Correct role | test | ✅ |
| 2.5-05 | C1 | Roles: permissions of a role, asked for by an org that can see it | Exact set | test | ✅ |
| 2.5-06 | C1 | Memberships: add, get for (user, org) | Found / None | test | ✅ |
| 2.5-07 | C5, C6 | Org A never gets org B's memberships, roles or role permissions (role id passed through org A) | Isolation holds | test | ✅ |
| 2.5-08 | C3 | Listing: limit 1, limit 100 with 101 rows, offset past the end, offset = max | Correct page and total | test | ✅ |
| 2.5-09 | C2 | Limit 0 / above max / negative offset | Rejected before querying | test | ✅ |
| 2.5-10 | C1 | Members of an org with their roles | Loaded in a fixed number of queries (no N+1) | test (query counter) | ✅ |
| 2.5-11 | C6 | Every repository (found automatically) declares its unscoped methods; all others require `organization_id` by keyword | Signature check | test | ✅ |
| 2.5-12 | C10 | Repository methods never commit | Invisible before commit and after rollback; visible after the caller commits | test | ✅ |
| 2.5-13 | C8 | Same lookup twice | Same result, no writes | test | ✅ |
| 2.5-14 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| — | C7 | Covered by 2.2-21 (concurrency is enforced by constraints, not repositories) | | | |
| — | C9 | Covered by 2.1-07 | | | |
| — | C11 | Covered by 2.6-12 (CLI uses the repositories on the real stack) | | | |

### Section 2.6: Password hashing, input rules, `create-admin`

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 2.6-01 | C1 | Hash then verify a password | Verifies; hash is Argon2id with the configured parameters | test | ✅ |
| 2.6-02 | C6 | Same password hashed twice | Different hashes (random salt) | test | ✅ |
| 2.6-03 | C6 | Wrong password; malformed hash | Not verified; no exception leaks | test | ✅ |
| 2.6-04 | C2, C3 | Password of 11 / 12 / 128 / 129 characters; control characters; spaces | 11, 129 and control characters rejected (422 `user.password_weak`); 12, 128 and spaces kept | test | ✅ |
| 2.6-05 | C2 | Unicode password (normalised NFKC) | Same password typed two ways verifies | test | ✅ |
| 2.6-06 | C9 | Hashing from async code | Runs in a worker thread (doesn't block the event loop) | test | ✅ |
| 2.6-07 | C2 | Emails: valid forms; missing `@`, spaces, empty parts, too long | Valid normalised (lower-cased domain); invalid rejected | test | ✅ |
| 2.6-08 | C1 | `create-admin` with email and password on stdin | Platform admin created, email verified, exit 0 | test | ✅ |
| 2.6-09 | C8 | `create-admin` for an existing email | Exit 1, nothing changed, clear message | test | ✅ |
| 2.6-10 | C6 | Password never on the command line | Only accepted on stdin; not in output or logs | test | ✅ |
| 2.6-11 | C2 | Weak password or invalid email | Exit 2 with a clear message; nothing created | test | ✅ |
| 2.6-12 | C11 | Operator runs `create-admin` in the Compose stack | Admin row exists with an Argon2id hash | CI step | ✅ |
| 2.6-13 | C9 | `create-admin` with the database refused, unresponsive (connect timeout) or not migrated | Exit 1 within seconds, clear message, no password in output | test | ✅ |
| 2.6-14 | C7 | Two concurrent creates with one email (different case) through the service | Exactly one user, exactly one `Conflict` (added) | test | ✅ |
| 2.6-15 | C11 | Route whose dependency reads, then calls the service (the step 3 shape) | 200 created; then 409 `user.email_taken`, 422 `user.email_invalid` / `user.password_weak` as problem JSON (added: R1-01, R1-02) | test | ✅ |
| 2.6-16 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| — | C10 | Covered by 2.6-09 and 2.6-11 (failures change nothing) | | | |

## Failure log

| # | Found by | What failed | Cause | Fix | Status |
| --- | --- | --- | --- | --- | --- |
| F1 | CI type check (run 45926311467) | `mypy --strict` on 2.1 tests: untyped `postgresql.dialect()` call, `**overrides` typed `int \| float` passed to `DatabaseSettings`, list of factories typed `object` | Test helpers written loosely | Dialect taken from an unconnected engine; explicit keyword parameters; precise list type | Fixed (run 45926673123) |
| F2 | CI test (run 45927754158) | 2.2-07 and 2.2-11 failed with a foreign-key error | Tests inserted memberships for users that were never added | Users added before their memberships | Fixed (run 45928196703) |
| F3 | CI test, 2.3-03 name parity (run 45927754158) | Every CHECK in the database was named twice over (`ck_users_ck_users_status`) | Alembic applies the target metadata's naming convention to explicit CHECK names again | Names wrapped in `op.f()` in the migration (not yet merged, so edited in place) | Fixed (run 45928196703) |
| F4 | CI type check (run 45927754158) | `mypy --strict`: untyped lambda calls in 2.2-15 | Lambdas in an unannotated dict | Dict annotated `dict[str, Callable[[bytes], Base]]` | Fixed (run 45928196703) |
| F5 | Self-review before tests ran | `sessions.user_id`, `one_time_tokens.user_id` and `invitations.organization_id` had only partial indexes | Indexes designed for the "active rows" query only | Full indexes; 2.2-20 now checks every foreign key | Fixed (run 45928196703) |
| F6 | CI test (run 45928783140, coverage) | `MembershipRepository.add` and `list_for_user` had no test (exit criterion: every repository method has one) | Missed in the plan | Test 2.5-06 extended | Fixed |
| F7 | CI type check / test (run 45929425304) | Hasher spy failed (`PasswordHasher` attributes are read-only); `mypy` on `cli.getpass`; service test hit "transaction already begun" | Spy patched a slotted object; test reused a session mid-transaction | Spy subclass swapped in; `getpass.getpass` patched by path; test commits its setup first. That treated the symptom: the design itself was wrong (review R1-01), replaced by `transaction(session)` | Fixed (run 45929858848; design fixed after review) |
| F8 | CI test (runs 45929858848, 45930272706) | 2.6-09 read attributes of an object the expected rollback had expired | The service's rolled-back transaction expires every object in the session (SQLAlchemy behaviour) | Ids read before the call; rule documented in ARCHITECTURE §2 and the `transaction` docstring (R1-01) | Fixed (run 45930672394) |
| F9 | CI type check (run 45932585174) | `mypy --strict`: untyped SQLAlchemy `get_current_parameters` call | Library method without type hints | Targeted ignore with the reason | Fixed |
| F10 | CI test (run 45932943098) | Step 1 test 1.3-33 failed (`dropped 16 >= 40`), then 5 later tests failed with `queue.Full` | Flaky test: it assumed the writer thread had taken its first record before the burst; on a slow runner the dropped counter was reset by the "records dropped" notice mid-burst. No cleanup, so the full queue leaked into later tests (step 1 review R5-05) | The test waits until the writer is stuck, then expects exactly 45 dropped and one notice; cleanup in `finally` | Fixed |

Review round 1 findings (R1-01 to R1-18) and what was done: see "Independent review" below.

**Totals:** 81 scenarios, 81 passed, 0 failing. Failures found and fixed: 10 by CI or
self-review (F1–F10) and 18 by the independent review (R1-xx), of which 14 were fixed in this
step and 4 carried to named steps.

## Gate

Security audit (check 6) is not required for step 2 (required at the end of steps 3, 4, 5, 6,
7 and 9); the password-hashing code it touches is audited with step 3.

### 1. Automated: PASS
Lint, `mypy --strict` (app, tests, scripts, migrations), the migration round trip
(upgrade → downgrade to an empty database → upgrade → repeated upgrade is a no-op), 271 tests
against real PostgreSQL 16 and Redis 7 at 98 % coverage, and the Compose job (migrations and
`create-admin` on the real stack, wrong-password migration, all step 1 checks): green in the
linked run.

### 2. Tester: PASS
Every section covers each category C1–C12 or gives an N/A reason (tables above); every row
names its evidence. Beyond the happy path the plan attacks: case-variant duplicate emails,
cross-organization roles (insert, update, invitation, moving the role), concurrent sign-ups
racing on one email, constraint names drifting between models and database, unindexed
foreign keys, naive datetimes, deleted users' emails, the database being down, passwords
reaching output or logs.

### 3. User: PASS
Real-stack scenarios: 2.3-05 (operator runs the migrations in Compose, seed roles present,
app ready), 2.3-06 (migration with a wrong password fails clearly, password not printed),
2.6-12 (operator creates the first admin in Compose; a second run exits 1 and changes
nothing), plus every step 1 real-stack scenario.

### 4. Cross-check vs old code (`main` @ `209a9bd`): PASS

| Old | New | Decision | Reason |
| --- | --- | --- | --- |
| Integer primary keys | UUID v4 keys (bigint identity for `audit_logs`) | Improved | No guessable ids in URLs |
| `users.role` free text (`super_admin` / `admin` / `user`) | `users.is_platform_admin` + `memberships.role_id` → `roles` → `permissions` | Replaced | Roles are data; one user can belong to several orgs |
| `users.organization_id` nullable, default `1` | `memberships (user_id, organization_id)` unique | Fixed | Every user silently joined org 1 |
| `users.username` unique | Dropped | Dropped | Login is by email (VISION); two identifiers doubled the enumeration surface |
| `users.email String(100)` unique, case-sensitive | `citext`, unique ignoring case, 3–254 characters | Fixed | `A@x.com` and `a@x.com` were different accounts |
| `users.password String(255)` (unsalted SHA-256) | `password_hash` Argon2id (RFC 9106 parameters) | Fixed | Old hashes were crackable |
| `phone_number` default `"0000000000"` | Dropped | Dropped | Fake default data |
| `login_attempts`, `locked_until` (never used) | `failed_login_count` (≥ 0), `locked_until` | Kept | Used by lockout in step 3 |
| `last_login` | Not yet present | Moved | Added with login in step 3 (ROADMAP) |
| `status String(20)` free text | `status` + CHECK; `deleted_at` must match `deleted` | Improved | Invalid states refused by the database |
| No soft delete | `deleted_at`; repositories hide deleted users | Added | Audit history survives account deletion |
| `updated_at onupdate=func.now()` (ORM only) | Database trigger, skipped when nothing changed | Improved | Bulk `UPDATE`s kept stale timestamps |
| `organizations.name` unique, `description` | `name` (not unique) + `slug` (citext, unique, URL-safe); no description | Changed | Two companies can share a name; the slug is the identifier |
| `refresh_tokens`: `is_revoked` + `revoked_at`, `ip_address String(45)`, `device_info` + `user_agent` | `sessions`: `revoked_at`, `ip inet`, `user_agent` (≤ 256), `family_id` for rotation, 32-byte hash | Improved | One source of truth for revocation; typed IP; reuse detection needs the family |
| No index on `user_id` / `expires_at` for tokens | Indexes on every foreign key and every `expires_at` | Fixed | Session checks and cleanup scanned the table |
| Foreign keys without `ON DELETE` | Every foreign key declares it (test 2.2-20) | Fixed | Deleting a user failed or left orphans |
| No schema management at all: tables had to be created by hand (`utils/database.py` only builds the engine) | Alembic migrations with a tested downgrade, a lock against concurrent runs and an operator command | Fixed | No way to create or evolve the schema |
| Naive and aware datetimes mixed | `timestamptz` everywhere; naive values refused | Fixed | Silent time-zone bugs |
| `pool_pre_ping=True`, `pool_recycle=3600` | `pool_pre_ping=True`; no recycle; connect timeout 5 s | Changed | Pre-ping already replaces dead connections; recycling is only needed behind proxies that cut idle connections, and can be added as a setting then |
| No first-admin path (`super_admin` set by hand in SQL) | `python -m app.cli create-admin` (password from stdin) | Added | Safe, repeatable bootstrap |

### 5. Independent review

| Round | Commit | Verdict | Record |
| --- | --- | --- | --- |
| 1 | `175cee2` | **FAIL**: 4 High, 5 Medium, 9 Low; overall 8.2 | [`reviews/step-2-round-1.md`](reviews/step-2-round-1.md) |

Round 1 findings and what was done:

| # | Sev. | Done | Evidence |
| --- | --- | --- | --- |
| R1-01 | High | `transaction(session)` continues a dependency's read transaction; services use it; rule in ARCHITECTURE §2 | 2.1-01, 2.1-10, 2.6-15 |
| R1-02 | High | `InvalidEmail`, `WeakPassword` are 422 `AppError`s with codes | 2.6-04, 2.6-15 |
| R1-03 | High | `permission_keys(*, organization_id, role_id)`; exemption removed | 2.5-05, 2.5-07, 2.5-11 |
| R1-04 | High | Cross-check row corrected (the old code had no schema management) | check 4 table |
| R1-05 | Medium | Timestamps from the app clock | 2.1-05, 2.2-25 |
| R1-06 | Medium | Advisory lock in `migrations/env.py` | 2.3-07 |
| R1-07 | Medium | 2.5-12 now commits and checks visibility | 2.5-12 |
| R1-08 | Medium | Carried to step 3 (ROADMAP) | — |
| R1-09 | Medium | Carried to step 8 (ROADMAP) | — |
| R1-10 | Low | One `EMAIL_MAX_LENGTH` (`app/core/emails.py`) | — |
| R1-11 | Low | Reason comment on the `Any` | `app/models/base.py` |
| R1-12 | Low | Cross-check row for `pool_recycle` | check 4 table |
| R1-13 | Low | Header run link, failure-log order, totals line | this report |
| R1-14 | Low | `DATABASE__CONNECT_TIMEOUT_SECONDS` (default 5) | 2.6-13 |
| R1-15 | Low | Ids compared; the password itself checked | 2.6-11, 2.6-13 |
| R1-16 | Low | Repositories declare `unscoped`; the test finds every subclass | 2.5-11 |
| R1-17 | Low | Docstring corrected; enforcement carried to step 9 (ROADMAP) | `app/models/audit.py` |
| R1-18 | Low | Carried to step 3 (decision and record) | — |

Missing scenarios named by the review were added: 2.1-10, 2.1-11, 2.2-23, 2.2-24, 2.2-25,
2.3-07, 2.3-08, 2.5-08 (largest page, deepest offset), 2.6-04 (control characters, spaces),
2.6-13 (not migrated, unresponsive host), 2.6-14 and 2.6-15.

## Carried forward

- From step 1: none due in step 2.
- To step 3: R1-08 (bound Argon2 concurrency), R1-18 (IDN email decision).
- To step 8: R1-09 (readiness checks the migration head).
- To step 9: R1-17 (append-only audit log in the database).
