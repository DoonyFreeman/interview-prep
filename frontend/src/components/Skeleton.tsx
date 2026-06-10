/**
 * Skeleton placeholders — used while a page's primary data loads, so the layout
 * lands in roughly its final shape instead of a centred spinner that then jumps.
 */

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`animate-pulse rounded-md bg-surface-2 ${className}`} />
  );
}

/** A card-shaped placeholder matching the app's rounded-2xl surfaces. */
export function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div
      className={`rounded-2xl border border-border bg-surface p-5 shadow-card ${className}`}
    >
      <Skeleton className="h-5 w-1/2" />
      <Skeleton className="mt-3 h-3 w-full" />
      <Skeleton className="mt-2 h-3 w-4/5" />
      <Skeleton className="mt-4 h-2 w-full" />
    </div>
  );
}

/** A grid of card skeletons (catalogue / lists). */
export function SkeletonGrid({
  count = 6,
  cols = 2,
}: {
  count?: number;
  cols?: 1 | 2;
}) {
  return (
    <div className={`grid gap-4 ${cols === 2 ? "sm:grid-cols-2" : ""}`}>
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}
