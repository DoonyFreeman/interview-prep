import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "../lib/api";
import type {
  CatThoughtApi,
  CourseDetail,
  CourseSummary,
  EvaluationOut,
  GlossaryList,
  GlossaryProgress,
  HintOut,
  LessonDetail,
  LessonQuestions,
  LessonTest,
  LessonTestProgress,
  PetState,
  ProgressOverviewOut,
  QuestionAttempts,
  QuestionOut,
  QuestionsProgress,
  QuizResultItem,
  ReviewQueue,
  SearchOut,
  TestResultItem,
  TestsOverview,
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

export function useQuestionsProgress() {
  return useQuery({
    queryKey: ["questions-progress"],
    queryFn: async () =>
      (await api.get<QuestionsProgress>("/progress/questions")).data,
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
export function useGlossary(
  category: string | null,
  q: string,
  kind: "reference" | "slang" = "reference",
) {
  return useQuery({
    queryKey: ["glossary", kind, category, q],
    queryFn: async () => {
      const params: Record<string, string> = { kind };
      if (category) params.category = category;
      if (q.trim()) params.q = q.trim();
      return (await api.get<GlossaryList>("/glossary", { params })).data;
    },
    // Glossary/slang content is static for the session — keep it fresh forever
    // so switching the Glossary↔Slang tab is instant (no refetch spinner).
    staleTime: Infinity,
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
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["progress"] });
      // Completing/uncompleting a lesson changes the corner cat's thought pool.
      qc.invalidateQueries({ queryKey: ["cat-thoughts"] });
    },
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

export function useQuestionAttempts(
  questionId: number | null,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: ["question-attempts", questionId],
    enabled: (options.enabled ?? true) && questionId != null,
    queryFn: async () =>
      (
        await api.get<QuestionAttempts>(
          `/quiz/questions/${questionId}/attempts`,
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
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["progress"] });
      qc.invalidateQueries({ queryKey: ["questions-progress"] });
      qc.invalidateQueries({ queryKey: ["lesson-questions"] });
      qc.invalidateQueries({ queryKey: ["review"] });
      qc.invalidateQueries({
        queryKey: ["question-attempts", vars.questionId],
      });
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

// --- Lesson MCQ self-test --------------------------------------------------
export function useLessonTest(
  courseSlug: string,
  lessonSlug: string,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: ["lesson-test", courseSlug, lessonSlug],
    enabled: options.enabled ?? true,
    queryFn: async () =>
      (
        await api.get<LessonTest>(
          `/quiz/courses/${courseSlug}/lessons/${lessonSlug}/test`,
        )
      ).data,
  });
}

export function useLessonTestProgress(
  courseSlug: string,
  lessonSlug: string,
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    queryKey: ["lesson-test-progress", courseSlug, lessonSlug],
    enabled: options.enabled ?? true,
    queryFn: async () =>
      (
        await api.get<LessonTestProgress>(
          `/quiz/courses/${courseSlug}/lessons/${lessonSlug}/test/progress`,
        )
      ).data,
  });
}

export function useTestsOverview() {
  return useQuery({
    queryKey: ["tests-overview"],
    queryFn: async () =>
      (await api.get<TestsOverview>("/quiz/tests/overview")).data,
  });
}

export function useRecordLessonTest(courseSlug: string, lessonSlug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (items: TestResultItem[]) =>
      (
        await api.post<LessonTestProgress>(
          `/quiz/courses/${courseSlug}/lessons/${lessonSlug}/test/result`,
          { items },
        )
      ).data,
    onSuccess: () => {
      qc.invalidateQueries({
        queryKey: ["lesson-test-progress", courseSlug, lessonSlug],
      });
      qc.invalidateQueries({ queryKey: ["tests-overview"] });
    },
  });
}

// --- Pet (corner cat) state ------------------------------------------------
export function usePet() {
  return useQuery({
    queryKey: ["pet"],
    queryFn: async () => (await api.get<PetState>("/pet")).data,
    staleTime: 60_000,
  });
}

/** Topics the corner cat can mention — one per concept of every completed
 *  lesson. Lesson content rarely changes, so cache generously. */
export function useCatThoughts() {
  return useQuery({
    queryKey: ["cat-thoughts"],
    queryFn: async () =>
      (await api.get<CatThoughtApi[]>("/cat/thoughts")).data,
    staleTime: 5 * 60_000,
    retry: false,
  });
}

export function useUpdatePet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (patch: Partial<PetState>) =>
      (await api.patch<PetState>("/pet", patch)).data,
    // Optimistic: update the shared cache immediately so the corner cat and the
    // settings form stay in lockstep; the server reply (skin clamped, etc.)
    // replaces it on success.
    onMutate: async (patch) => {
      await qc.cancelQueries({ queryKey: ["pet"] });
      const prev = qc.getQueryData<PetState>(["pet"]);
      if (prev) qc.setQueryData<PetState>(["pet"], { ...prev, ...patch });
      return { prev };
    },
    onError: (_e, _patch, ctx) => {
      if (ctx?.prev) qc.setQueryData(["pet"], ctx.prev);
    },
    onSuccess: (data) => qc.setQueryData(["pet"], data),
  });
}

/** Mark the user active today; the server rolls the daily streak atomically.
 *  Authoritative (no optimistic write) so a daily visit can't be lost to a
 *  rollback or a race — that was the streak-reset bug. Retries transient fails. */
export function useVisitPet() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (today: string) =>
      (await api.post<PetState>("/pet/visit", { today })).data,
    onSuccess: (data) => qc.setQueryData(["pet"], data),
    retry: 2,
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

/** Global lesson search (Cmd+K). Server-side ranking; keep previous results
 *  on screen while the next keystroke's query is in flight. */
export function useSearch(q: string) {
  const query = q.trim();
  return useQuery({
    queryKey: ["search", query],
    queryFn: async () =>
      (await api.get<SearchOut>("/search", { params: { q: query } })).data,
    enabled: query.length >= 2,
    placeholderData: keepPreviousData,
    staleTime: Infinity,
  });
}
