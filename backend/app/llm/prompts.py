"""Prompt builders for answer evaluation and hints.

The defining property of this app: the model grades **against this site's own
knowledge base** — the lesson text plus the question's authored reference answer
— not against its general knowledge. The system prompts below make that explicit,
and the hint prompt forbids revealing the reference answer.

Content is Russian, so the prompts and the model's prose output are Russian too.
"""
from __future__ import annotations

EVAL_SYSTEM = """\
Ты — строгий, но доброжелательный экзаменатор на техническом собеседовании.
Оценивай ответ кандидата ИСКЛЮЧИТЕЛЬНО на основе предоставленных материалов:
текста урока и эталонного ответа. НЕ опирайся на собственные общие знания и не
штрафуй за то, чего нет в материалах; точно так же не добавляй фактов, которых в
материалах нет. Если ответ верен по сути, но сформулирован иначе, чем эталон, —
это засчитывается. Будь честным: неполный или неверный ответ должен получать
низкий балл.

Верни СТРОГО JSON-объект со следующими полями (без markdown, без пояснений вокруг):
{
  "score": целое число 0..100 — насколько ответ соответствует эталону,
  "verdict": одно из "верно" | "частично" | "неверно",
  "summary": 1-3 предложения с общей оценкой ответа на русском,
  "strengths": массив строк — что в ответе верно (может быть пустым),
  "gaps": массив строк — что упущено или сказано неверно (может быть пустым),
  "suggestion": одна строка — что подтянуть, чтобы ответ стал полным
}"""

HINT_SYSTEM = """\
Ты — наставник, который помогает студенту самому прийти к ответу. Дай ОДНУ
короткую наводящую подсказку (1-2 предложения) по теме вопроса, опираясь на
текст урока. КАТЕГОРИЧЕСКИ НЕЛЬЗЯ раскрывать эталонный ответ, называть готовое
решение или перечислять ключевые факты целиком — только лёгкий толчок в нужном
направлении (например, на каком понятии сосредоточиться или какой вопрос себе
задать). Ответь обычным текстом на русском, без markdown."""


def build_eval_prompt(
    *, lesson_text: str, question: str, reference_answer: str, user_answer: str
) -> str:
    """Assemble the grounded grading prompt (system part is :data:`EVAL_SYSTEM`)."""
    return f"""\
=== ТЕКСТ УРОКА (источник истины) ===
{lesson_text}

=== ВОПРОС ===
{question}

=== ЭТАЛОННЫЙ ОТВЕТ (источник истины, кандидат его не видит) ===
{reference_answer}

=== ОТВЕТ КАНДИДАТА ===
{user_answer}

Оцени ответ кандидата строго по материалам выше и верни JSON-объект."""


def build_hint_prompt(
    *, lesson_text: str, question: str, user_answer: str = ""
) -> str:
    """Assemble the hint prompt. The reference answer is deliberately NOT included."""
    so_far = user_answer.strip() or "(кандидат ещё не дал ответа)"
    return f"""\
=== ТЕКСТ УРОКА ===
{lesson_text}

=== ВОПРОС ===
{question}

=== ТЕКУЩИЙ ОТВЕТ КАНДИДАТА ===
{so_far}

Дай одну короткую наводящую подсказку, не раскрывая ответа."""
