# RAG Learning Path Implementation Plan

**Goal:** Cover the mentor's five RAG topics in three connected, understandable lessons, with definitions, diagrams, worked examples and links to existing concepts.

**Architecture:** Append lessons 5–7 to the existing LLM course, preserving all previous lesson/concept slugs and progress. Use authored Markdown link titles for optional internal concept previews; no new API, database or external service. Technical diagrams are checked-in SVGs generated offline with the standard library.

**Tech Stack:** Existing Markdown/JSON content loader, React/TypeScript, CSS tokens, Vitest, pytest; Python SVG authoring.

## Agreed scope from user request

- Three days recommended: documents/embeddings, search/indexes, evaluation/diagnosis; explicit compressed two-day and overview one-day routes.
- Existing overview remains a prerequisite/reference; no duplicate progress identifiers or changes to earlier lessons.
- Explain terms before use and every formula symbol in words. Follow existing ML lesson rhythm: example → explanation → diagram → calculation → common mistake → exercise/answer.
- Cover all five screenshot topics including IVF, normalized vector metrics, TF-IDF, RRF, NDCG and generation evaluation, not just the familiar RAG overview.
- Hover/focus previews use curated definitions and navigate directly to the referenced lesson heading. Touch users have an explicit preview control; ordinary links stay ordinary.

## Tasks and verification

- [x] Author three lessons and metadata, one grounded interview question and at least two meaningful MCQs per new concept; preserve existing content.
- [x] Implement validated internal concept links with accessible previews, keyboard dismissal and responsive bounds; test malformed/external links and rendering.
- [x] Create six diagrams: document lifecycle, vector geometry, exact/ANN search, hybrid ranking, retrieval metrics, diagnosis.
- [x] Add per-lesson roadmap sources and integrity checks for internal links, diagram assets, mentor coverage and formula examples.
- [x] Run targeted content/SPA tests, full frontend tests and production build. Avoid touching personal/production databases.
- [x] Inspect locally at desktop/mobile sizes and both themes, test preview controls/navigation, diagrams, tests and console errors.
- [x] Independent read-only code review, fix confirmed findings, rerun relevant checks.
- [x] Prepare the reviewed feature-branch handoff for commit and push. Deployment requires approval of the resulting revision and production destination.

## Important edge cases

No relevant documents, fewer than k results, duplicate chunks, zero vectors, incompatible embedding spaces, stale document versions, missing index candidates, permission-filtered retrieval, partial relevance and judge uncertainty are explained in the lessons. Previews must not depend on hover alone or hide the destination link; arbitrary URLs and raw HTML are not accepted as preview targets.

## Verification and review outcome

- Frontend: 111 tests passed; TypeScript/Vite production build passed (existing large-chunk warning).
- Backend: content, reference-answer boundaries, roadmap, SPA and RAG-specific anchors/assets checked together (41 tests).
- Browser: 1440×1000 desktop and 390×844 mobile, light/dark themes; all three mobile documents stay within viewport. Cross-lesson navigation lands on the exact heading. Definition button, keyboard focus and Escape checked; new 14-question test loads and gives immediate explanation. No console errors in inspected flows.
- Independent read-only review found and verified fixes for focus persistence, popup scrolling and RRF illustration consistency. Browser QA additionally found focus-induced scrolling dismissal and a long inline formula overflowing mobile; both were fixed and rechecked. Distractors were revised to test realistic misconceptions.
- No backend runtime, database, migration, authentication, production dependency or infrastructure changes. Existing lesson/concept/question records preserved.
- Production has not been changed; release awaits explicit approval under the repository workflow.
