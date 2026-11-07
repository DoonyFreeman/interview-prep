import { useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

interface TraceStep {
  node: string;
  explanation: string;
  state: Record<string, unknown>;
}
interface Trace {
  title: string;
  nodes: string[];
  steps: TraceStep[];
}

const record = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const shortText = (value: unknown, max: number): value is string =>
  typeof value === "string" && value.trim().length > 0 && value.length <= max;

function readableValue(value: unknown, depth = 0): boolean {
  if (depth > 8) return false;
  if (typeof value === "string") return value.length <= 4000;
  if (value === null || typeof value === "boolean" || typeof value === "number") return true;
  if (Array.isArray(value)) return value.length <= 100 && value.every((item) => readableValue(item, depth + 1));
  return record(value) && Object.keys(value).length <= 30
    && Object.values(value).every((item) => readableValue(item, depth + 1));
}

/** Authored data only: the reader never executes code from a lesson. */
function parseTrace(source: string): Trace | null {
  if (source.length > 100_000) return null;
  try {
    const data: unknown = JSON.parse(source);
    if (!record(data) || !shortText(data.title, 200) || !Array.isArray(data.nodes)
      || data.nodes.length < 1 || data.nodes.length > 12
      || !data.nodes.every((node) => shortText(node, 80))
      || new Set(data.nodes).size !== data.nodes.length
      || !Array.isArray(data.steps) || data.steps.length < 1 || data.steps.length > 40) return null;
    const nodes = data.nodes;
    if (!data.steps.every((step: unknown) => record(step)
      && shortText(step.node, 80) && nodes.includes(step.node)
      && shortText(step.explanation, 1600) && record(step.state)
      && Object.keys(step.state).length <= 20
      && Object.keys(step.state).every((key) => shortText(key, 80))
      && readableValue(step.state))) return null;
    return data as unknown as Trace;
  } catch {
    return null;
  }
}

function display(value: unknown): string {
  if (typeof value === "string") return value === "" ? '""' : value;
  return JSON.stringify(value) ?? "—";
}

export function ExecutionTrace({ source }: { source: string }) {
  const { t } = useTranslation();
  const trace = useMemo(() => parseTrace(source), [source]);
  const [index, setIndex] = useState(0);
  const captionId = useId();
  if (!trace) return <p className="text-muted">{t("lessonBlocks.invalidTrace")}</p>;
  const current = trace.steps[index];
  const previous = trace.steps[index - 1]?.state;
  const fields = [...new Set([...Object.keys(current.state), ...Object.keys(previous ?? {})])];

  return (
    <section className="execution-trace" aria-label={trace.title} aria-describedby={captionId}>
      <p className="execution-trace-title">{trace.title}</p>
      <p id={captionId} className="execution-trace-caption">{t("lessonBlocks.fixedExample")}</p>
      <ul className="execution-trace-nodes" aria-label={t("lessonBlocks.nodes")}>
        {trace.nodes.map((node) => (
          <li key={node} aria-current={node === current.node ? "step" : undefined}>{node}</li>
        ))}
      </ul>
      <div className="execution-trace-navigation">
        <button type="button" disabled={index === 0} onClick={() => setIndex((i) => i - 1)}>
          {t("lessonBlocks.previous")}
        </button>
        <button type="button" disabled={index === trace.steps.length - 1} onClick={() => setIndex((i) => i + 1)}>
          {t("lessonBlocks.next")}
        </button>
        <button type="button" disabled={index === 0} onClick={() => setIndex(0)}>
          {t("lessonBlocks.reset")}
        </button>
      </div>
      <div className="execution-trace-description" aria-live="polite" aria-atomic="true">
        <p className="execution-trace-counter">{t("lessonBlocks.step", { current: index + 1, total: trace.steps.length })} · {current.node}</p>
        <p>{current.explanation}</p>
      </div>
      <div className="table-scroll">
        <table>
          <caption>{t("lessonBlocks.stateCaption")}</caption>
          <thead><tr><th scope="col">{t("lessonBlocks.field")}</th><th scope="col">{t("lessonBlocks.value")}</th></tr></thead>
          <tbody>
            {fields.map((field) => {
              const changed = previous !== undefined && JSON.stringify(previous[field]) !== JSON.stringify(current.state[field]);
              return (
                <tr key={field} data-changed={changed || undefined}>
                  <th scope="row">{field}{changed && <span className="execution-trace-change"> · {t("lessonBlocks.changed")}</span>}</th>
                  <td>{Object.prototype.hasOwnProperty.call(current.state, field) ? display(current.state[field]) : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
