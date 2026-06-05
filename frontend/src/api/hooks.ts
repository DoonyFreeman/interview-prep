import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "../lib/api";
import type {
  CourseDetail,
  CourseSummary,
  EvaluationOut,
  GlossaryList,
  GlossaryProgress,
  HintOut,
  LessonDetail,
  LessonQuestions,
  ProgressOverviewOut,
  QuestionOut,
  QuizResultItem,
  ReviewQueue,
  TokenOut,
  UserOut,
} from "./types";

// --- Content (public reads) ------------------------------------------------
export function useCourses() {
  return useQuery({
    queryKey: ["courses"],
    queryFn: async () => (await api.get<CourseSummary[]>("/courses")).data,
  });
}

export function useCourse(slug: string) {
  return useQuery({
    queryKey: ["course", slug],
    queryFn: async () =>
      (await api.get<CourseDetail>(`/courses/${slug}`)).data,
  });
}

export function useLesson(courseSlug: string, lessonSlug: string) {
  return useQuery({
    queryKey: ["lesson", courseSlug, lessonSlug],
    queryFn: async () =>
      (
        await api.get<LessonDetail>(
          `/courses/${courseSlug}/lessons/${lessonSlug}`,
        )
      ).data,
  });
}

// --- Progress --------------------------------------------------------------
export function useProgress() {
  return useQuery({
    queryKey: ["progress"],
    queryFn: async () =>
      (await api.get<ProgressOverviewOut>("/progress")).data,
  });
}

export function useReview() {
  return useQuery({
    queryKey: ["review"],
    queryFn: async () =>
      (await api.get<ReviewQueue>("/progress/review")).data,
  });
}

// --- Glossary (public reads) -----------------------------------------------
export function useGlossary(category: string | null, q: string) {
  return useQuery({
    queryKey: ["glossary", category, q],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (category) params.category = category;
      if (q.trim()) params.q = q.trim();
      return (await api.get<GlossaryList>("/glossary", { params })).data;
    },
  });
}

// --- Glossary quiz progress (auth) -----------------------------------------
export function useGlossaryProgress() {
  return useQuery({
    queryKey: ["glossary-progress"],
    queryFn: async () =>
      (await api.get<GlossaryProgress>("/glossary/progress")).data,
  });
}

export function useRecordQuizResult() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (items: QuizResultItem[]) =>
      (await api.post<GlossaryProgress>("/glossary/quiz/result", { items })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["glossary-progress"] });
    },
  });
}

export function useMarkLesson() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: {
      courseSlug: string;
      lessonSlug: string;
      completed: boolean;
    }) => {
      await api.post(
        `/progress/courses/${vars.courseSlug}/lessons/${vars.lessonSlug}`,
        { completed: vars.completed },
      );
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["progress"] }),
  });
}

// --- Quiz ------------------------------------------------------------------
export function useNextQuestion(
  courseSlug: string,
  lessonSlug: string,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: ["next-question", courseSlug, lessonSlug],
    enabled: options.enabled ?? true,
    queryFn: async () =>
      (
        await api.get<QuestionOut>(
          `/quiz/courses/${courseSlug}/lessons/${lessonSlug}/next`,
        )
      ).data,
    staleTime: 0,
    gcTime: 0,
    refetchOnMount: "always",
  });
}

export function useQuestion(questionId: number | null) {
  return useQuery({
    queryKey: ["question", questionId],
    enabled: questionId != null,
    queryFn: async () =>
      (await api.get<QuestionOut>(`/quiz/questions/${questionId}`)).data,
  });
}

export function useLessonQuestions(courseSlug: string, lessonSlug: string) {
  return useQuery({
    queryKey: ["lesson-questions", courseSlug, lessonSlug],
    queryFn: async () =>
      (
        await api.get<LessonQuestions>(
          `/quiz/courses/${courseSlug}/lessons/${lessonSlug}/questions`,
        )
      ).data,
  });
}

export function useEvaluate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: {
      questionId: number;
      answerText: string;
      hintUsed: boolean;
    }) =>
      (
        await api.post<EvaluationOut>(
          `/quiz/questions/${vars.questionId}/evaluate`,
          { answer_text: vars.answerText, hint_used: vars.hintUsed },
        )
      ).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["progress"] });
      qc.invalidateQueries({ queryKey: ["lesson-questions"] });
      qc.invalidateQueries({ queryKey: ["review"] });
    },
  });
}

export function useHint() {
  return useMutation({
    mutationFn: async (vars: { questionId: number; answerText: string }) =>
      (
        await api.post<HintOut>(`/quiz/questions/${vars.questionId}/hint`, {
          answer_text: vars.answerText,
        })
      ).data,
  });
}

// --- Auth ------------------------------------------------------------------
export function useLogin() {
  return useMutation({
    mutationFn: async (vars: { email: string; password: string }) =>
      (await api.post<TokenOut>("/auth/login", vars)).data,
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: async (vars: {
      email: string;
      password: string;
      display_name: string;
    }) => (await api.post<TokenOut>("/auth/register", vars)).data,
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { display_name: string }) =>
      (await api.patch<UserOut>("/auth/me", vars)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: async (vars: {
      current_password: string;
      new_password: string;
    }) => {
      await api.post("/auth/password", vars);
    },
  });
}
