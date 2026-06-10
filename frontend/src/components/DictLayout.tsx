import { useEffect } from "react";
import { Outlet } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { DictTabs } from "./DictTabs";
import type { GlossaryList } from "../api/types";

/**
 * Persistent shell for the Glossary ↔ Slang pages. Keeping `DictTabs` mounted
 * here (instead of inside each page) means the active-tab pill glides between
 * tabs and the tabs never blink while the page below them loads. Both
 * dictionaries are prefetched on mount so switching tabs is instant.
 *
 * The parent route transition (in `Layout`) treats `/glossary` and `/slang` as
 * one section, so navigating between them doesn't unmount this shell.
 */
export function DictLayout() {
  const qc = useQueryClient();

  useEffect(() => {
    for (const kind of ["reference", "slang"] as const) {
      qc.prefetchQuery({
        queryKey: ["glossary", kind, null, ""],
        queryFn: async () =>
          (await api.get<GlossaryList>("/glossary", { params: { kind } })).data,
        staleTime: Infinity,
      });
    }
  }, [qc]);

  return (
    <div className="mx-auto max-w-4xl">
      <DictTabs />
      <div className="mt-4">
        <Outlet />
      </div>
    </div>
  );
}
