import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

type Answer = { question: string; answer: string };

export type ResumeStep = {
  from_node: string;
  to_node: string;
  title: string;
  payload: string;
  state: string;
  why: string;
};

export type ResumeSection = {
  id: string;
  title: string;
  quote: string;
  takeaway?: string | null;
  flows?: {
    title: string;
    nodes: { title: string; detail: string }[];
    links: string[];
  }[] | null;
  panels: { title: string; text: string }[];
  scenarios: { title: string; steps: ResumeStep[] }[];
  questions: Answer[];
  terms: Answer[];
};

export const privateResumePath = "/cheatsheets/my-resume";

export function usePrivateResume(token: string | null) {
  return useQuery({
    queryKey: ["private-resume", token],
    enabled: Boolean(token),
    gcTime: 0,
    retry: false,
    queryFn: async ({ signal }) =>
      (await api.get<ResumeSection[]>(privateResumePath, {
        signal,
        headers: { Authorization: `Bearer ${token}` },
      })).data,
  });
}
