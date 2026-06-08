export interface CourseSummary {
  slug: string;
  title: string;
  description: string;
  order: number;
  lesson_count: number;
}

export interface LessonSummary {
  slug: string;
  title: string;
  order: number;
  duration_minutes: number;
  concept_count: number;
}

export interface CourseDetail {
  slug: string;
  title: string;
  description: string;
  order: number;
  lessons: LessonSummary[];
}

export interface ConceptOut {
  slug: string;
  title: string;
  anchor: string;
  order: number;
  question_count: number;
}

export interface LessonDetail {
  slug: string;
  title: string;
  course_slug: string;
  duration_minutes: number;
  markdown: string;
  concepts: ConceptOut[];
}

export interface TokenOut {
  access_token: string;
  token_type: string;
}

export interface UserOut {
  id: number;
  email: string;
  display_name: string;
  created_at: string;
}

export interface QuestionOut {
  id: number;
  text: string;
  difficulty: number;
  concept_slug: string;
  concept_title: string;
  anchor: string;
  course_slug: string;
  lesson_slug: string;
}

export interface QuestionStatus {
  id: number;
  text: string;
  difficulty: number;
  concept_slug: string;
  concept_title: string;
  anchor: string;
  attempts: number;
  last_score: number | null;
  last_verdict: string | null;
  last_attempted_at: string | null;
}

export interface LessonQuestions {
  course_slug: string;
  lesson_slug: string;
  questions: QuestionStatus[];
}

export interface ReviewItem {
  concept_slug: string;
  concept_title: string;
  course_slug: string;
  lesson_slug: string;
  anchor: string;
  last_score: number;
  reps: number;
  due_at: string;
  question_id: number | null;
}

export interface ReviewQueue {
  count: number;
  items: ReviewItem[];
}

export interface MasteryOut {
  reps: number;
  ease: number;
  interval_days: number;
  last_score: number;
  due_at: string;
  due: boolean;
}

export type Verdict = "верно" | "частично" | "неверно";

export interface EvaluationOut {
  attempt_id: number;
  score: number;
  verdict: Verdict | string;
  summary: string;
  strengths: string[];
  gaps: string[];
  suggestion: string;
  concept_slug: string;
  mastery: MasteryOut;
}

export interface HintOut {
  hint: string;
}

export interface ConceptProgressOut {
  slug: string;
  title: string;
  anchor: string;
  attempted: boolean;
  mastered: boolean;
  reps: number;
  last_score: number;
  due_at: string | null;
  due: boolean;
}

export interface LessonProgressOut {
  slug: string;
  title: string;
  completed: boolean;
  total_concepts: number;
  attempted_concepts: number;
  mastered_concepts: number;
  due_concepts: number;
  concepts: ConceptProgressOut[];
}

export interface CourseProgressOut {
  slug: string;
  title: string;
  total_concepts: number;
  attempted_concepts: number;
  mastered_concepts: number;
  due_concepts: number;
  lessons: LessonProgressOut[];
}

export interface ProgressOverviewOut {
  total_concepts: number;
  attempted_concepts: number;
  mastered_concepts: number;
  due_concepts: number;
  courses: CourseProgressOut[];
}

export interface GlossaryLink {
  course_slug: string;
  lesson_slug: string;
  anchor: string;
}

export interface GlossaryTerm {
  slug: string;
  term: string;
  category: string;
  short_md: string;
  aliases: string[];
  links: GlossaryLink[];
}

export interface GlossaryList {
  count: number;
  categories: string[];
  terms: GlossaryTerm[];
}

export interface GlossaryTermStat {
  term_slug: string;
  seen: number;
  correct: number;
  last_correct: boolean;
  mastered: boolean;
  last_seen_at: string;
}

export interface GlossaryCategoryProgress {
  category: string;
  total: number;
  seen: number;
  mastered: number;
}

export interface GlossaryProgress {
  total: number;
  seen: number;
  mastered: number;
  recorded: number;
  categories: GlossaryCategoryProgress[];
  terms: GlossaryTermStat[];
}

export interface QuizResultItem {
  term_slug: string;
  correct: boolean;
}

export interface AttemptOut {
  id: number;
  score: number;
  verdict: Verdict | string;
  summary: string;
  strengths: string[];
  gaps: string[];
  suggestion: string;
  answer_text: string;
  hint_used: boolean;
  created_at: string;
}

export interface QuestionAttempts {
  question_id: number;
  text: string;
  concept_title: string;
  anchor: string;
  course_slug: string;
  lesson_slug: string;
  attempts: AttemptOut[];
}

export interface LessonQuestionsProgress {
  slug: string;
  title: string;
  total: number;
  answered: number;
}

export interface CourseQuestionsProgress {
  slug: string;
  title: string;
  total: number;
  answered: number;
  lessons: LessonQuestionsProgress[];
}

export interface QuestionsProgress {
  total: number;
  answered: number;
  courses: CourseQuestionsProgress[];
}
