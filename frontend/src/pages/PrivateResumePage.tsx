import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api } from "../lib/api";
import { usePrivateResume, type ResumeSection } from "../lib/privateResume";
import "../components/cheatsheets.css";
import "../components/private-resume.css";

function Simulation({ scenarios }: Pick<ResumeSection, "scenarios">) {
  const [scenarioIndex, setScenarioIndex] = useState(0);
  const [stepIndex, setStepIndex] = useState(0);
  const scenario = scenarios[scenarioIndex];
  const step = scenario?.steps[stepIndex];
  if (!scenario || !step) return null;

  const nodes = [...new Set(scenario.steps.flatMap(({ from_node, to_node }) => [from_node, to_node]))];

  return (
    <section className="resume-simulation" aria-label="Симуляция">
      <div className="resume-simulation-header">
        <h3>Путь запроса</h3>
        <label>
          Сценарий
          <select value={scenarioIndex} onChange={(event) => {
            setScenarioIndex(Number(event.target.value));
            setStepIndex(0);
          }}>
            {scenarios.map(({ title }, index) => <option key={title} value={index}>{title}</option>)}
          </select>
        </label>
      </div>
      <ul className="resume-nodes" aria-label="Компоненты">
        {nodes.map((node) => (
          <li key={node} data-active={node === step.from_node || node === step.to_node}>{node}</li>
        ))}
      </ul>
      <div className="resume-step" aria-live="polite" aria-atomic="true">
        <p className="resume-direction">
          {step.from_node} <span aria-label="передаёт в">→</span> {step.to_node}
        </p>
        <h4>{step.title}</h4>
        <pre><code>{step.payload}</code></pre>
        <p><strong>Состояние:</strong> {step.state}</p>
        <p>{step.why}</p>
      </div>
      <div className="resume-controls">
        <button type="button" className="cheatsheet-action" disabled={stepIndex === 0}
          onClick={() => setStepIndex(stepIndex - 1)}>← Назад</button>
        <button type="button" className="cheatsheet-action cheatsheet-action-primary"
          disabled={stepIndex === scenario.steps.length - 1}
          onClick={() => setStepIndex(stepIndex + 1)}>Следующий шаг →</button>
        <button type="button" className="cheatsheet-action" disabled={stepIndex === 0}
          onClick={() => setStepIndex(0)}>Сбросить</button>
        <span>Шаг {stepIndex + 1} из {scenario.steps.length}</span>
      </div>
      <details className="resume-details">
        <summary>Журнал событий</summary>
        <ol>{scenario.steps.slice(0, stepIndex + 1).map((entry, index) => (
          <li key={index}>{entry.title}. {entry.state}</li>
        ))}</ol>
      </details>
    </section>
  );
}

function Architecture({ section }: { section: ResumeSection }) {
  // Older documents still expose their real edges through the scenario steps.
  const flows = section.flows?.length ? section.flows : section.scenarios.flatMap((scenario) =>
    scenario.steps.map((step) => ({
      title: `${scenario.title} · ${step.title}`,
      nodes: [{ title: step.from_node, detail: step.why }, { title: step.to_node, detail: step.state }],
      links: [step.title],
    })),
  );
  if (!flows.length) return null;

  return (
    <section className="resume-architecture" aria-labelledby={`architecture-${section.id}`}>
      <div className="resume-section-heading">
        <span className="resume-eyebrow">Система в действии</span>
        <h3 id={`architecture-${section.id}`}>Архитектура и потоки</h3>
      </div>
      {flows.map((flow, index) => (
        <figure className="resume-flow" key={`${flow.title}-${index}`}>
          <figcaption>{flow.title}</figcaption>
          <ol className="resume-flow-track">
            {flow.nodes.map((node, nodeIndex) => (
              <li className="resume-flow-part" key={`${node.title}-${nodeIndex}`}>
                {nodeIndex > 0 && (
                  <div className="resume-flow-edge">
                    <span>{flow.links[nodeIndex - 1]}</span>
                    <span className="resume-flow-arrow" aria-label="затем">→</span>
                  </div>
                )}
                <div className="resume-flow-node">
                  <span className="resume-flow-number" aria-hidden="true">{String(nodeIndex + 1).padStart(2, "0")}</span>
                  <strong>{node.title}</strong>
                  <p>{node.detail}</p>
                </div>
              </li>
            ))}
          </ol>
        </figure>
      ))}
    </section>
  );
}

