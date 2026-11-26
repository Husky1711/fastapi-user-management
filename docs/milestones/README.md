# Milestone gate

Every roadmap step is a milestone. A milestone is **not finished when its tests pass**: it is
finished when it passes this gate and the owner approves the report. Only then does the next
milestone start.

Why: tests written by the author prove the code does what the author expected. The gate
attacks the milestone from four other directions: a tester trying to break it, a user trying
to use it, the old code checking nothing was forgotten, and a reviewer who doubts it.

## The five checks

| # | Check | Question it answers | Evidence required |
| --- | --- | --- | --- |
| 1 | **Automated** | Does it build, lint, type-check and pass every test? | Link to a green CI run: lint, `mypy --strict`, tests with coverage ≥ 90 %, Compose smoke test |
| 2 | **Tester** | Does it survive bad input, edge cases and attacks? | A test plan written **before** the code, each case linked to an automated test |
| 3 | **User** | Does it work end to end on the real stack, the way a client uses it? | Scripted scenarios in `tests/e2e/` run in CI against `docker compose` |
| 4 | **Cross-check vs old code** | Did we keep everything worth keeping and fix everything that was wrong? | Table: each old endpoint / table / behaviour in scope → kept, improved or dropped, with a reason. Old code is on `main` at `209a9bd` |
| 5 | **Independent review** | Would a doubtful senior engineer sign this off? | A review by someone (or a fresh AI session) who did not write the code, listing findings and a verdict |

**Rules**

- Every check is **PASS** or **FAIL**. There is no "mostly".
- A finding of severity *high* or *critical* in any check is an automatic FAIL.
- On FAIL: fix, re-run the failed checks, and update the report. Do not start the next milestone.
- Checks 2 and 3 must be automated tests wherever possible, so they keep running in every
  later milestone (regression protection), not just once.
- The report lives at `docs/milestones/step-<n>.md` and is part of the milestone's PR.
- The owner reads the report, then approves the PR (or pushes back). Merge only after approval.

## Report template

Copy into `docs/milestones/step-<n>.md`:

```markdown
# Milestone <n>: <title> — gate report

- Branch / PR: <link>
- CI run: <link>
- Verdict: PASS | FAIL

## 1. Automated — PASS | FAIL
<lint / typecheck / tests / coverage / compose results>

## 2. Tester — PASS | FAIL
| # | Scenario (written before the code) | Expected | Test | Result |

## 3. User — PASS | FAIL
| # | Scenario on the real stack | Steps | Expected | Result |

## 4. Cross-check vs old code — PASS | FAIL
| Old (main @ 209a9bd) | New | Decision | Reason |

## 5. Independent review — PASS | FAIL
| # | Finding | Severity | Resolution |

## Open items carried forward
<anything consciously deferred, with the step that will handle it>
```
