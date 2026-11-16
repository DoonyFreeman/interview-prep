import { useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  assistantThreadKey, assistantThreadsKey, deleteAssistantThread, renameAssistantThread,
  type AssistantThread, type AssistantThreadSummary,
} from "../api/assistant";
import { getToken } from "../lib/token";
import { Button } from "./Button";
import type { AssistantThreadAction } from "./AssistantHistory";

export function AssistantThreadDialog({ action, onDeleted, onDismiss }: {
  action: AssistantThreadAction;
  onDeleted: (id: string) => void;
  onDismiss: () => void;
}) {
  const { t } = useTranslation();
  const modal = useRef<HTMLDialogElement>(null);
  const [title, setTitle] = useState(action.thread.title);
  const qc = useQueryClient();
  const isRename = action.kind === "rename";
  const id = action.thread.id;

  useLayoutEffect(() => {
    const dialog = modal.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  const mutation = useMutation({
    mutationFn: async (token: string) => {
      if (isRename) return renameAssistantThread(token, id, title.trim());
      await deleteAssistantThread(token, id);
      return null;
    },
    async onSuccess(updated, token) {
      if (getToken() !== token) return;
      await Promise.all([
        qc.cancelQueries({ queryKey: assistantThreadKey(id), exact: true }),
        qc.cancelQueries({ queryKey: assistantThreadsKey, exact: true }),
      ]);
      if (getToken() !== token) return;
      if (updated) {
        qc.setQueryData<AssistantThread>(assistantThreadKey(id), (cached) =>
          cached ? { ...cached, title: updated.title } : updated
        );
        qc.setQueryData<AssistantThreadSummary[]>(assistantThreadsKey, (cached) =>
          cached?.map((thread) => thread.id === id ? { ...thread, title: updated.title } : thread)
        );
        void qc.invalidateQueries({ queryKey: assistantThreadKey(id), exact: true });
      } else {
        qc.removeQueries({ queryKey: assistantThreadKey(id), exact: true });
        qc.setQueryData<AssistantThreadSummary[]>(assistantThreadsKey, (cached) =>
          cached?.filter((thread) => thread.id !== id)
        );
        onDeleted(id);
      }
      void qc.invalidateQueries({ queryKey: assistantThreadsKey, exact: true });
      modal.current?.close();
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = getToken();
    if (token && !mutation.isPending && (!isRename || title.trim())) mutation.mutate(token);
  }

  return (
    <dialog
      ref={modal}
      className="assistant-action-dialog"
      aria-labelledby="assistant-action-title"
      onClose={onDismiss}
      onCancel={(event) => { if (mutation.isPending) event.preventDefault(); }}
    >
      <form onSubmit={submit} className="space-y-4">
        <h2 id="assistant-action-title" className="font-display text-xl font-bold">{t(isRename ? "assistant.rename" : "assistant.delete")}</h2>
        {isRename ? (
          <label className="grid gap-1.5 text-sm font-semibold">
            {t("assistant.chatName")}
            <input
              value={title}
              maxLength={100}
              onChange={(event) => setTitle(event.target.value)}
              onFocus={(event) => event.target.select()}
              readOnly={mutation.isPending}
              autoFocus
              className="assistant-title-input"
            />
          </label>
        ) : (
          <div className="space-y-1 text-sm text-muted">
            <p className="break-words font-semibold text-ink">{title}</p>
            <p>{t("assistant.deleteConfirm")}</p>
          </div>
        )}
        {mutation.isError && <p role="alert" className="text-sm text-danger">{t(isRename ? "assistant.renameError" : "assistant.deleteError")}</p>}
        <div className="flex flex-wrap justify-end gap-2">
          <Button type="button" variant="ghost" autoFocus={!isRename} disabled={mutation.isPending} onClick={() => modal.current?.close()}>
            {t("assistant.cancel")}
          </Button>
          <Button type="submit" className={isRename ? undefined : "!bg-danger !text-white hover:brightness-90"} disabled={mutation.isPending || (isRename && !title.trim())}>
            {t(isRename ? "assistant.saveTitle" : "assistant.delete")}
          </Button>
        </div>
      </form>
    </dialog>
  );
}
