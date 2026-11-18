import { useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import {
  filterQuestions,
  interviewPriorities,
  interviewQuestions,
  interviewSources,
  interviewTopics,
  sourceCoverage,
  sourceKinds,
  sourceTotals,
} from "../lib/pythonAiInterview";
import "../components/cheatsheets.css";
import "../components/python-ai-interview.css";

function SourceCoverage() {
  const { t } = useTranslation();
  const rows = [...sourceCoverage].sort((a, b) => b.interview - a.interview || b.role - a.role);

  return (
    <details className="interview-evidence">
      <summary>{t("pythonAiInterview.evidenceTitle")}</summary>
      <div className="interview-evidence-body">
        <p>{t("pythonAiInterview.method")}</p>
        <table className="interview-coverage">
          <caption className="sr-only">{t("pythonAiInterview.evidenceTitle")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("pythonAiInterview.topic")}</th>
              {sourceKinds.map((kind) => <th key={kind} scope="col">{t(`pythonAiInterview.sources.${kind}`)}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map(({ topic, ...counts }) => (
              <tr key={topic}>
                <th scope="row">{t(`pythonAiInterview.topics.${topic}`)}</th>
                {sourceKinds.map((kind) => (
                  <td key={kind}>
                    <div className="interview-coverage-value">
                      <span>{counts[kind]}/{sourceTotals[kind]}</span>
                      <meter value={counts[kind]} max={sourceTotals[kind]} aria-hidden="true" />
                    </div>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        <ul className="interview-sources">
          {interviewSources.map((source) => (
            <li key={source.url}>
              <span>{t(`pythonAiInterview.sources.${source.type}`)}</span>
              <a href={source.url} target="_blank" rel="noreferrer">{source.title}</a>
            </li>
          ))}
        </ul>
      </div>
    </details>
  );
}

export function PythonAiInterviewPage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const resultsRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const topic = interviewTopics.find((value) => value === params.get("topic")) ?? null;
  const matches = filterQuestions(topic, query);

  useLayoutEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  function showResultsStart() {
    const results = resultsRef.current;
    if (results && results.getBoundingClientRect().top < 80) {
      results.scrollIntoView({ block: "start" });
    }
  }

  return (
    <div className="cheatsheet-reader interview-reader">
      <Link to="/cheatsheets" className="cheatsheet-back-link">
        <span aria-hidden="true">←</span> {t("cheatsheets.backToLibrary")}
      </Link>

      <header className="interview-header">
        <p className="interview-level">Middle / Middle+ <span aria-hidden="true">·</span> {t("pythonAiInterview.market")}</p>
        <h1 className="font-display">{t("pythonAiInterview.title")}</h1>
        <p className="interview-description">{t("pythonAiInterview.description")}</p>
        <div className="interview-priority-guide">
          {interviewPriorities.map((priority) => (
            <div key={priority}>
              <strong>{t(`pythonAiInterview.priorities.${priority}.title`)}</strong>
              <p>{t(`pythonAiInterview.priorities.${priority}.description`)}</p>
            </div>
          ))}
        </div>
      </header>

      <SourceCoverage />

      <div className="interview-layout">
        <aside className="interview-filters" aria-label={t("pythonAiInterview.filters")}>
          <label htmlFor="interview-search">{t("pythonAiInterview.search")}</label>
          <input
            id="interview-search"
            ref={searchRef}
            type="search"
            value={query}
            onChange={(event) => {
              showResultsStart();
              setQuery(event.target.value);
            }}
            placeholder={t("pythonAiInterview.searchPlaceholder")}
          />
          <div className="interview-topics" role="group" aria-label={t("pythonAiInterview.topic")}>
            {[null, ...interviewTopics].map((value) => (
              <button
                key={value ?? "all"}
                type="button"
                aria-pressed={topic === value}
                onClick={() => {
                  if (topic === value) return;
                  showResultsStart();
                  const next = new URLSearchParams(params);
                  if (value) next.set("topic", value);
                  else next.delete("topic");
                  setParams(next, { preventScrollReset: true });
                }}
              >
                {value ? t(`pythonAiInterview.topics.${value}`) : t("pythonAiInterview.allTopics")}
              </button>
            ))}
          </div>
        </aside>

        <div className="interview-results" ref={resultsRef}>
          <p className="interview-count" role="status">
            {t("pythonAiInterview.results", { count: matches.length, total: interviewQuestions.length })}
          </p>
          {matches.length === 0 && (
            <div className="interview-empty">
              <p>{t("pythonAiInterview.empty")}</p>
              <button type="button" className="cheatsheet-action cheatsheet-action-secondary" onClick={() => {
                setQuery("");
                const next = new URLSearchParams(params);
                next.delete("topic");
                setParams(next, { preventScrollReset: true });
                searchRef.current?.focus();
              }}>
                {t("pythonAiInterview.reset")}
              </button>
            </div>
          )}
          {interviewPriorities.map((priority) => {
            const questions = matches.filter((question) => question.priority === priority);
            if (questions.length === 0) return null;
            return (
              <section key={priority} className="interview-group" aria-labelledby={`interview-${priority}`}>
                <h2 className="font-display" id={`interview-${priority}`}>
                  {t(`pythonAiInterview.priorities.${priority}.title`)}
                </h2>
                {questions.map(({ rank, topic: questionTopic, question, answer, followUp }) => (
                  <article key={rank} className="interview-question">
                    <div className="interview-question-meta">
                      <span className="interview-rank">#{String(rank).padStart(2, "0")}</span>
                      <span>{t(`pythonAiInterview.topics.${questionTopic}`)}</span>
                    </div>
                    <h3 lang="ru">{question}</h3>
                    <p lang="ru">{answer}</p>
                    <p className="interview-followup">
                      <strong>{t("pythonAiInterview.followUp")}</strong>{" "}
                      <span lang="ru">{followUp}</span>
                    </p>
                  </article>
                ))}
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}
