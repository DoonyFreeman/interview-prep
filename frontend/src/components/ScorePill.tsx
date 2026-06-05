export function ScorePill({ score }: { score: number }) {
  const cls =
    score >= 80
      ? "bg-success-soft text-success"
      : score >= 40
        ? "bg-warn-soft text-warn"
        : "bg-danger-soft text-danger";
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${cls}`}>
      {score}
    </span>
  );
}
