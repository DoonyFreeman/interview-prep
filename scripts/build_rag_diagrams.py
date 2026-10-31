"""Offline, dependency-free authoring for the three deep RAG lessons."""
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "frontend/public/lesson-media/llm"
INK, MUTED = "#172b4d", "#52647d"
BLUE, GREEN, ORANGE = "#0c66e4", "#16825d", "#b65b13"


class Diagram:
    def __init__(self, title, subtitle):
        self.parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="720" viewBox="0 0 1200 720" role="img" aria-labelledby="title desc">',
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(subtitle)}</desc>',
            '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10z" fill="#8590a2"/></marker></defs>',
            '<rect width="1200" height="720" fill="#fbfaf8"/>',
        ]
        self.text(40, 53, title, 29, bold=True)
        self.text(40, 86, subtitle, 18, MUTED)

    def text(self, x, y, value, size=20, color=INK, bold=False):
        self.parts.append(f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="{size}" fill="{color}" font-weight="{700 if bold else 400}">{escape(str(value))}</text>')

    def rect(self, x, y, w, h, fill="#fff", stroke="#c7d1db"):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')

    def card(self, x, y, w, h, title, lines, fill="#fff", color=BLUE):
        self.rect(x, y, w, h, fill, color)
        self.text(x+18, y+33, title, 21, color, True)
        for i, line in enumerate(lines):
            self.text(x+18, y+66+i*27, line, 18, MUTED)

    def arrow(self, x1, y1, x2, y2):
        self.parts.append(f'<path d="M{x1} {y1} L{x2} {y2}" stroke="#8590a2" stroke-width="3" fill="none" marker-end="url(#arrow)"/>')

    def line(self, x1, y1, x2, y2, color=BLUE, width=3):
        self.parts.append(f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{color}" stroke-width="{width}" fill="none"/>')

    def dot(self, x, y, color=BLUE, radius=7):
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{color}"/>')

    def save(self, name):
        (OUT / f"rag-deep-{name}.svg").write_text("\n".join(self.parts)+"\n</svg>\n", encoding="utf-8")


def lifecycle():
    d = Diagram("Документ обновился — индекс тоже должен обновиться", "Два процесса: подготовка знаний заранее и ответ на конкретный вопрос")
    d.text(40, 134, "1. ИНДЕКСАЦИЯ · при изменении источника", 18, MUTED, True)
    data = [
        ("Документ v2", ["Возврат: 45 дней", "v1: 30 дней — устарел"]),
        ("Чанки v2", ["Текст + заголовок", "doc_id + версия + права"]),
        ("Векторы v2", ["Модель A, размер d", "Та же схема обработки"]),
        ("Новый индекс", ["Проверить готовность", "Убрать старую версию"]),
    ]
    for i, (title, lines) in enumerate(data):
        x = 40+i*290
        d.card(x, 154, 250, 145, title, lines)
        if i < 3:
            d.arrow(x+253, 225, x+282, 225)
    d.text(40, 354, "2. ОТВЕТ · на каждый запрос пользователя", 18, MUTED, True)
    for i, (title, lines) in enumerate([
        ("Вопрос", ["«Какой срок возврата?»", "→ вектор моделью A"]),
        ("Поиск", ["Только доступные v2", "Кандидаты → реранкинг"]),
        ("Контекст", ["Нужные чанки + ссылки", "В пределах окна LLM"]),
        ("Ответ", ["«45 дней [doc:v2]»", "Проверяем опору на текст"]),
    ]):
        x = 40+i*290
        d.card(x, 376, 250, 145, title, lines, "#e9f2ff")
        if i < 3:
            d.arrow(x+253, 448, x+282, 448)
    d.card(40, 566, 1120, 112, "Если ответ всё ещё «30 дней»", ["Проверьте версию на каждом этапе: источник → чанк → индекс → найденный контекст → ответ.", "Новый промпт сам по себе не перечитает документ и не пересчитает старые векторы."], "#fff3eb", ORANGE)
    d.save("lifecycle")


def vectors():
    d = Diagram("Похожесть векторов: направление и длина", "Двумерный учебный пример; в настоящем эмбеддинге координат обычно гораздо больше")
    d.rect(40, 120, 520, 425)
    d.arrow(105, 470, 515, 470)
    d.arrow(105, 470, 105, 170)
    d.text(477, 506, "ось 1", 17, MUTED)
    d.text(60, 158, "ось 2", 17, MUTED)
    d.line(105, 470, 265, 310, GREEN)
    d.line(105, 470, 425, 470, ORANGE, 5)
    d.dot(265, 470)
    d.dot(425, 470, ORANGE)
    d.dot(265, 310, GREEN)
    d.text(225, 505, "q = (1, 0)", 19, BLUE, True)
    d.text(353, 445, "a = (2, 0)", 19, ORANGE, True)
    d.text(273, 299, "b = (1, 1)", 19, GREEN, True)
    d.text(160, 400, "угол 45°", 19, MUTED)
    d.card(590, 120, 570, 126, "Cosine · сравнивает направление", ["cos(q, a) = 1; cos(q, b) ≈ 0,707", "Больше → ближе по направлению. Длина не влияет."])
    d.card(590, 268, 570, 126, "Dot product · направление и длина", ["q · a = 2; q · b = 1", "Больше → выше оценка. Шкала зависит от модели."], "#fff3eb", ORANGE)
    d.card(590, 416, 570, 129, "L2 · расстояние между точками", ["L2(q, a) = 1; L2(q, b) = 1", "Меньше → ближе. Здесь расстояния равны."], "#dcfff1", GREEN)
    d.card(40, 574, 1120, 110, "После нормализации ненулевых векторов до длины 1", ["dot = cosine; квадрат L2 = 2 − 2 × cosine → одинаковый порядок соседей.", "Одинаковая размерность не делает векторы разных моделей совместимыми. Score ≠ вероятность."], "#e9f2ff")
    d.save("vectors")


def search():
    d = Diagram("Как искать соседей: все точки, граф или группы", "Точный поиск — эталон близости по выбранной метрике; ANN ускоряет поиск ценой возможных пропусков")
    titles = [("Exact · перебор", ["Сравнить запрос со всеми", "векторами допустимого набора.", "Ничего не пропустим по метрике."], BLUE), ("HNSW · граф", ["Идти по связям между точками.", "efSearch ↑: шире поиск;", "обычно точнее, но медленнее."], GREEN), ("IVF · группы", ["Сначала выбрать группы.", "nprobe ↑: проверить больше", "из nlist групп индекса."], ORANGE)]
    for i, (title, lines, color) in enumerate(titles):
        x = 40+i*380
        d.card(x, 125, 350, 482, title, [], color=color)
        for row in range(3):
            for col in range(4):
                px, py = x+60+col*68, 238+row*75
                d.dot(px, py, color, 7)
                if i == 0:
                    d.line(x+172, 465, px, py, "#c7d1db", 1)
                elif i == 1 and col < 3:
                    d.line(px, py, px+68, py+(75 if row == 0 else 0), "#94b8a8", 2)
        if i == 2:
            for col in range(2):
                d.rect(x+37+col*138, 208, 119, 208, "none", "#e8bb98")
            d.line(x+172, 465, x+95, 315, color)
        if i == 1:
            d.arrow(x+172, 453, x+60, 388)
            d.line(x+60, 388, x+60, 313, color, 4)
            d.line(x+60, 313, x+128, 313, color, 4)
            d.line(x+264, 238, x+264, 313, "#94b8a8", 2)
        d.dot(x+172, 465, INK, 10)
        d.text(x+190, 471, "запрос", 16, MUTED)
        for j, line in enumerate(lines):
            d.text(x+18, 523+j*27, line, 18, MUTED)
    d.text(40, 650, "ANN recall: сколько точных соседей сохранили?  ≠  Retrieval Recall: сколько полезных источников нашли?", 20, INK, True)
    d.text(40, 682, "Права доступа ограничивают допустимый набор до передачи текста реранкеру, LLM и пользователю.", 19, MUTED)
    d.save("search")


def ranking():
    d = Diagram("Гибридный поиск: найти → объединить → перечитать", "RRF объединяет позиции в списках; реранкер заново оценивает пары «вопрос + фрагмент»")
    d.card(40, 132, 320, 153, "BM25 · совпадение слов", ["1. A: ERR-4031", "2. B: общие причины отказа", "3. D: похожий код"])
    d.card(40, 322, 320, 153, "Dense · близость смысла", ["1. B: общие причины отказа", "2. C: доступ к пространству", "3. A: ERR-4031"], "#dcfff1", GREEN)
    d.arrow(370, 207, 426, 276)
    d.arrow(370, 396, 426, 308)
    d.card(442, 174, 315, 259, "RRF · c = 60", ["A: 1/61 + 1/63 ≈ 0,0323", "B: 1/62 + 1/61 ≈ 0,0325", "C: 1/62; D: 1/63", "Порядок: B → A → C → D", "Повторы склеиваем по ID."], "#e9f2ff")
    d.arrow(768, 297, 804, 297)
    d.card(820, 174, 340, 259, "Cross-encoder", ["Читает вопрос и каждый", "кандидат вместе.", "Может изменить порядок.", "Не вернёт документ, которого", "нет среди кандидатов."], "#fff3eb", ORANGE)
    d.card(40, 528, 1120, 151, "Кандидаты и контекст — разные бюджеты", ["Например: 20 BM25 + 20 dense → объединение → реранкинг → 5 фрагментов в промпт.", "Это пример настройки, а не универсальные числа. Проверяем качество, токены и задержку.", "Складывать сырые score BM25 и cosine без обоснованного приведения шкал нельзя."], "#fff")
    d.save("ranking")


def evaluation():
    d = Diagram("Одна выдача — четыре разных вопроса о качестве", "В корпусе 4 релевантных фрагмента. Смотрим первые k = 3: [неполезный, полезный, полезный]")
    for i, (label, fill, color) in enumerate([("1 · нет", "#ffeceb", "#ae2e24"), ("2 · да", "#dcfff1", GREEN), ("3 · да", "#dcfff1", GREEN)]):
        d.card(40+i*380, 124, 350, 88, label, [], fill, color)
    cards = [
        (40, 250, "Precision@3 = 2/3", ["Сколько полезного среди найденного?", "2 полезных / 3 результата ≈ 0,667."]),
        (610, 250, "Recall@3 = 2/4", ["Какую долю нужного нашли?", "2 найденных / 4 нужных = 0,5."]),
        (40, 414, "RR = 1/2; MRR — среднее RR", ["Где первый полезный результат?", "Он второй: обратная позиция = 0,5."]),
        (610, 414, "NDCG@3 ≈ 0,531", ["Насколько хорош порядок?", "DCG = 1/log₂3 + 1/log₂4 ≈ 1,131.", "IDCG = 1 + 1/log₂3 + 1/log₂4 ≈ 2,131."]),
    ]
    for x, y, title, lines in cards:
        d.card(x, y, 550, 143, title, lines)
    d.text(40, 610, "Для NDCG здесь релевантность 0/1, gain = 2ʳᵉˡ − 1; идеальная первая тройка — [1, 1, 1].", 20, MUTED)
    d.text(40, 647, "Эти числа проверяют поиск. Даже идеальная выдача не гарантирует правильный ответ LLM.", 20, INK, True)
    d.text(40, 681, "Пустая разметка / нет релевантных: отдельное правило оценки, а не деление на ноль.", 19, MUTED)
    d.save("evaluation")


def diagnosis():
    d = Diagram("Неверный ответ: проверяем первый сломанный этап", "Сохраняйте трассу на фиксированных учебных вопросах: версии, ID кандидатов, контекст и ответ")
    rows = [
        ("Источник", "В актуальном документе есть ответ?", "Нет → исправить базу знаний; не настраивать поиск."),
        ("Индекс", "Попали ли туда новые чанки v2?", "Нет → загрузка / нарезка / эмбеддинги / обновление."),
        ("Retrieval", "Есть ли нужный чанк в кандидатах?", "Нет → фильтры, модель, sparse/dense, ANN, размер списка."),
        ("Reranking", "Остался ли чанк после отбора?", "Нет → реранкер, дубли, лимит контекста и токенов."),
        ("Generation", "LLM передали нужный текст, а ответ неверен?", "Проверить инструкцию, цитаты, отказ и противоречия."),
    ]
    for i, (stage, question, action) in enumerate(rows):
        y = 122+i*100
        d.rect(40, y, 1120, 84, "#fff" if i % 2 == 0 else "#e9f2ff")
        d.text(58, y+33, stage, 21, BLUE, True)
        d.text(246, y+30, question, 20, INK, True)
        d.text(246, y+60, action, 18, MUTED)
    d.text(40, 657, "Faithfulness: ответ подтверждён контекстом?  ·  Relevance: отвечает на вопрос?  ·  Correctness: верен?", 19, INK, True)
    d.text(40, 690, "Устаревший контекст может дать верный пересказ и неверный по текущим правилам ответ.", 20, MUTED)
    d.save("diagnosis")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for build in (lifecycle, vectors, search, ranking, evaluation, diagnosis):
        build()
    print("Built 6 RAG diagrams (1200 × 720, SVG).")
