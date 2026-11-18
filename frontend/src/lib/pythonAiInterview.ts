import questionBank from "../content/interview/python-ai-questions.json";

export const pythonAiInterviewPath = "/cheatsheets/python-ai-interview";

export const interviewTopics = [
  "python", "backend", "rag", "eval", "agents", "llm", "ml", "coding",
] as const;
export type InterviewTopic = (typeof interviewTopics)[number];

export const interviewPriorities = ["first", "next", "deep"] as const;

type InterviewQuestion = {
  topic: InterviewTopic;
  question: string;
  answer: string;
  followUp: string;
};

const bank: Record<(typeof interviewPriorities)[number], InterviewQuestion[]> =
  questionBank as Record<(typeof interviewPriorities)[number], InterviewQuestion[]>;

export const interviewQuestions = interviewPriorities
  .flatMap((priority) => bank[priority].map((question) => ({ ...question, priority })))
  .map((question, index) => ({ ...question, rank: index + 1 }));

export function filterQuestions(topic: InterviewTopic | null, query: string) {
  const normalize = (value: string) => value.toLowerCase().replaceAll("ё", "е");
  const words = normalize(query).trim().split(/\s+/).filter(Boolean);

  return interviewQuestions.filter((question) => {
    if (topic && question.topic !== topic) return false;
    const text = normalize([question.question, question.answer, question.followUp].join(" "));
    return words.every((word) => text.includes(word));
  });
}

export const sourceKinds = ["interview", "role"] as const;

type InterviewSource = {
  title: string;
  url: string;
  kind: (typeof sourceKinds)[number];
  type: "officialFormat" | "publicBreakdown" | "pastHiringEvent" | "jobPosting";
  topics: InterviewTopic[];
};

export const interviewSources: InterviewSource[] = [
  {
    title: "SberDevices · Python Developer",
    url: "https://developers.sber.ru/kak-v-sbere/interview/python_senior_mid",
    kind: "interview",
    type: "officialFormat",
    topics: ["python", "backend", "coding"],
  },
  {
    title: "GigaChat Data Team · ML Engineer",
    url: "https://developers.sber.ru/kak-v-sbere/one-day-offer/ml_february_2026",
    kind: "interview",
    type: "officialFormat",
    topics: ["python", "coding", "ml"],
  },
  {
    title: "Сбер · Python Developer (Unicode School)",
    url: "https://unicode.school/media/provalnoe-sobesedovanie-v-sber-na-python-razrabotchika-zhestkiy-sobeseduyuschiy/",
    kind: "interview",
    type: "publicBreakdown",
    topics: ["python", "backend"],
  },
  {
    title: "Сбер · Data Scientist (Unicode School)",
    url: "https://unicode.school/media/zhestkoe-sobesedovanie-v-sber-na-data-scientist/",
    kind: "interview",
    type: "publicBreakdown",
    topics: ["python", "llm", "ml"],
  },
  {
    title: "SberDevices · Agent Execution Framework",
    url: "https://developers.sber.ru/kak-v-sbere/one-day-offer/pyth_august_2026",
    kind: "role",
    type: "pastHiringEvent",
    topics: ["python", "backend", "rag", "agents", "llm"],
  },
  {
    title: "Сбер · AI Solutions (NLP / LLM)",
    url: "https://developers.sber.ru/kak-v-sbere/one-day-offer/solutions_june",
    kind: "role",
    type: "pastHiringEvent",
    topics: ["python", "backend", "rag", "agents", "llm"],
  },
  {
    title: "SberDevices · ML HomeOS / Search",
    url: "https://developers.sber.ru/kak-v-sbere/one-day-offer/ml_august_2026",
    kind: "role",
    type: "pastHiringEvent",
    topics: ["python", "rag", "eval", "llm"],
  },
  {
    title: "QSOFT / TEAMLY · Python AI, Middle",
    url: "https://career.habr.com/vacancies/1000169407",
    kind: "role",
    type: "jobPosting",
    topics: ["python", "backend", "rag", "eval", "agents", "llm"],
  },
  {
    title: "Яндекс · ML-разработчик агентов Алисы",
    url: "https://career.habr.com/vacancies/1000164325",
    kind: "role",
    type: "jobPosting",
    topics: ["python", "rag", "agents", "llm", "eval"],
  },
  {
    title: "Сбер · Lead Python / Блок «Финансы»",
    url: "https://developers.sber.ru/kak-v-sbere/one-day-offer/python_august_2026",
    kind: "role",
    type: "pastHiringEvent",
    topics: ["python", "backend", "rag", "agents", "llm"],
  },
];

export const sourceTotals = {
  interview: interviewSources.filter((source) => source.kind === "interview").length,
  role: interviewSources.filter((source) => source.kind === "role").length,
};

export const sourceCoverage = interviewTopics.map((topic) => ({
  topic,
  interview: interviewSources.filter(
    (source) => source.kind === "interview" && source.topics.includes(topic),
  ).length,
  role: interviewSources.filter(
    (source) => source.kind === "role" && source.topics.includes(topic),
  ).length,
}));
