# Add the widget index to the messages store

Status: draft
Worktree: ../wv-plansyntax
Branch: build/plan-syntax

## Objective

Give the messages store a widget index so a wake-up
handoff can name the widgets a message touches without
scanning every row. The work is the store change, its
payload exposure, and the tests that pin both; it ends
when a message carrying widget references answers with
their index entries and the full gate is green.

For a message whose widgets carry weights $w_i$ and
scores $x_i$, the summary score $s$ is the weighted mean:

$$
s = \frac{\sum_i w_i x_i}{\sum_i w_i}
$$

Two stores could hold the index:

| Store | Owns the lifecycle | Verdict |
| --- | --- | --- |
| messages store | yes | the index lives here |
| registry store | no | left unchanged |

## Rulings

- The index lives in the messages store — it already owns
  the lifecycle rules the index must follow.
- The header carries no `Created:` field; the filename's
  date prefix is the single source for the plan's date.
- Answers to open questions move here when they land; the
  question that produced a ruling is checked in the same
  edit.

## Steps

### Step 1 — Store and payload

The store gains the index table and the payload gains
the two semantic sections. Reading a plan that lacks
either section answers empty, never an error — the same
degradation the steps already get. The failure this step
removes, verbatim from the current build:

> KeyError: 'open_questions'
>   File "server/server.py", line 812, in plan_payload

The probe prints `total: $0` when idle, and the fallback
costs $5 while the upgrade costs $10 — neither price is
math, and the renderer must leave both alone.

files: lib/plans/parser.py, server/server.py
verify: .venv/bin/python -m unittest tests.test_plans
done when: the payload carries open_questions and critical_files for this fixture

### Step 2 — Renderer treatment

The plan body renders the index summary inline; the
node-level check exercises the swap end to end:

```bash
bun viewer/tools/test-math.ts
```

files: viewer/client/src/sections/plans/PlanBody.tsx
verify: unverifiable — the swap is visual; the node tool covers structure, not pixels
done when: a math-bearing plan shows rendered formulas or their source text, never a hole

## Open questions

- [ ] Which store holds the index?
  Recommendation: the messages store — it already owns the
  lifecycle rules.
- [x] Does the header gain a `Created:` field?
  Answered under Rulings: the filename date prefix
  carries it.

## Critical files

- `lib/plans/parser.py` — the parser the payload comes from
- `viewer/client/src/sections/plans/PlanBody.tsx`
- `tests/test_plans.py`
