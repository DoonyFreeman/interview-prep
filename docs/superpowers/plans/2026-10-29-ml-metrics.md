# ML Metrics Lessons Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development. Separate ownership: one author per lesson and its temporary question fragment; one author for diagram sources/assets; the lead integrates shared JSON files and performs verification.

**Goal:** Add two clear Russian lessons covering all 11 mentor ML-metrics checkpoints, with worked examples, seven readable diagrams, interview questions and MCQ, for two study days.

**Architecture:** Extend the existing `llm` content course using the current metadata → Markdown → question/test/exam seed pipeline. Use the established HTML → PNG lesson-media pipeline; no new API, table, production dependency or Markdown widget. Existing content-integrity and public-lesson API tests verify registration, anchors, questions, media and answer hiding.

**Tech Stack:** Markdown/JSON, HTML/CSS/SVG authored diagrams, existing Chrome renderer, FastAPI content loader, pytest, React/Vite reader.

## Task 1 — Author lessons and assessments

- [x] Create `content/courses/llm/03-ml-classification-metrics.md`, slug `ml-classification-metrics`, 55 minutes reading, 7 concepts: task-types, confusion-matrix, accuracy-imbalance, precision-recall, f1-score, decision-threshold, metric-averaging.
- [x] Create `content/courses/llm/04-ml-curves-regression.md`, slug `ml-curves-regression`, 60 minutes reading, 7 concepts: roc-curve, roc-auc, precision-recall-curve, average-precision, regression-errors, r2-score, metric-choice.
- [x] For each concept author one open interview question/reference answer and two meaningful MCQ; additionally two applied exam questions per lesson. Store worker fragments under `/tmp/interview-prep-ml-metrics/`, then lead merges into course JSON without replacing existing entries.
- [x] Explain terms before formulas, use the 100-ticket example TP=8/FP=4/FN=2/TN=86, distinguish undefined metrics, score/probability, ranking/calibration, averaging, AP/trapezoidal area and R² baseline. Include study route, mentor responses, exercises with solutions, short recap and official sources. Keep RAG expansions outside scope.

## Task 2 — Seven teaching diagrams

- [x] Add seven sources under `scripts/lesson-screens/llm/`: `ml-confusion-matrix`, `ml-accuracy-imbalance`, `ml-threshold`, `ml-roc`, `ml-roc-pr`, `ml-averaging`, `ml-regression`. Reuse existing CSS, large type, explicit axes/units and labels; sources declare `screen-size`.
- [x] Render only the seven new images via `bash scripts/render_lesson_screens.sh llm <names>`; visually inspect all output, fix clipping and misleading numbers. Commit generated lesson media as existing content assets, not build output.

## Task 3 — Integrate content

- [x] Append metadata and question/test/exam maps, preserve existing lessons/slugs. Update course description to four lessons, add lesson-specific official resources to `content/roadmap.json`, update the LLM section in `CLAUDE.md`.
- [x] Match every concept anchor to its exact H2, every image URL to its declared dimensions. Reading metadata is distinct from the suggested 2–3 hours active study per day.

## Task 4 — Verify and review

- [x] Before integration run baseline `.venv/bin/python -m pytest tests/test_content_integrity.py -q` from `backend/`.
- [x] After integration run content-integrity/API checks, `python3 scripts/check_mcq_quality.py --help` then the supported targeted checks, and full backend suite as appropriate.
- [x] Run `npm test` and `npm run build` from `frontend/`; inspect the two rendered lesson pages at desktop and phone sizes, light/dark, image links, ToC and console/network errors using synthetic local preview data only.
- [x] Independently review scope first and content/math/integration quality second; fix confirmed findings and rerun affected checks.
**Release action:** Commit only reviewed task files on `codex/ml-metrics-lessons` and push that branch to the verified `origin`; the workflow deploys only on master. No merge or shared deployment without approval of the reviewed revision/destination.


## Verification record

- Baseline: 13 content-integrity checks passed before integration.
- Integrated content/API/roadmap: 25 checks passed; full backend: 200 passed (one existing dependency deprecation warning).
- Frontend: 85 tests passed; TypeScript/Vite production build passed (existing chunk-size warning). All seven PNGs are present in the build output.
- New question banks pass the option-length quality gate: 28 lesson MCQ, 4 exam MCQ. Existing lesson and question entries are unchanged.
- Independent scope review confirms all 11 mentor groups; independent math/content/integration review has no outstanding findings. Clarified distinct scores in standalone AUC/AP questions.
- Desktop and phone, light/dark: both lessons render, mobile ToC including the R² anchor works, image links load PNGs, the 14-question lesson test starts and gives correct feedback. No browser console errors in the final preview.
- Mobile QA found overflowing inline formulas. They now wrap as text in the two new articles; the phone document width equals the viewport width (354 CSS pixels).
- The local preview uses only a separate disposable SQLite database and a synthetic learner. No production database, external LLM call, migration, merge or deployment was involved.
