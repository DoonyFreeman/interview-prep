# LangChain and LangGraph learning path

**Goal:** Add five concise Russian lessons that explain concrete execution and data flow, covering the mentor's visible LangChain/LangGraph topics without overloading a study day.

**Architecture:** Append lessons 8–12 to the existing LLM course, retaining all previous progress identifiers. Author Markdown, interview questions and MCQs; use local offline SVG diagrams and two small safe Markdown teaching blocks (collapsed solutions and a step-by-step authored execution trace). No real model calls, new runtime dependencies, database schema changes or deployment.

**Tech Stack:** Existing FastAPI content loader, Markdown/JSON curriculum, React/TypeScript, CSS tokens, Vitest, pytest, dependency-free Python SVG generation.

## Scope and acceptance

- Five days: components/LCEL; structured output and tools; agent decisions; graph/state; persistence/HITL. Each has roughly 25–35 minutes reading plus 20–35 minutes practice, an explicit stopping point and next-day recall.
- One synthetic Mayak shop assistant (order 42, return policy 45 days, unused goods) throughout. Fixed educational results are labelled; no API keys or installed LangChain required to understand the path.
- Every new term has a plain definition and a concrete input/output or responsibility. Distinguish model/runtime/tool, parsed shape/factual correctness, state/snapshot/saver/thread, graph workflow/agent.
- Each concept has one grounded interview question and two plausible MCQs. Existing identifiers and authored records remain unchanged.
- Internal links have short title previews. At least one meaningful local diagram per lesson, accessible titles/descriptions, responsive image enlargement.
- Closed solution blocks use a fenced `solution` language; no raw HTML execution. A fenced `execution` block uses validated JSON data only, with keyboard-native previous/next/reset controls and a state table.
- Correct obsolete LangChain-only-linear wording in the overview without rewriting unrelated RAG content.

## Work and ownership

- [x] Author `08-langchain-components.md`, `09-langchain-contracts.md`, `10-agent-decisions.md` plus metadata/question/test fragments in a task-specific temporary directory.
- [x] Author `11-langgraph-state.md`, `12-langgraph-persistence.md` plus fragments; include one finite execution trace.
- [x] Generate eight offline SVGs using `scripts/build_agent_diagrams.py` under `frontend/public/lesson-media/llm/agents-*.svg`.
- [x] Add content-path regression checks, observe missing-path failure, then integrate fragments into LLM metadata/questions/tests. Check anchors, internal links, local diagrams, compactness and trace structure.
- [x] Add rendering tests for closed solutions, safe data-only traces and invalid data fallback, observe failure; implement teaching components in existing typography/tokens with RU/EN controls.
- [x] Correct the overview and link to the five-day path; update relevant project guidance.
- [x] Run targeted checks, full frontend tests/build and backend curriculum checks. Run an isolated local preview with synthetic authentication, inspect desktop/mobile and light/dark, exercise disclosures/trace/concept navigation/lesson quiz, check runtime errors.
- [x] Obtain independent read-only review of scope, accuracy, UI and security; resolve findings and rerun affected checks.
- [x] Commit only task files and push feature branch if supported. Present exact reviewed revision and local preview; merging/deploying waits for explicit approval.

## Verification commands

From `backend/`: `.venv/bin/python -m pytest tests/test_agent_learning_path.py tests/test_content_integrity.py tests/test_rag_learning_path.py tests/test_content.py`.

From `frontend/`: `npm test` and `npm run build`.

Run `python3 scripts/build_agent_diagrams.py` and confirm deterministic checked-in assets. Browser QA verifies closed solutions before activation, finite trace navigation/reset, no page-wide overflow at 390px and readable full-size SVGs. Confirm existing lessons and reference-answer boundaries remain intact.

## Important edge cases

Invalid trace JSON or indices must not crash the reader; text is rendered without HTML. State values may be empty lists, null, long text or absent keys. Multiple trace components have independent state. No hidden model reasoning is required for ReAct. A tool call is not tool execution or permission. Empty retrieval causes an explicit lack-of-evidence result. Node replay, unknown tools, argument validation, bounded loops and approval rejection are taught. Checkpoint state is not model weights, authentication, or exactly-once side effects.

## Verification and review outcome

- Backend: full suite 208 passed; one existing Starlette/AnyIO deprecation warning. Targeted curriculum/content/roadmap checks: 31 passed.
- Frontend: 124 tests passed; TypeScript/Vite production build passed. Existing large-chunk warning remains. New rendering checks first failed without the teaching blocks, then passed after implementation; excessive nesting is rejected.
- Eight SVG assets parse with accessible title/description and regenerate byte-identically. Rendered contact sheet inspected; diagram contracts aligned with the exact lesson fields and parser output.
- Local UI: five new lessons checked on desktop and phone layouts, light/dark; solutions start closed, keyboard disclosure works, concept previews link to real sections, 8-question lesson quiz gives immediate feedback, trace next/back/reset/end bounds and RU/EN controls work. No console errors in the final preview tab.
- Independent scope review confirmed coverage and internal consistency. Independent code review found one P2: inline ReactMarkdown renderers remounted stateful teaching blocks on parent renders. Reproduced in the browser (step 3 reset to step 1), fixed with stable module-level renderers, and verified that steps and open solutions survive heading navigation. Re-review found no remaining issues.
- Known unrelated limitation: at the existing in-app browser's intermediate default width (~721 CSS px), the unchanged global header is wider than the viewport. Lesson content fits; the tested desktop and phone layouts fit. Header/layout files are outside this change and were not modified.
- No schema, auth, user-state API, external model call or production dependency changes. Preview uses an isolated disposable SQLite database and synthetic account. Production release remains subject to approval of the reviewed feature revision.
