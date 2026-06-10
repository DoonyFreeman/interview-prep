import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { RequireAuth } from "./auth/RequireAuth";
import { LoginPage } from "./pages/LoginPage";
import { CatalogPage } from "./pages/CatalogPage";
import { CoursePage } from "./pages/CoursePage";
import { LessonPage } from "./pages/LessonPage";
import { QuizPage } from "./pages/QuizPage";
import { QuestionsPage } from "./pages/QuestionsPage";
import { ProgressPage } from "./pages/ProgressPage";
import { SettingsPage } from "./pages/SettingsPage";
import { ReviewPage } from "./pages/ReviewPage";
import { GlossaryPage } from "./pages/GlossaryPage";
import { GlossaryQuizPage } from "./pages/GlossaryQuizPage";
import { SlangPage } from "./pages/SlangPage";
import { DictLayout } from "./components/DictLayout";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<CatalogPage />} />
        {/* Glossary + Slang share a persistent tab shell (DictLayout). */}
        <Route element={<DictLayout />}>
          <Route path="/glossary" element={<GlossaryPage />} />
          <Route path="/slang" element={<SlangPage />} />
        </Route>
        <Route path="/glossary/quiz" element={<GlossaryQuizPage />} />
        <Route path="/slang/quiz" element={<GlossaryQuizPage kind="slang" />} />
        <Route path="/review" element={<ReviewPage />} />
        <Route path="/progress" element={<ProgressPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/courses/:courseSlug" element={<CoursePage />} />
        <Route
          path="/courses/:courseSlug/lessons/:lessonSlug"
          element={<LessonPage />}
        />
        <Route
          path="/courses/:courseSlug/lessons/:lessonSlug/questions"
          element={<QuestionsPage />}
        />
        <Route
          path="/courses/:courseSlug/lessons/:lessonSlug/quiz"
          element={<QuizPage />}
        />
        <Route
          path="/courses/:courseSlug/lessons/:lessonSlug/quiz/:questionId"
          element={<QuizPage />}
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
