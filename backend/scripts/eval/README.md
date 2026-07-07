# Skill eval harness

Runs every skill end-to-end against a live, isolated backend on the
shipped default models, capturing the full transcript and every saved
document so the outputs can be graded against a ground-truth fixture set.
This is the permanent home of the harness built for the 2026-07 skills
quality review; every new skill must ship with a scenario here (enforced
by `tests/test_eval_scenarios.py`).

## What's committed vs. what isn't

**Committed (this directory):** the runner, per-skill scenario *prompts*
(`scenarios/<skill>.yaml`), the isolated-server script. Scenario
`grader_notes` may reference fixture *section names and planted-fact ids* —
questions, not answers.

**Never committed:** the fixture documents themselves, the ground-truth
canon (including planted-fact contents — it's the scoring key), run
outputs, and grades. Those live in an external fixtures/eval-history
directory owned by the maintainer. If the scoring key were in the repo,
graders (and models trained on public code) could pattern-match instead of
fact-check.

## Fixture directory contract

The `--fixtures` dir (or `MOMENTUM_EVAL_FIXTURES`) must contain:

- `profile.yaml` — the seeded persona: `role`, `company`, `goals` strings
  (posted to `/onboarding/profile`).
- `manifest.yaml` — `upload:` list of document filenames (uploaded in
  order to `/memory/documents`; the heavy model extracts memories from
  each, so seeding takes a few minutes and real API credits).
- The documents named in the manifest.

## Recipe

```bash
cd backend
TMP=$(mktemp -d)
scripts/eval/serve_isolated.sh "$TMP" &          # 1. isolated backend on :8000
.venv/bin/python -m scripts.eval.run_live_skills check   # 2. every skill has a scenario
.venv/bin/python -m scripts.eval.run_live_skills seed \
    --fixtures <fixtures-dir> --data-dir "$TMP"  # 3. profile + docs + memory extraction
.venv/bin/python -m scripts.eval.run_live_skills run \
    --fixtures <fixtures-dir> --data-dir "$TMP" \
    --label wave1 [skill ...]                    # 4. all skills, or a subset
```

Outputs land in `eval-runs/<date>-<label>/` (gitignored):
`<skill>.transcript.md`, `<skill>.meta.json`, `<skill>.doc-N.md`.
Grading happens outside this repo (agents fact-checking each deliverable
line-by-line against the canon).

## Gotchas

- **Restart the backend after any branch checkout or SKILL.md edit.** The
  skill registry and the heavy-routing command set are cached at import
  time; a stale process silently runs old playbooks or routes a new skill
  to the light model.
- **Cost/time:** roughly $0.05–0.15 and 45–150s per skill run on the
  shipped defaults; runs are serial. Free-tier rate limits stretch this.
- **`--runs N` reuses one seeded workspace**, so run 2 can read documents
  run 1 saved (generated-doc contamination is a known failure mode the
  grounding rules guard against). For grade-bearing repeat runs, prefer a
  fresh data dir + re-seed per run.
- **Scripted intake:** skills that interview the user before drafting get
  `scripted_replies` in their scenario — consumed in order before the
  generic "use your judgment" nudges kick in.

## Trigger-keyword policy (for new skills)

Trigger phrases must be verb+object ("plan the sprint") or document-name
compounds ("launch plan") with **≥2 essential tokens** after filler-word
stripping; single-token triggers are reserved for the acronym allowlist in
`tests/test_trigger_matrix.py`. Bare nouns that occur in ordinary PM chat
(`roadmap`, `strategy`, `metrics`, `pricing`, `vision`, `experiment`,
`okr`, `prd`) must never be triggers on their own. The matcher joins
tokens with whitespace, so hyphenated terms need explicit variants
("premortem", "pre mortem", "pre-mortem"). Every new skill adds: its
keywords to the self-trigger matrix (automatic — read from the registry),
plus realistic positive AND negative utterances to
`tests/trigger_corpus.yaml`.
