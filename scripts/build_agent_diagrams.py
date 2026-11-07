"""Build the eight LangChain/LangGraph teaching diagrams offline (stdlib only).

Run from any directory: python3 scripts/build_agent_diagrams.py
All examples are synthetic; this script never calls a model or external tool.
"""
from html import escape
from pathlib import Path
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parents[1] / "frontend/public/lesson-media/llm"
INK, MUTED, BLUE, GREEN, ORANGE = "#172b4d", "#52647d", "#0c66e4", "#16825d", "#b65b13"
WHITE, COOL, MINT, WARM = "#ffffff", "#e9f2ff", "#e6f6ee", "#fff3eb"


class Diagram:
    def __init__(self, title, subtitle):
        self.parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720" viewBox="0 0 1200 720" role="img" aria-labelledby="title desc">',
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(subtitle)}. Учебный пример «Маяк», без внешних вызовов.</desc>',
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10z" fill="#8590a2"/></marker></defs>',
            '<rect width="1200" height="720" fill="#fbfaf8"/>',
        ]
        self.text(40, 53, title, 29, bold=True)
        self.text(40, 89, subtitle, 20, MUTED)
        self.text(40, 697, "МАЯК · учебный пример · без внешних вызовов", 18, MUTED)

    def text(self, x, y, value, size=22, color=INK, bold=False):
        # Conservative character-width estimate catches accidental canvas overflow.
        width = sum(0.92 if c in "WMЖШЩЮЫ@" else 0.64 for c in str(value)) * size
        assert 0 <= x and x + width < 1190 and size <= y <= 710, (value, x, y, width)
        self.parts.append(f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="{size}" fill="{color}" font-weight="{700 if bold else 400}">{escape(str(value))}</text>')

    def rect(self, x, y, w, h, fill=WHITE, color="#c7d1db"):
        assert 0 <= x < x + w <= 1200 and 0 <= y < y + h <= 720
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{color}" stroke-width="2"/>')

    def card(self, x, y, w, h, title, lines=(), fill=WHITE, color=BLUE):
        self.rect(x, y, w, h, fill, color)
        self.text(x+18, y+35, title, 24, color, True)
        assert 67 + max(0, len(lines)-1)*30 <= h-12 if lines else True
        for i, line in enumerate(lines):
            # Check against its own card, in addition to the canvas check.
            width = sum(0.92 if c in "WMЖШЩЮЫ@" else 0.64 for c in line)*21
            assert width <= w-32, (title, line, width, w)
            self.text(x+18, y+67+i*30, line, 21, MUTED)

    def arrow(self, x1, y1, x2, y2, via=None, color="#8590a2"):
        points = [(x1, y1), *(via or []), (x2, y2)]
        path = "M" + " L".join(f"{x} {y}" for x, y in points)
        self.parts.append(f'<path d="{path}" stroke="{color}" stroke-width="3" fill="none" marker-end="url(#arrow)"/>')

    def save(self, name):
        value = "\n".join(self.parts) + "\n</svg>\n"
        ET.fromstring(value)
        (OUT / f"agents-{name}.svg").write_text(value, encoding="utf-8")


def components():
    d = Diagram("Цепочка: кто что делает и какой тип передаёт", "Вопрос: «Можно вернуть заказ 42?» · политика: 45 дней, только неиспользованный товар")
    d.card(40, 148, 290, 170, "1 · Переменные", ["dict", '{question: "Можно', 'вернуть заказ 42?"}'], COOL)
    d.card(450, 148, 330, 170, "2 · Prompt template", ["Подставляет {question}", "Добавляет инструкцию", "Не вызывает модель"], COOL)
    d.arrow(340, 235, 440, 235)
    d.text(350, 213, "dict", 20, BLUE)
    d.arrow(790, 235, 1130, 375, via=[(1130, 235)])
    d.text(827, 207, "PromptValue", 20, BLUE)
    d.text(825, 268, "сообщения + факты:", 20, MUTED)
    d.text(825, 300, "age_days = 40", 20, MUTED)
    d.text(825, 330, "policy_days = 45", 20, MUTED)
    d.text(825, 360, "unused = true", 20, MUTED)
    d.card(650, 385, 510, 170, "3 · ChatModel", ["Формирует AIMessage · content:", '"Да: 40 ≤ 45,', 'товар не использован."'], MINT, GREEN)
    d.card(40, 385, 480, 170, "4 · StrOutputParser", ["Берёт текст content из AIMessage", 'str · "Да: 40 ≤ 45,', 'товар не использован."'], WARM, ORANGE)
    d.arrow(640, 470, 530, 470)
    d.text(526, 440, "AIMessage", 20, GREEN)
    d.text(40, 610, "Контекст модели: age_days = 40; unused = true; policy_days = 45.", 23)
    d.text(40, 650, "Parser извлекает текст; правильность решения проверяется отдельно.", 23, ORANGE)
    d.save("components")


def invocations():
    d = Diagram("invoke, batch и stream: три способа получить выход", "Одна Runnable-цепочка; способ вызова меняет форму получения результата")
    rows = [
        (135, "invoke", "1 вход", "1 полный результат", COOL, BLUE),
        (290, "batch", "[вход 1, вход 2, вход 3]", "[выход 1, выход 2, выход 3]", MINT, GREEN),
        (445, "stream", "1 вход", "порция 1 → 2 → 3 → …", WARM, ORANGE),
    ]
    for y, name, inp, output, fill, color in rows:
        d.rect(40, y, 1120, 130, fill, color)
        d.text(60, y+40, name, 27, color, True)
        d.text(238, y+48, inp, 23)
        d.arrow(575, y+60, 685, y+60)
        d.text(713, y+48, output, 23)
        note = {"invoke": "Например: итоговая строка с ответом о заказе 42.", "batch": "Три независимых запроса; batch не обещает один API-вызов.", "stream": "Порции одного результата; их тип и границы зависят от реализации."}[name]
        d.text(238, y+98, note, 20, MUTED)
    d.text(40, 638, "Stream — не три независимых ответа; batch — не один общий диалог.", 23, bold=True)
    d.save("invocations")


def contracts():
    d = Diagram("Два контракта: данные ответа и запрос действия", "Structured output описывает результат; tool call просит приложение вызвать инструмент")
    d.card(40, 140, 545, 390, "Structured output", ["Схема Decision (Pydantic)", "status: allowed / denied / unknown", "reason: str; sources: list[str]", "", "Результат:", 'status: "allowed"', 'reason: "40 ≤ 45; unused = true"', 'sources: ["policy-v2", "order-42"]', "Ответ уже имеет нужную форму."], COOL)
    d.card(615, 140, 545, 390, "Tool call", ["Имя инструмента + аргументы", 'name: "get_order"', "args: {order_id: 42}", "", "Это просьба получить данные.", "Приложение проверяет аргументы", "и право доступа, затем вызывает", "свою функцию get_order(42).", "Модель сама её не исполняет."], MINT, GREEN)
    d.card(40, 570, 1120, 94, "Валидация формы ≠ проверка истины", ["bool / str / схема не доказывают, что заказ существует или правила соблюдены."], WARM, ORANGE)
    d.save("contracts")


def tool_loop():
    d = Diagram("Tool loop: модель предлагает, приложение выполняет", "Чтение заказа 42: age_days = 40, unused = true · правило возврата: ≤ 45 дней и unused")
    xs = [40, 425, 810]
    for x, title, fill in zip(xs, ["ПРИЛОЖЕНИЕ", "МОДЕЛЬ", "ИНСТРУМЕНТ"], [COOL, WHITE, MINT]):
        d.rect(x, 127, 350, 483, fill)
        d.text(x+18, 163, title, 24, BLUE, True)
    d.text(58, 222, "1 · Вопрос + политика", 21)
    d.arrow(300, 237, 480, 237)
    d.text(443, 281, "2 · get_order(order_id=42)", 21)
    d.text(443, 311, "tool call · id = call_1", 21, MUTED)
    d.arrow(490, 327, 310, 327)
    d.text(58, 370, "3 · Права + args → exec", 21)
    d.arrow(320, 385, 840, 385)
    d.text(828, 429, "4 · Данные заказа", 21)
    d.text(828, 459, "40 дней; unused = true", 21, MUTED)
    d.arrow(840, 478, 320, 478)
    d.text(58, 516, "5 · ToolMessage", 21)
    d.text(58, 546, "result + call_1 → модель", 21, MUTED)
    d.arrow(320, 562, 480, 562)
    d.text(443, 594, "6 · «Да, условия выполнены»", 21)
    d.arrow(490, 604, 310, 604)
    d.text(40, 648, "Приложение передаёт результат с тем же tool_call_id; затем модель отвечает.", 23)
    d.save("tool-loop")


def patterns():
    d = Diagram("Chain, workflow, agent: кто выбирает следующий шаг", "Выбор зависит от задачи, контроля, задержки и стоимости; дешевле не всегда значит лучше")
    for x, title, lines, fill, color in [
        (40, "Chain · фиксировано", ["Заданный порядок", "Prompt", "↓", "Model", "↓", "Parser"], COOL, BLUE),
        (420, "Workflow · ветвление", ["Заданные переходы", "Проверка заказа", "↓", "eligible?", "да → ответ", "нет → отказ"], MINT, GREEN),
        (800, "Agent · цикл", ["Модель выбирает шаг", "Model → tool call", "↑                 ↓", "результат ← exec", "", "до ответа / лимита"], WARM, ORANGE),
    ]:
        d.card(x, 140, 360, 298, title, lines, fill, color)
    d.card(40, 477, 1120, 168, "Две организации агентного цикла", ["ReAct: следующий шаг → действие → наблюдаемый результат → следующий шаг.", "Plan-and-execute: план → выполнение шагов → при необходимости перепланирование.", "На схеме только действия и результаты; скрытые рассуждения не отображаются."], WHITE)
    d.save("patterns")


def state():
    d = Diagram("StateGraph: узлы возвращают обновления состояния", "State — общие данные графа; update описывает изменение, а не весь новый снимок")
    d.card(40, 135, 335, 215, "До · state", ["order_id: 42", "age_days: 40", "unused: true", "events: [\"loaded\"]", "eligible: null"], COOL)
    d.arrow(385, 230, 425, 230)
    d.card(440, 135, 320, 190, "Узел check_policy", ["Читает state", "Возвращает update:", "eligible: true", "events: [\"policy\"]"], WHITE)
    d.arrow(770, 230, 810, 230)
    d.card(825, 135, 335, 230, "После · state", ["order_id: 42", "age_days: 40", "unused: true", "eligible: true", 'events: ["loaded",', '"policy"]'], MINT, GREEN)
    d.card(40, 390, 545, 118, "Поле без reducer → замена", ["eligible: null → true", "Для events без reducer: [\"policy\"]"], WARM, ORANGE)
    d.card(615, 390, 545, 118, "events с reducer → накопление", ['["loaded"] + ["policy"]', '= ["loaded", "policy"]'], MINT, GREEN)
    d.text(40, 543, "Условный переход", 24, BLUE, True)
    d.card(360, 515, 290, 106, "Данных хватает?", ["Routing по state"])
    d.arrow(660, 548, 860, 548)
    d.text(705, 530, "да", 21, GREEN)
    d.text(885, 556, "ответ → END", 23, GREEN)
    d.arrow(500, 631, 180, 330, via=[(500, 657), (20, 657), (20, 350), (180, 350)])
    d.text(65, 617, "нет → загрузить ещё", 21, ORANGE)
    d.save("state")


def threads():
    d = Diagram("thread_id связывает снимки одного выполнения", "Checkpointer сохраняет состояние по шагам; конфигурация выбирает нужную историю")
    for y, thread, labels, fill, color in [
        (150, 'thread_id = "return-42"', ["s₀ · вопрос", "s₁ · заказ загружен", "s₂ · ответ"], COOL, BLUE),
        (330, 'thread_id = "return-77"', ["s₀ · другой вопрос", "s₁ · другие данные", "s₂ · свой ответ"], MINT, GREEN),
    ]:
        d.rect(40, y, 1120, 146, fill, color)
        d.text(60, y+34, thread, 24, color, True)
        for i, label in enumerate(labels):
            x = 70 + i*370
            d.rect(x, y+60, 320, 63, WHITE)
            d.text(x+15, y+100, label, 22)
            if i < 2:
                d.arrow(x+325, y+92, x+360, y+92)
    d.card(40, 520, 545, 118, "RAM saver", ["Удобен локально; перезапуск процесса", "теряет историю в оперативной памяти."], WARM, ORANGE)
    d.card(615, 520, 545, 118, "SQLite / Postgres saver", ["Снимки хранятся в базе; срок жизни", "зависит от хранения и очистки."], WHITE)
    d.text(40, 673, "thread_id — строковый ключ, не поток ОС и не проверка прав доступа.", 23, bold=True)
    d.save("threads")


def interrupt():
    d = Diagram("interrupt: пауза и повторный запуск узла", "Маяк подготовил черновик для заказа 42; сохранение требует решения человека")
    d.card(40, 140, 330, 140, "1 · draft", ["Подготовить черновик", "Без сохранения в базу"], COOL)
    d.arrow(380, 210, 430, 210)
    d.card(440, 140, 320, 140, "2 · interrupt()", ["Пауза + checkpoint", "Дождаться человека"], WARM, ORANGE)
    d.arrow(770, 210, 820, 210)
    d.card(830, 140, 330, 140, "3 · Решение", ["approve / reject", "Command(resume=…)"], MINT, GREEN)
    d.arrow(995, 290, 610, 345, via=[(995, 320), (610, 320)])
    d.rect(40, 350, 720, 229, WHITE, ORANGE)
    d.text(58, 386, "4 · Узел запускается С НАЧАЛА", 25, ORANGE, True)
    d.text(58, 430, "Код до interrupt выполняется снова", 24, ORANGE, True)
    d.text(58, 466, "interrupt получает значение resume → проверка решения", 22)
    d.text(58, 502, "approve → действие; reject → завершить без действия", 22)
    d.text(58, 544, "Локальные переменные не восстанавливаются как стек.", 22, MUTED)
    d.arrow(770, 460, 820, 460)
    d.card(830, 350, 330, 229, "5 · Только approve", ["Сохранить черновик", "после одобрения", "", "Ключ идемпотентности:", '"order-42:draft-v1"'], MINT, GREEN)
    d.text(40, 627, "До паузы — безопасные повторяемые шаги; побочный эффект — после проверки.", 23)
    d.text(40, 665, "Повторный запуск возможен: защита от дублей нужна и после одобрения.", 23, ORANGE)
    d.save("interrupt")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for build in (components, invocations, contracts, tool_loop, patterns, state, threads, interrupt):
        build()
    print("Built 8 agent diagrams (1200 × 720, valid SVG XML).")


if __name__ == "__main__":
    main()
