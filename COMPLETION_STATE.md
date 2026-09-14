# Completion State

**Branch:** `main` (v6.1.0 audit remediation)
**Assessed:** 2026-09-14
**Test Suite:** 164 passed across 26 modules; `ruff --select F,E9,ASYNC` clean

---

## Remaining Work

All audit findings resolved. Ready for sign-off.

- [x] **D-01 DOM injection closed** — the run JSON dump swaps as `textContent`; HTMX ignores
      `Content-Type` and would otherwise `innerHTML` verbatim model output.
- [x] **D-02 Fingerprint discriminates** — intensity-weighted dominance replaced presence
      counting, which saturated near 100% for every model.
- [x] **D-03 D11 enforced once** — `resolve_paradox()` is the single three-tier
      implementation; three consumers had skipped tiers 2 and 3.
- [x] **D-04 Position bias mitigated** — shuffling is reachable, defaults on, and is drawn
      per iteration rather than per run.
- [x] **D-05 Scenario vocabulary** — closed `dimensions` set validated at load, backfilled
      across all 197 scenarios.
- [x] **D-06 One report layout** — the 790-line legacy template is deleted; failures surface
      as 503 rather than silently swapping documents.
- [x] **D-07 Hygiene** — blocking I/O removed from async paths, dead field deleted, CI added,
      lint gate widened, doc claims asserted.
- [x] **D-08 Permutation guard** — found while reviewing the remediation. Per-iteration
      shuffle on a placeholder-less (D11 tier-3) template mis-mapped every answer. Now
      guarded by `template_supports_option_rendering()`; degrades to a fixed order.
- [x] **D-09 Report profile honesty** — `single_template_name` is empty rather than naming a
      template that expects a different context object.

---

## Completion Criteria

### Architecture

- [x] **Boundary integrity** — no logic leaks across the 7 seams in `boundaries.md`
  - Verified: zero `fastapi`/`starlette` imports in `lib/`. `resolve_paradox()` lives in
    `lib/paradoxes.py`, not in a route. The new `lib/prompt_templates.py` exists specifically
    so `analysis.py` and `report_writer.py` do not import each other.

- [x] **State orthogonality** — no module-level mutable state introduced
  - New caches (`read_prompt_template`) are `lru_cache` over pure reads, documented in
    `state.md` alongside the existing paradox and report-prose caches.

- [x] **Dependency audit** — no packages added. `pytest-asyncio` was already declared and is
      now actually configured (`asyncio_mode = "auto"`).

### Verification

- [x] **Tests pass** — 164 passed, 0 failed, 1 warning (upstream pydyf deprecation)
- [x] **Every fix has a regression test** — each defect is pinned by a test that fails
      without the fix. D-01's and D-08's were both verified by reverting the fix and watching
      the test fail.
- [x] **End-to-end verified** — live instance serves `/`, `/experiments`, fingerprint
      fragment, JSON export, and generates real single-run (61 KB) and comparison (78 KB) PDFs.

### Release

- [x] **Architecture docs updated** — D10 extended, D11 rewritten, D12 and D13 added;
      `boundaries.md` gained Seam 5d; `state.md`, `execution-context.md`, `tech-stack.md` aligned.
- [x] **Doc drift closed permanently** — `scripts/check_doc_claims.py` derives counts from the
      repo and fails CI on disagreement. Two prior "align the docs" commits had left the docs
      misaligned because alignment was reviewed rather than asserted.

### Cleanup

- [x] **Working artifacts removed** — no scratch files or stale diffs in the tree.

---

## Known Follow-Ups

Not defects; tracked in `ROADMAP.md` §5. The dimension backfill is heuristic and wants a human
review pass; the lint gate can widen further after a mechanical `--fix`; `main.py` still holds
all 22 routes in one factory; `list_runs()` remains an O(n) directory scan.

---

## Sign-Off

- Date:
- Owner:
- Notes:
