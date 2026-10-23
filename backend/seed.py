"""初始化种子数据：7 个知识点 × 15 题 + 4 个徽章。

幂等：按 (level, sort_order) 判知识点，按 (knowledge_point_id, stem) 判题目。
内容按人教版（L1/L2 小学，L3 八年级上）范围编写。
"""

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Badge, KnowledgePoint, Question

# ---------------------------------------------------------------- 知识点定义

KP_DEFS = [
    ("L1", "字母表", "letter", 1),
    ("L1", "基础问候词", "word", 2),
    ("L2", "常用单词", "word", 1),
    ("L2", "简单拼写", "spelling", 2),
    ("L2", "单词跟读", "pronunciation", 3),
    ("L3", "听力理解", "listening", 1),
    ("L3", "拼写进阶", "spelling", 2),
]

DIFFICULTY = {"L1": 1, "L2": 2, "L3": 3}

# ---------------------------------------------------------------- 数据

GREETINGS = [
    ("早上好", "Good morning"),
    ("下午好", "Good afternoon"),
    ("晚上好", "Good evening"),
    ("晚安", "Good night"),
    ("你好", "Hello"),
    ("再见", "Goodbye"),
    ("谢谢", "Thank you"),
    ("对不起", "Sorry"),
    ("请", "Please"),
    ("是的", "Yes"),
    ("不是", "No"),
    ("你好吗", "How are you"),
    ("我很好", "I'm fine"),
    ("你叫什么名字", "What's your name"),
    ("很高兴认识你", "Nice to meet you"),
]

COMMON_WORDS = [
    ("学校", "school"),
    ("老师", "teacher"),
    ("学生", "student"),
    ("书", "book"),
    ("铅笔", "pencil"),
    ("书包", "bag"),
    ("尺子", "ruler"),
    ("橡皮", "eraser"),
    ("猫", "cat"),
    ("狗", "dog"),
    ("苹果", "apple"),
    ("香蕉", "banana"),
    ("红色", "red"),
    ("蓝色", "blue"),
    ("朋友", "friend"),
]

SPELLING_L2 = [
    ("苹果", "apple"),
    ("香蕉", "banana"),
    ("猫", "cat"),
    ("狗", "dog"),
    ("书", "book"),
    ("钢笔", "pen"),
    ("尺子", "ruler"),
    ("红色", "red"),
    ("蓝色", "blue"),
    ("绿色", "green"),
    ("学校", "school"),
    ("老师", "teacher"),
    ("朋友", "friend"),
    ("牛奶", "milk"),
    ("鸡蛋", "egg"),
]

PRONUNCIATION = [
    "apple",
    "banana",
    "cat",
    "dog",
    "book",
    "pen",
    "ruler",
    "red",
    "blue",
    "green",
    "school",
    "teacher",
    "friend",
    "milk",
    "egg",
]

LISTENING = [
    ("My favourite fruit is banana.", "banana", ["apple", "orange", "grape"]),
    ("I go to school by bus every day.", "school", ["park", "zoo", "library"]),
    ("My mother is a teacher.", "teacher", ["doctor", "driver", "farmer"]),
    ("There is a cat under the table.", "cat", ["dog", "bird", "fish"]),
    ("I would like a glass of milk.", "milk", ["juice", "water", "tea"]),
    ("We have English class on Monday.", "English", ["math", "music", "art"]),
    ("It is raining outside today.", "raining", ["snowing", "sunny", "windy"]),
    ("My father works in a hospital.", "hospital", ["school", "bank", "factory"]),
    ("She likes playing the piano.", "piano", ["guitar", "violin", "drum"]),
    ("The train leaves at eight o'clock.", "train", ["bus", "plane", "ship"]),
    ("I have two brothers and one sister.", "sister", ["brother", "cousin", "uncle"]),
    ("We are going to the park this weekend.", "park", ["museum", "cinema", "market"]),
    ("He is reading a book in the library.", "library", ["classroom", "office", "garden"]),
    ("Please open the window, it is hot.", "window", ["door", "box", "bag"]),
    ("My birthday is in September.", "September", ["October", "November", "December"]),
]

SPELLING_L3 = [
    ("环境", "environment"),
    ("污染", "pollution"),
    ("发明", "invention"),
    ("科学家", "scientist"),
    ("旅行", "travel"),
    ("健康", "health"),
    ("锻炼", "exercise"),
    ("习惯", "habit"),
    ("决定", "decision"),
    ("经验", "experience"),
    ("文化", "culture"),
    ("传统", "tradition"),
    ("想象", "imagination"),
    ("成功", "success"),
    ("挑战", "challenge"),
]

BADGES = [
    ("streak_3", "连续三天", "streak", 3),
    ("streak_7", "连续七天", "streak", 7),
    ("complete_l1_first", "初学有成", "complete_kp", 1),
    ("answer_100", "百题达成", "answer_correct", 100),
]

KEYS = ["A", "B", "C", "D"]


def make_choice(stem: str, correct: str, wrongs: list[str], rot: int) -> tuple[str, dict, str]:
    options = list(wrongs)
    pos = rot % 4
    options.insert(pos, correct)
    keyed = {KEYS[i]: options[i] for i in range(4)}
    return stem, keyed, KEYS[pos]


def build_letter_items() -> list[tuple[str, dict, str]]:
    items = []
    for i in range(1, 16):
        correct = chr(64 + i)
        wrongs = [chr(64 + ((i + d - 1) % 26) + 1) for d in (1, 2, 3)]
        stem, opts, ans = make_choice(f"字母表里第 {i} 个字母是哪个？", correct, wrongs, i - 1)
        items.append((stem, opts, ans))
    return items


def build_word_items(pairs: list[tuple[str, str]]) -> list[tuple[str, dict, str]]:
    items = []
    english = [en for _cn, en in pairs]
    total = len(pairs)
    for idx, (cn, en) in enumerate(pairs):
        wrongs = [english[(idx + k) % total] for k in (1, 2, 3)]
        stem, opts, ans = make_choice(f"“{cn}”用英语怎么说？", en, wrongs, idx)
        items.append((stem, opts, ans))
    return items


def build_listening_items() -> list[tuple[str, dict, str]]:
    items = []
    for idx, (sentence, correct, distractors) in enumerate(LISTENING):
        stem, opts, ans = make_choice(sentence, correct, distractors, idx)
        items.append((stem, opts, ans))
    return items


# ---------------------------------------------------------------- 写入


def seed_badges(db) -> None:
    for code, name, ctype, value in BADGES:
        exists = db.execute(select(Badge).where(Badge.code == code)).scalar_one_or_none()
        if exists is None:
            db.add(Badge(code=code, name=name, condition_type=ctype, condition_value=value))
    db.flush()


def ensure_kp(db, level: str, name: str, qtype: str, order: int) -> KnowledgePoint:
    kp = db.execute(
        select(KnowledgePoint).where(
            KnowledgePoint.level == level, KnowledgePoint.sort_order == order
        )
    ).scalar_one_or_none()
    if kp is None:
        kp = KnowledgePoint(level=level, name=name, sort_order=order, question_type=qtype)
        db.add(kp)
        db.flush()
    return kp


def ensure_question(db, kp: KnowledgePoint, qtype: str, stem: str, options, answer: str, difficulty: int):
    exists = db.execute(
        select(Question).where(Question.knowledge_point_id == kp.id, Question.stem == stem)
    ).scalar_one_or_none()
    if exists is not None:
        return
    db.add(
        Question(
            knowledge_point_id=kp.id,
            question_type=qtype,
            stem=stem,
            options=options,
            answer=answer,
            difficulty=difficulty,
        )
    )


def seed() -> None:
    with SessionLocal() as db:
        seed_badges(db)

        kps: dict[tuple[str, int], KnowledgePoint] = {}
        for level, name, qtype, order in KP_DEFS:
            kps[(level, order)] = ensure_kp(db, level, name, qtype, order)

        def add_all(kp, qtype, items):
            for stem, opts, ans in items:
                ensure_question(db, kp, qtype, stem, opts, ans, DIFFICULTY[kp.level])

        add_all(kps[("L1", 1)], "letter", build_letter_items())
        add_all(kps[("L1", 2)], "word", build_word_items(GREETINGS))
        add_all(kps[("L2", 1)], "word", build_word_items(COMMON_WORDS))
        add_all(kps[("L3", 1)], "listening", build_listening_items())

        for cn, word in SPELLING_L2:
            ensure_question(
                db, kps[("L2", 2)], "spelling", f"“{cn}”怎么拼写？", None, word, 2
            )
        for cn, word in SPELLING_L3:
            ensure_question(
                db, kps[("L3", 2)], "spelling", f"“{cn}”怎么拼写？", None, word, 3
            )
        for word in PRONUNCIATION:
            ensure_question(db, kps[("L2", 3)], "pronunciation", word, None, word, 2)

        db.commit()

        total_kp = db.execute(select(KnowledgePoint)).scalars().all()
        total_q = db.execute(select(Question)).scalars().all()
        print(f"知识点 {len(total_kp)} 个，题目 {len(total_q)} 道")

        for kp in total_kp:
            count = len([q for q in total_q if q.knowledge_point_id == kp.id])
            print(f"  {kp.level} {kp.name}({kp.question_type}) -> {count} 题")

        # 一致性校验：知识点题型与其下题目题型必须一致
        bad = []
        for kp in total_kp:
            types = {q.question_type for q in total_q if q.knowledge_point_id == kp.id}
            if types and types != {kp.question_type}:
                bad.append((kp.name, types))
        if bad:
            raise SystemExit(f"题型不一致：{bad}")


if __name__ == "__main__":
    seed()
