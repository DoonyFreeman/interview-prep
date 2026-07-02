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
  /** Authored reference answer — revealed only after grading. */
  reference_answer: string;
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

// --- Lesson MCQ self-test (closed questions, graded client-side) -----------
export interface McqQuestion {
  slug: string; // stable id, also the result key
  type: "single" | "boolean" | string;
  text: string;
  options: string[];
  correct_index: number;
  explanation_md: string;
  concept_slug: string;
  concept_title: string;
  anchor: string;
  difficulty: number;
}

export interface LessonTest {
  course_slug: string;
  lesson_slug: string;
  total: number;
  questions: McqQuestion[];
}

export interface TestResultItem {
  slug: string;
  correct: boolean;
}

export interface LessonTestProgress {
  total: number;
  answered: number;
  correct: number;
  attempts: number;
  last_score: number;
  best_score: number;
  passed: boolean;
}

export interface TestsCourseOverview {
  slug: string;
  total: number;
  passed: number;
  started: number;
}

export interface TestsOverview {
  total: number;
  passed: number;
  started: number;
  courses: TestsCourseOverview[];
}

// --- Pet (corner cat) state ------------------------------------------------
export interface PetState {
  name: string;
  skin: string;
  streak: number;
  best_streak: number;
  last_active_day: string | null;
  hidden: boolean;
}

/** One topic the corner cat can mention, from a completed lesson (one per
 *  concept). `definition` is the first prose paragraph of its section ("" for
 *  a code-only section). Mirrors backend `CatThoughtOut`. */
export interface CatThoughtApi {
  key: string;
  term: string;
  definition: string;
  course_slug: string;
  lesson_slug: string;
  anchor: string;
}

// --- Global lesson search ----------------------------------------------------
export interface SearchResult {
  course_slug: string;
  course_title: string;
  lesson_slug: string;
  lesson_title: string;
  section_title: string | null;
  anchor: string; // "" => lesson top
  snippet: string;
  match_field: "lesson_title" | "section_title" | "body" | "course_title";
}

export interface SearchOut {
  query: string;
  count: number;
  results: SearchResult[];
}
