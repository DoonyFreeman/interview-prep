# ML cheatsheet clarity

Goal: clarify the actual misunderstandings observed in tutoring, in the existing website reader and its three-page PDF.

Scope: the nine existing Markdown sections and generated ML PDF. Preserve anchors, diagrams, lesson links and page count. No application behavior, user state, or deployment changes.

- [x] Clarify fact/pred axes, count checks and the distinct Precision column / Recall row using one consistent urgent-ticket example.
- [x] Separate fixed scores, threshold decisions, ROC-AUC/AP ranking, and the simple AP formula from the general tied-score formula.
- [x] Make classification vs regression and macro/weighted/micro choice explicit; interpret R² and retain numeric regression examples.
- [x] Rebuild PDF; inspect all three rendered pages for overflow, glyphs and readable layout; inspect website on desktop and mobile.
- [x] Run existing asset/curve/frontend checks, obtain independent read-only review, resolve confirmed findings, commit and push feature branch only.

Release: present local preview, PDF and reviewed revision. Production merge/deploy requires user approval under AGENTS.md. Practice branch is unrelated and excluded.

Verification: 4 diagram tests, 7 frontend cheatsheet tests, 2 backend PDF-asset tests passed. Frontend production build passed (existing large-chunk warning). All three PDF pages rendered and inspected. Website inspected at 1440×1000 and 390×844, light/dark; no page overflow or console errors. Existing React Router v7 future warnings only. Independent code_reviewer found no issues. Synthetic local account on disposable /tmp database; no production data used.
