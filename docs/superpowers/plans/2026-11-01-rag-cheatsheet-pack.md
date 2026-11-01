# RAG Cheatsheet Pack Implementation Plan

**Goal:** Add one informative reference per new RAG lesson and download all RAG references with one action.

**Architecture:** Three Markdown readers with checked-in two-page PDFs extend the existing cheatsheet registry. A seven-page static PDF combines the existing RAG overview and three new lesson sheets. Existing server, authentication and progress are unchanged; PDFs are authored offline.

**Tech Stack:** Existing React/TypeScript/i18next/CSS tokens, Markdown, ReportLab/pypdf offline authoring, Vitest and pytest.

## Scope

- Lesson 5: documents/embeddings, including step-by-step dot/cosine/L2, normalization, chunk overlap and version/condition diagnosis.
- Lesson 6: TF-IDF/BM25, sparse/dense, permissions, exact/ANN, HNSW/IVF, worked RRF, reranking and context budget.
- Lesson 7: relevance/evaluation set, worked Precision/Recall/MRR/NDCG, answer evaluation, dev/test, judge limitations and diagnosis.
- Six short sections per sheet, two readable landscape A4 pages each; preserve earlier sheet style and mathematical meaning.
- Bundle order: overview → documents/embeddings → search/indexes → evaluation/diagnosis, with PDF bookmarks.
- Library RAG group, bundle download on RAG readers, compact links at the end of only the three new lessons. Preserve the existing ML lesson 4 attachment.

## Tasks

- [x] Author and check three six-section references against the lessons and the user's recent questions.
- [x] Implement registry, grouping, translated controls, individual downloads and single bundle download without new dependencies.
- [x] Generate four final PDF files with embedded fonts and inspect every rendered page; check extracted math/text, page counts and bundle ordering.
- [x] Update asset and navigation regression checks; run targeted backend checks, frontend tests and production build.
- [x] Inspect library, readers, lesson footer and actual PDF download on desktop/mobile and both themes. Check keyboard, unknown slug, overflow and console errors.
- [x] Obtain independent read-only review, fix confirmed findings and rerun relevant checks.
- [x] Prepare a reviewed feature-branch handoff for commit and push. Production release requires approval of the resulting revision.

## Edge cases

Unknown routes have the existing empty state. Only explicit registry entries are downloadable; the bundle must include the old RAG overview but exclude ML/agents/LLM sheets. Page labels must match real assets. Long headings, tables and formulas must remain readable on screen and PDF, with selectable text and no missing math glyphs. Old PDFs must remain byte-identical. No user data is collected or exported.

## Verification outcome

- 113 frontend tests and 31 targeted backend checks passed; TypeScript/Vite build passed with the existing large-chunk warning.
- All six new PDF pages inspected after rendering. The bundle contains seven pages and four bookmarks; every bundled page matches its standalone source. Full text/math extraction and deterministic rebuild checks passed. Existing six Markdown/PDF pairs remain byte-identical.
- Desktop 1440×1000 and mobile 390×844 inspected in light/dark themes. All three readers and lesson footers fit the viewport. The library exposes one seven-page bundle download; an actual browser download byte-matches the checked-in file. RU/EN labels, unknown reader, keyboard focus and retained ML-only attachment checked; console has no errors in tested flows.
- Independent read-only code/content/PDF review found no confirmed issues. No production dependency, runtime backend, database, authentication or infrastructure changes.
- Production release remains pending approval of the reviewed feature revision.
