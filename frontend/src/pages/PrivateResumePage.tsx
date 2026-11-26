import { useLayoutEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
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

export function PrivateResumePage() {
  const { token } = useAuth();
  const { data, isPending, isError, refetch } = usePrivateResume(token);
  const [selected, setSelected] = useState<string>();
  useLayoutEffect(() => {
    window.scrollTo(0, 0);
  }, []);
  const section = data?.find(({ id }) => id === selected) ?? data?.[0];

  return (
    <div className="cheatsheets-library resume-sheet">
      <Link className="cheatsheet-action" to="/cheatsheets">← Шпаргалки</Link>
      {isPending && <p role="status">Загружаем шпаргалку…</p>}
      {isError && (
        <p role="alert">Не удалось загрузить шпаргалку.{" "}
          <button className="cheatsheet-action" onClick={() => void refetch()}>Повторить</button>
        </p>
      )}
      {!section && !isPending && !isError && <p>Шпаргалка недоступна для этого аккаунта.</p>}
      {section && (
        <>
          <header className="cheatsheets-library-header">
            <h1 className="font-display text-4xl font-bold text-ink">Моё резюме</h1>
            <p>Разбор опыта для технического собеседования</p>
          </header>
          <nav aria-label="Темы шпаргалки" className="resume-controls">
            {data?.map(({ id, title }) => (
              <button key={id} type="button" aria-pressed={section.id === id}
                className={`cheatsheet-action ${section.id === id ? "cheatsheet-action-primary" : ""}`}
                onClick={() => setSelected(id)}>{title}</button>
            ))}
          </nav>
          <article key={section.id} className="resume-topic">
            <h2 className="font-display text-3xl font-bold">{section.title}</h2>
            <blockquote>{section.quote}</blockquote>
            {section.panels.slice(0, 1).map(({ title, text }) => (
              <section key={title}><h3>{title}</h3><p>{text}</p></section>
            ))}
            <Simulation scenarios={section.scenarios} />
            {section.panels.slice(1).map(({ title, text }) => (
              <section key={title}><h3>{title}</h3><p>{text}</p></section>
            ))}
            <section>
              <h3>Проверь себя перед собеседованием</h3>
              <p>Ответь вслух, затем раскрой пример.</p>
              {section.questions.map(({ question, answer }) => (
                <details key={question} className="resume-details">
                  <summary>{question}</summary>
                  <p>{answer}</p>
                </details>
              ))}
            </section>
            <section>
              <h3>Термины</h3>
              <dl className="resume-terms">{section.terms.map(({ question, answer }) => (
                <div key={question}><dt>{question}</dt><dd>{answer}</dd></div>
              ))}</dl>
            </section>
          </article>
        </>
      )}
    </div>
  );
}
