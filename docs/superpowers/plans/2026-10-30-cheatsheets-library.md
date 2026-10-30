# Cheatsheet Library Implementation Plan

> **For agentic workers:** Execute in this chat with independent ownership: six Markdown documents; catalog/reader/registry; six printable PDFs. The lead owns navigation, routes, lesson CTA, translations and integration. Do not revert other work or edit files outside the assignment.

**Goal:** Replace the Progress destination with a six-item cheatsheet library, responsive readers and PDF downloads. Attach only the ML metrics sheet to the end of the fourth LLM lesson.

**Architecture:** Static Markdown in `frontend/src/content/cheatsheets/`, typed registry in `frontend/src/lib/cheatsheets.ts`, two React pages, PDFs in `frontend/public/cheatsheets/`. No database/schema/API or production-dependency changes. Existing progress tracking/dashboard remains. Old `/progress` redirects to `/cheatsheets`, with persisted mobile-tab migration.

**Tech Stack:** React/TypeScript/Vite, existing Markdown and design tokens, vitest, reportlab/pypdf for offline PDF production.

## Contracts

Six slugs/files: `concurrency`, `team-processes`, `llm-basics`, `rag`, `agents`, `ml-metrics`. Each `.md` has titled `##` sections and no H1. Each PDF `/cheatsheets/<slug>.pdf` has one landscape A4 page. Groups are `python`, `team`, `ai`.

Registry exports `CHEATSHEETS`, `CHEATSHEET_GROUPS`, `getCheatsheet(slug)`, `getLessonCheatsheet(courseSlug, lessonSlug)` and `getCheatsheetSections(markdown)`. Sections have `title`, `anchor`, `markdown`. Sheets have `slug`, `title`, `description`, `category`, `pdfUrl`, `pages: 1`, `markdown`. Lesson lookup returns only `ml-metrics` for `llm/ml-curves-regression`, undefined otherwise.

## Tasks

- [x] Baseline frontend tests. Add a failing regression test that saved `progress` tabs migrate to `cheatsheets` without changing other user choices; implement migration/defaults.
- [x] Author six Markdown sheets faithful to the sources. ML covers all eleven mentor groups in nine compact blocks with existing lesson examples.
- [x] Implement registry, section parser, catalog and responsive reader with semantic headings, PDF download and unknown-slug state. Write tests before new behavior.
- [x] Produce five standalone PDFs from supplied files, fix standalone pagination/cross-references and metadata; create one-page ML PDF in the PT Serif/Sans/Mono style. Reopen, extract, render and visually inspect all six. Lead has successfully run the PDF authoring marker once for six outputs.
- [x] Replace desktop/mobile/settings Progress navigation, icon and labels; redirect old route and remove dashboard link to the old page. Keep progress APIs/data.
- [x] Add catalog/detail routes and compact open/download CTA after resources in lesson4, using exact course/lesson lookup. No CTA in lesson3 or other lessons.
- [x] Add RU/EN UI labels. Preserve design tokens/themes/fonts/motion; six sheets need grouping without complex filtering.
- [x] Run frontend tests/build, PDF/asset checks and relevant backend SPA/content tests. Inspect desktop/phone, both themes, keyboard, downloads, unknown slug, old redirect, lesson4-only CTA and console/network with synthetic preview data.
- [x] Independent implementation review, including registry, routing, PDF structure/generator and final asset tests. No findings. Lead completed content/visual checks and fixed route scroll position found during browser QA.


## Verification results

- Frontend: 94 tests pass; TypeScript and Vite production build pass. Existing large-chunk warning remains; no dependency changes.
- Backend: 29 targeted content/static-serving tests pass, including real PDF bytes and content type through the production SPA fallback. No DB/API/schema changes.
- All six PDFs reopen as one landscape A4 page, selectable text without replacement characters; source annotations removed. All final page renders inspected.
- Desktop 1440×1000 and phone 390×844: catalog/reader, light/dark, no document overflow on all six readers; unknown slug, RU/EN labels, keyboard focus and download checked. Browser console has no errors.
- ML downloaded through the UI matches the repository PDF byte for byte. Every local PDF URL returns 200 application/pdf. The Vite build contains all six unchanged PDF assets.
- /progress redirects to /cheatsheets. Lesson 3 has no attachment; lesson 4's final article block opens ML at the top and downloads its PDF.
- Code review: independent code_reviewer reported no confirmed findings, then rechecked the scroll fix and final tests/docs.

## Handoff

Commit and push only the feature branch as the final local step. Merge to master and deployment to https://iprep.duckdns.org require explicit approval of the reviewed revision; no new deployment is authorized by this implementation request.
