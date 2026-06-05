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
