import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";
import { getToken } from "../lib/token";

const path = "/cheatsheets/my-openspec";
const files = {
  original: ["/pdf", "openspec-agent-engineering.pdf", "cheatsheets.downloadOpenspec"],
  bundle: ["/bundle.pdf", "my-cheatsheets-all.pdf", "cheatsheets.downloadMyBundle"],
} as const;
type Kind = keyof typeof files;
type Availability = Record<Kind, boolean>;

export function PrivateOpenspecDownloads({ token }: { token: string | null }) {
  return token ? <SessionDownloads key={token} token={token} /> : null;
}

function SessionDownloads({ token }: { token: string }) {
  const { t } = useTranslation();
  const headers = { Authorization: `Bearer ${token}` };
  const availability = useQuery({
    queryKey: ["private-openspec", token],
    queryFn: async ({ signal }) => (await api.get<Availability>(path, { headers, signal })).data,
    gcTime: 0,
    retry: false,
  });
  const request = useRef<AbortController | null>(null);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => () => request.current?.abort(), []);

  async function download(kind: Kind) {
    if (request.current || getToken() !== token) return;
    const controller = new AbortController();
    request.current = controller;
    setPending(true);
    setFailed(false);
    const [suffix, filename] = files[kind];
    try {
      const { data } = await api.get<Blob>(path + suffix, {
        headers, responseType: "blob", signal: controller.signal,
      });
      if (controller.signal.aborted || getToken() !== token) return;
      if (data.type !== "application/pdf") throw new Error("Expected PDF");
      const url = URL.createObjectURL(data);
      try {
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        try { link.click(); } finally { link.remove(); }
      } finally {
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
    } catch {
      if (!controller.signal.aborted && getToken() === token) {
        setFailed(true);
        void availability.refetch();
      }
    } finally {
      request.current = null;
      if (!controller.signal.aborted) setPending(false);
    }
  }

  const enabled = (Object.keys(files) as Kind[]).filter((kind) => (
    !availability.isError && availability.data?.[kind] === true
  ));
  if (!enabled.length && !failed) return null;
  return (
    <div className="mt-3">
      <div className="cheatsheet-card-actions">
        {enabled.map((kind) => (
          <button key={kind} type="button" className="cheatsheet-action cheatsheet-action-secondary"
            disabled={pending} onClick={() => void download(kind)}>
            {t(files[kind][2])}
          </button>
        ))}
      </div>
      {failed && <p role="alert" className="text-sm text-muted">{t("cheatsheets.privateDownloadError")}</p>}
    </div>
  );
}
