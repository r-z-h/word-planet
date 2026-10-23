"""初始化种子数据：7 个知识点 × 15 题 + 4 个徽章 + 每题解析。

幂等：按 (level, sort_order) 判知识点，按 (knowledge_point_id, stem) 判题目；
已存在的题会补写缺失的 explanation。
内容按人教版（L1/L2 小学，L3 八年级上）范围编写。
"""

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Attempt, Badge, KnowledgePoint, Question

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
    ("书包", "schoolbag"),
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

# (英文句子, 正确词, 干扰项, 中文意思)
LISTENING = [
    ("My favourite fruit is an apple.", "apple", ["banana", "orange", "grape"], "我最喜欢的水果是苹果。"),
    ("I go to school by bus every day.", "school", ["park", "zoo", "library"], "我每天坐公交车去学校。"),
    ("My mother is a teacher.", "teacher", ["doctor", "driver", "farmer"], "我妈妈是一名老师。"),
    ("There is a cat under the table.", "cat", ["dog", "bird", "fish"], "桌子下面有一只猫。"),
    ("I would like a glass of milk.", "milk", ["juice", "water", "tea"], "我想要一杯牛奶。"),
    ("We have an English class on Monday.", "English", ["math", "music", "art"], "我们星期一有英语课。"),
    ("It is raining outside today.", "raining", ["snowing", "sunny", "windy"], "今天外面在下雨。"),
    ("My father works in a hospital.", "hospital", ["school", "bank", "factory"], "我爸爸在医院工作。"),
    ("She likes playing the piano.", "piano", ["guitar", "violin", "drum"], "她喜欢弹钢琴。"),
    ("The train leaves at eight o'clock.", "train", ["bus", "plane", "ship"], "火车八点出发。"),
    ("I have two brothers and one sister.", "sister", ["aunt", "cousin", "uncle"], "我有两个兄弟和一个姐妹。"),
    ("We are going to the park this weekend.", "park", ["museum", "cinema", "market"], "这个周末我们要去公园。"),
    ("He is reading a book in the library.", "library", ["classroom", "office", "garden"], "他正在图书馆看书。"),
    ("Please open the window, it is hot.", "window", ["door", "box", "bag"], "请打开窗户，天气很热。"),
    ("My birthday is in September.", "September", ["October", "November", "December"], "我的生日在九月。"),
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

# 中文释义表，供解析使用
CN_OF_WORD = {en: cn for cn, en in GREETINGS + COMMON_WORDS + SPELLING_L2 + SPELLING_L3}


def spell_out(word: str) -> str:
    return " ".join(word)


def make_choice(stem, correct, wrongs, rot):
    options = list(wrongs)
    pos = rot % 4
    options.insert(pos, correct)
    return stem, {KEYS[i]: options[i] for i in range(4)}, KEYS[pos]


# ---------------------------------------------------------------- 题目构造


def build_letter_items():
    """返回 (stem, options, answer, explanation)"""
    items = []
    for i in range(1, 16):
        correct = chr(64 + i)
        wrongs = [chr(64 + ((i + d - 1) % 26) + 1) for d in (1, 2, 3)]
        stem, opts, ans = make_choice(f"字母表里第 {i} 个字母是哪个？", correct, wrongs, i - 1)
        explanation = (
            f"字母表从 A 开始按顺序排：A B C D E …，第 {i} 个是 {correct}。"
            f"{correct} 的大写是 {correct}，小写是 {correct.lower()}。"
            "记顺序时可以唱着念：A-B-C-D-E-F-G…"
        )
        items.append((stem, opts, ans, explanation))
    return items


def build_word_items(pairs, level_hint: str = ""):
    items = []
    english = [en for _cn, en in pairs]
    total = len(pairs)
    for idx, (cn, en) in enumerate(pairs):
        wrongs = [english[(idx + k) % total] for k in (1, 2, 3)]
        stem, opts, ans = make_choice(f"“{cn}”用英语怎么说？", en, wrongs, idx)
        if " " in en:
            explanation = f"“{cn}”的英文是 {en}，由 {len(en.split())} 个单词组成：{en}。"
        else:
            explanation = (
                f"“{cn}”的英文是 {en}，共 {len(en)} 个字母：{spell_out(en)}。"
            )
        items.append((stem, opts, ans, explanation))
    return items


def build_listening_items():
    items = []
    for idx, (sentence, correct, distractors, cn) in enumerate(LISTENING):
        stem, opts, ans = make_choice(sentence, correct, distractors, idx)
        explanation = (
            f"你听到的句子是「{sentence}」，意思是「{cn}」。"
            f"句子里出现的词是 {correct}。"
        )
        items.append((stem, opts, ans, explanation))
    return items


def build_spelling_items(pairs, level: str):
    items = []
    for cn, word in pairs:
        stem = f"“{cn}”怎么拼写？"
        explanation = (
            f"“{cn}”是 {word}，共 {len(word)} 个字母：{spell_out(word)}。"
            "拼的时候一小段一小段读出来，比一个字母一个字母背更好记。"
        )
        items.append((stem, None, word, explanation))
    return items


def build_pronunciation_items():
    items = []
    for word in PRONUNCIATION:
        cn = CN_OF_WORD.get(word, "")
        stem = word
        explanation = f"{word}（{cn}）。先听标准音，再跟读一遍，注意把每个音节读清楚。"
        items.append((stem, None, word, explanation))
    return items


# ---------------------------------------------------------------- 写入


def seed_badges(db) -> None:
    for code, name, ctype, value in BADGES:
        exists = db.execute(select(Badge).where(Badge.code == code)).scalar_one_or_none()
        if exists is None:
            db.add(Badge(code=code, name=name, condition_type=ctype, condition_value=value))
    db.flush()


def ensure_kp(db, level, name, qtype, order) -> KnowledgePoint:
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


def ensure_question(db, kp, qtype, stem, options, answer, difficulty, explanation):
    existing = db.execute(
        select(Question).where(Question.knowledge_point_id == kp.id, Question.stem == stem)
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            Question(
                knowledge_point_id=kp.id,
                question_type=qtype,
                stem=stem,
                options=options,
                answer=answer,
                difficulty=difficulty,
                explanation=explanation,
            )
        )
        return

    # 已存在：以 seed 为准同步内容，避免改了种子但库里还是旧数据
    if existing.options != options:
        existing.options = options
    if existing.answer != answer:
        existing.answer = answer
    if existing.difficulty != difficulty:
        existing.difficulty = difficulty
    if existing.explanation != explanation:
        existing.explanation = explanation


def prune_stale(db, kp, expected_stems) -> None:
    """删掉该知识点下已经不在种子里的题（没有作答记录时）。"""
    stale = db.execute(
        select(Question).where(
            Question.knowledge_point_id == kp.id, Question.stem.notin_(expected_stems)
        )
    ).scalars().all()
    for q in stale:
        used = db.execute(
            select(Attempt.id).where(Attempt.question_id == q.id).limit(1)
        ).first()
        if used:
            print(f"  跳过删除（已有作答记录）：{q.stem[:40]}")
            continue
        db.delete(q)
        print(f"  已删除旧题：{q.stem[:40]}")


def seed() -> None:
    with SessionLocal() as db:
        seed_badges(db)

        kps = {}
        for level, name, qtype, order in KP_DEFS:
            kps[(level, order)] = ensure_kp(db, level, name, qtype, order)

        def add_all(kp, qtype, items, explanation_index=3):
            for item in items:
                stem, opts, ans = item[0], item[1], item[2]
                explanation = item[explanation_index]
                ensure_question(
                    db, kp, qtype, stem, opts, ans, DIFFICULTY[kp.level], explanation
                )
            prune_stale(db, kp, [item[0] for item in items])

        add_all(kps[("L1", 1)], "letter", build_letter_items())
        add_all(kps[("L1", 2)], "word", build_word_items(GREETINGS))
        add_all(kps[("L2", 1)], "word", build_word_items(COMMON_WORDS))
        add_all(kps[("L3", 1)], "listening", build_listening_items())
        add_all(kps[("L2", 2)], "spelling", build_spelling_items(SPELLING_L2, "L2"))
        add_all(kps[("L3", 2)], "spelling", build_spelling_items(SPELLING_L3, "L3"))
        add_all(kps[("L2", 3)], "pronunciation", build_pronunciation_items())

        db.commit()

        total_kp = db.execute(select(KnowledgePoint)).scalars().all()
        total_q = db.execute(select(Question)).scalars().all()
        print(f"知识点 {len(total_kp)} 个，题目 {len(total_q)} 道")

        for kp in total_kp:
            count = len([q for q in total_q if q.knowledge_point_id == kp.id])
            print(f"  {kp.level} {kp.name}({kp.question_type}) -> {count} 题")

        missing = [q.stem for q in total_q if not q.explanation]
        if missing:
            print(f"警告：{len(missing)} 道题没有解析")

        bad = []
        for kp in total_kp:
            types = {q.question_type for q in total_q if q.knowledge_point_id == kp.id}
            if types and types != {kp.question_type}:
                bad.append((kp.name, types))
        if bad:
            raise SystemExit(f"题型不一致：{bad}")


if __name__ == "__main__":
    seed()