export function PrivateResumePage() {
  const { token } = useAuth();
  const { data, isPending, isError, refetch } = usePrivateResume(token);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");
  const downloadRequest = useRef<AbortController | null>(null);
  const downloadUrl = useRef<string | null>(null);
  useLayoutEffect(() => {
    window.scrollTo(0, 0);
  }, []);
  useEffect(() => {
    setDownloading(false);
    setDownloadError("");
    return () => {
      downloadRequest.current?.abort();
      downloadRequest.current = null;
      if (downloadUrl.current) URL.revokeObjectURL(downloadUrl.current);
      downloadUrl.current = null;
    };
  }, [token]);

  async function downloadPdf() {
    if (!token || downloadRequest.current) return;
    const controller = new AbortController();
    downloadRequest.current = controller;
    setDownloading(true);
    setDownloadError("");
    try {
      const response = await api.get<Blob>("/cheatsheets/my-resume/pdf", {
        responseType: "blob",
        signal: controller.signal,
        headers: { Authorization: `Bearer ${token}` },
      });
      if (controller.signal.aborted) return;
      const url = URL.createObjectURL(response.data);
      downloadUrl.current = url;
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "my-resume-cheatsheet.pdf";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => {
        URL.revokeObjectURL(url);
        if (downloadUrl.current === url) downloadUrl.current = null;
      }, 1000);
    } catch {
      if (!controller.signal.aborted) setDownloadError("Не удалось скачать PDF. Попробуйте ещё раз.");
    } finally {
      if (downloadRequest.current === controller) downloadRequest.current = null;
      if (!controller.signal.aborted) setDownloading(false);
    }
  }

  return (
    <div className="cheatsheets-library resume-sheet">
      <div className="resume-toolbar">
        <Link className="cheatsheet-action cheatsheet-back-link" to="/cheatsheets">← Все шпаргалки</Link>
        <span className="resume-access-label">Личный материал</span>
      </div>
      {isPending && <p className="resume-status" role="status">Загружаем шпаргалку…</p>}
      {isError && (
        <div className="resume-status" role="alert">Не удалось загрузить шпаргалку.{" "}
          <button type="button" className="cheatsheet-action" onClick={() => void refetch()}>Повторить</button>
        </div>
      )}
      {!data?.length && !isPending && !isError && <p className="resume-status">Шпаргалка недоступна для этого аккаунта.</p>}
      {!!data?.length && (
        <>
          <header className="resume-cover">
            <div>
              <p className="resume-eyebrow">Подготовка к техническому собеседованию</p>
              <h1>Моё резюме</h1>
            </div>
            <div className="resume-cover-actions">
              <button type="button" className="cheatsheet-action cheatsheet-action-primary"
                disabled={downloading || !token} onClick={() => void downloadPdf()}>
                {downloading ? "Готовим PDF…" : "Скачать PDF ↓"}
              </button>
              {downloadError && <p className="resume-download-error" role="alert">{downloadError}</p>}
            </div>
          </header>
          <div className="resume-document-layout">
            <nav aria-label="Оглавление шпаргалки" className="resume-toc" id="resume-contents">
              <p className="resume-eyebrow">Содержание</p>
              <ol>{data.map(({ id, title }, index) => (
                <li key={id}><a href={`#resume-${id}`}><span>{String(index + 1).padStart(2, "0")}</span>{title}</a></li>
              ))}</ol>
            </nav>
            <div className="resume-document">
              {data.map((section, index) => (
                <article key={section.id} id={`resume-${section.id}`} className="resume-topic" aria-labelledby={`title-${section.id}`}>
                  <header className="resume-topic-header">
                    <span className="resume-topic-number" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                    <div><p className="resume-eyebrow">Тема из резюме</p><h2 id={`title-${section.id}`}>{section.title}</h2></div>
                  </header>
                  <blockquote><span className="resume-eyebrow">Как это звучит в резюме</span><p>{section.quote}</p></blockquote>
                  {section.takeaway && <div className="resume-takeaway"><span className="resume-eyebrow">Главная мысль</span><p>{section.takeaway}</p></div>}
                  <Architecture section={section} />
                  <div className="resume-panels">
                    {section.panels.map(({ title, text }, panelIndex) => (
                      <section key={title} className="resume-panel"><span className="resume-panel-number" aria-hidden="true">{String(panelIndex + 1).padStart(2, "0")}</span><div><h3>{title}</h3><p>{text}</p></div></section>
                    ))}
                  </div>
                  {!!section.questions.length && <section className="resume-questions">
                    <div className="resume-section-heading"><span className="resume-eyebrow">Подготовь ответ</span><h3>Что могут спросить</h3></div>
                    <dl>{section.questions.map(({ question, answer }) => (
                      <div key={question}><dt>{question}</dt><dd>{answer}</dd></div>
                    ))}</dl>
                  </section>}
                  {!!section.terms.length && <section className="resume-glossary">
                    <h3>Термины, которые нужно объяснить</h3>
                    <dl className="resume-terms">{section.terms.map(({ question, answer }) => (
                      <div key={question}><dt>{question}</dt><dd>{answer}</dd></div>
                    ))}</dl>
                  </section>}
                  {!!section.scenarios.length && <details className="resume-practice">
                    <summary><span>Практика · пошаговый тренажёр</span><span className="resume-practice-hint">Разобрать сценарий</span></summary>
                    <Simulation scenarios={section.scenarios} />
                  </details>}
                  <a className="resume-back-top" href="#resume-contents">К содержанию ↑</a>
                </article>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
