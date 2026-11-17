"""系统问答助手 · A 层（Phase A）：确定性「规则/状态」问答。

把这份文件放进 RAG 的框架里看，会更清楚它在干嘛：

    标准 RAG：  知识源 → 切分 → 向量化 → 存向量库 → 检索 top-k → LLM 生成 → 引用
    Phase A ：  知识源(DB/常量) ──────────────► 「查询函数」 ──► 「模板拼装」 ─► sources

- 意图识别  ≈ 查询理解（把用户的话映射到一个"检索意图"）
- 查询函数  ≈ 检索（这里不是向量召回，而是精确查库/常量）
- 模板拼装  ≈ 生成（这里不是 LLM，而是把查询结果填进固定句式）
- sources   ≈ 引用（给用户一个"去哪儿看"的链接）

**Phase A 故意不引入向量和 LLM**：因为"怎么解锁/我还差几枚"这类答案本质是数据库里的
实时数值，向量检索既检索不到"你个人还差几枚"，还会让数字漂移。等 Phase B 才需要语义
检索（FAQ 语义匹配）和 LLM（把说明文字组织成人话），那时替换的只是"检索/生成"两步。

接口约定（与 Phase B 保持一致，避免以后重写）：
    answer(db, user, question, context) -> {
        "answer": str,
        "mode": "rule" | "faq" | "refuse",
        "sources": [{"title": str, "path": str}],
        "context": {...},          # 前端带回，用于多轮
        "suggestions": [str],      # 下一句可点的候选，降低多轮门槛
    }
"""

from __future__ import annotations

import datetime
import json
import logging
import re
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (
    Achievement,
    Attempt,
    Badge,
    DailyTask,
    KnowledgePoint,
    PlanetMedal,
    Question,
    Streak,
    User,
)
from . import llm
from .attempts import MASTERY_STREAK, local_date_of, local_today
from .lesson import (
    SETS_REQUIRED,
    completed_set_numbers,
    current_set_no,
    kp_set_numbers,
    level_gate,
    level_kps,
    resolve_current_kp,
)
from .rewards import (
    FLOWERS_PER_STAR,
    STARS_PER_MEDAL,
    count_flowers,
    get_set_progress,
    planet_medal_count,
)

logger = logging.getLogger("word_planet.help")

# 与 routers/practice.py 的 PRACTICE_COOLDOWN_MINUTES 保持一致（Phase A 先就近声明）
PRACTICE_COOLDOWN_MINUTES = 10

DEFAULT_SUGGESTIONS = [
    "怎么做能力测试？",
    "徽章怎么解锁？",
    "花、星、徽记怎么换？",
    "今天任务完成了吗？",
]

_UNMATCHED_LOG = Path(__file__).resolve().parents[3] / "data" / "logs" / "help_unmatched.jsonl"


def _log_unmatched(question: str) -> None:
    """记录未命中的问题（仅问题文本，不记账号），用于指导补充知识库。"""
    try:
        _UNMATCHED_LOG.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                "question": (question or "")[:500],
            },
            ensure_ascii=False,
        )
        with _UNMATCHED_LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:  # noqa: BLE001 — 日志失败不能影响问答
        logger.exception("log unmatched question failed")


# ---------------------------------------------------------------- 来源（引用）

def _src(title: str, path: str) -> dict:
    return {"title": title, "path": path}


# ---------------------------------------------------------------- 意图识别

def detect_intent(question: str) -> str | None:
    """把一句话映射到一个意图。顺序很重要（先窄后宽、先具体后笼统）。"""
    q = question or ""

    # 测试"怎么算过"要先于"怎么做"，因为两者都含"测试"
    if re.search(r"(能力测试|水平测试|测试)", q) and re.search(
        r"(通过|算过|几题|多少题|8|八|及格|分数)", q
    ):
        return "test_pass"
    # 题量类（"简单拼写有多少题"）——放在 test_pass 之后，避免抢"能力测试几题"
    if re.search(r"((多少|几)\s*(道|个)?\s*题(目)?|题量|有多少题|一共多少题)", q):
        return "kp_question_count"
    # 站点总览类（"一共有几个难度模块""几个星球"）
    if re.search(r"(几个|多少|一共).{0,8}(难度|等级|模块|星球|知识点|关卡)|难度.{0,4}(几|多少)|几个\s*(难度|模块|星球)", q):
        return "site_overview"
    if re.search(
        r"(能力测试|水平测试|怎么.*测|如何.*测|测一测|解锁下一级|怎么.*升级|如何.*升级|怎样才能.*级|升级)",
        q,
    ):
        return "capability_test"
    # 兑换要先于徽记判断，否则"花/星/徽记怎么换"会被星球徽记吃掉
    if re.search(r"(兑换|怎么换|换星|换徽记|花.*星|星.*徽记|换.*徽记)", q):
        return "exchange"
    if re.search(r"(成就|徽章)", q):
        return "achievement_badge"
    if re.search(r"(徽记|星球)", q):
        return "planet_medal"
    if re.search(r"(今天.*(任务|学|完成)|每日任务|任务完成|今天.*做)", q):
        return "daily_task"
    if re.search(r"(几级|等级|进度|做到哪|当前.*(级|进度)|几套)", q):
        return "progress"
    if re.search(r"(错题|补花|连对|掌握|几次|错.*花)", q):
        return "mastery"
    return None


# ---------------------------------------------------------------- 小工具

def _badge_condition_text(condition_type: str, v: int) -> str:
    """徽章条件文案。与 routers/achievement.py 的 cond_text 保持一致。"""
    return {
        "streak": f"连续学习 ≥{v} 天",
        "answer_correct": f"累计答对 ≥{v} 题",
        "complete_kp": "完成第 1 个知识点",
        "complete_level": "完成当前等级全部知识点",
        "perfect_set": "有一套 15 题全对",
        "level_test_pass": "通过 1 次能力测试",
        "active_days": f"累计学习 ≥{v} 天",
        "daily_correct": f"单日答对 ≥{v} 题",
        "planet_medals": f"单个星球集齐 {v} 枚徽记",
        "perfect_sets": f"累计 {v} 套全对",
        "wrong_cleared": f"错题本待练清零（历史错题 ≥{v}）",
        "refill": f"错题本补花 ≥{v} 次",
        "consecutive_correct": f"连续答对 ≥{v} 题",
        "ultimate": "所有星球都拿到过花 + 字母表已完成",
    }.get(condition_type, "")


def _count_correct_total(db: Session, user_id) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(Attempt)
            .where(Attempt.user_id == user_id, Attempt.is_correct.is_(True))
        ).scalar_one()
    )


def _active_days(db: Session, user_id) -> int:
    return int(
        db.execute(
            select(func.count(func.distinct(local_date_of(Attempt.created_at)))).where(
                Attempt.user_id == user_id
            )
        ).scalar_one()
    )


def _today_correct(db: Session, user_id, today) -> int:
    return int(
        db.execute(
            select(func.count())
            .select_from(Attempt)
            .where(
                Attempt.user_id == user_id,
                Attempt.is_correct.is_(True),
                local_date_of(Attempt.created_at) == today,
            )
        ).scalar_one()
    )


def _max_planet_medals(db: Session, user_id) -> int:
    v = db.execute(
        select(func.coalesce(func.max(PlanetMedal.medals), 0)).where(
            PlanetMedal.user_id == user_id
        )
    ).scalar_one()
    return int(v)


def _badge_progress(db: Session, user: User, badge: Badge):
    """能算的徽章给出 (当前值, 目标值)，算不了的返回 None（只报条件）。"""
    t, v = badge.condition_type, int(badge.condition_value or 0)
    if t == "streak":
        s = db.get(Streak, user.id)
        return ((s.current_streak if s else 0), v)
    if t == "answer_correct":
        return (_count_correct_total(db, user.id), v)
    if t == "active_days":
        return (_active_days(db, user.id), v)
    if t == "daily_correct":
        return (_today_correct(db, user.id, local_today(db)), v)
    if t == "planet_medals":
        return (_max_planet_medals(db, user.id), v)
    return None


def _find_kp(db: Session, user: User, question: str, context: dict) -> KnowledgePoint | None:
    """按名字/徽记名找星球；找不到用上一轮实体；再不行用当前星球。"""
    for kp in db.execute(select(KnowledgePoint)).scalars():
        if (kp.name and kp.name in question) or (kp.medal_name and kp.medal_name in question):
            return kp
    last = context.get("last_kp_id")
    if last:
        uid = _as_uuid(last)
        if uid is not None:
            kp = db.get(KnowledgePoint, uid)
            if kp is not None:
                return kp
    if user.has_tested:
        return resolve_current_kp(db, user)
    return None


def _as_uuid(value):
    import uuid

    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------- 追问判定（多轮守卫）
# 只有"像追问"的短句才允许继承上一轮意图；否则一律当"不认识"，避免拿旧答案顶新问题。

# 追问判定：只认"明显是省略/指代上一句"的短句，避免把普通新问题（如"今天星期几"）误当追问
_FOLLOWUP_START = re.compile(r"^\s*(那|这(个|里|样)?|它|还有|还差|剩下|然后|另外|再)")
_FOLLOWUP_END = re.compile(r"(呢|吗)\s*[？?]?\s*$")


def _mentions_entity(db: Session, q: str) -> bool:
    """句子里是否出现了具体的星球/徽章名 —— 出现就是新话题，不算追问。"""
    for kp in db.execute(select(KnowledgePoint)).scalars():
        if kp.name and kp.name in q:
            return True
        if kp.medal_name and kp.medal_name in q:
            return True
    for b in db.execute(select(Badge)).scalars():
        if b.name and b.name in q:
            return True
    return False


def _is_followup(db: Session, q: str, context: dict) -> bool:
    if not context.get("last_intent"):
        return False
    q2 = (q or "").strip()
    if not q2 or len(q2) > 14:
        return False
    if not (_FOLLOWUP_START.search(q2) or _FOLLOWUP_END.search(q2)):
        return False
    if _mentions_entity(db, q2):
        return False
    return True


# ---------------------------------------------------------------- 各意图的答案

def _ans_capability(db: Session, user: User) -> dict:
    if not user.has_tested:
        return _res(
            "你还没做水平测试哦。先完成水平测试，系统会给你定级，之后才谈「解锁下一级 / 能力测试」。",
            sources=[_src("首页 · 水平测试", "/test")],
        )
    gate = level_gate(db, user)
    lines = []
    for item in gate["knowledge_points"]:
        if not item.get("counts_for_gate"):
            continue
        name = item["name"]
        if item.get("meets_gate"):
            lines.append(f"✅ {name}：已达标")
        elif item.get("gate_mode") == "completion":
            lines.append(f"⬜ {name}：还没完成（需要 15 题全部答对）")
        else:
            need = int(item.get("gate_required") or 0) - int(item.get("medals") or 0)
            lines.append(
                f"⬜ {name}：还差 {max(need, 0)} 枚徽记"
                f"（需 {item.get('gate_required')} 枚，已有 {item.get('medals')} 枚）"
            )
    if gate["ready"]:
        answer = "本级门槛已全部达标！你可以去做能力测试了：10 题答对 8 题及以上就通过。"
    else:
        answer = "能力测试要本级每个计入门槛的星球都达标。你当前的进度：\n" + "\n".join(lines)
    return _res(answer, sources=[_src("首页 · 能力测试", "/home")])


def _ans_test_pass() -> dict:
    return _res(
        "能力测试一共 10 道题，答对 8 道及以上就通过。通过后会解锁下一等级，"
        "再由你选择升级还是留在本级。",
        sources=[_src("能力测试", "/level-test")],
    )


def _ans_site_overview(db: Session) -> dict:
    """站点总览：几个难度 / 几个星球 / 各自多少套多少题。"""
    kps = db.execute(
        select(KnowledgePoint).order_by(KnowledgePoint.level, KnowledgePoint.sort_order)
    ).scalars().all()
    by = {}
    for kp in kps:
        by.setdefault(kp.level, []).append(kp)
    level_names = {"L1": "L1 小学低年级", "L2": "L2 小学高年级", "L3": "L3 初中"}
    parts = []
    for lv in ["L1", "L2", "L3"]:
        arr = by.get(lv, [])
        if not arr:
            continue
        seg = []
        for kp in arr:
            total = int(
                db.execute(
                    select(func.count()).select_from(Question).where(
                        Question.knowledge_point_id == kp.id
                    )
                ).scalar_one()
            )
            sets = len(kp_set_numbers(db, kp.id))
            pure = (not kp.produces_flowers) and kp.question_type != "picquiz"
            seg.append(f"{kp.name}（{sets}套/{total}题{'，纯练' if pure else ''}）")
        parts.append(f"{level_names[lv]}：{'、'.join(seg)}")
    total_q = int(db.execute(select(func.count()).select_from(Question)).scalar_one())
    answer = (
        f"本站共 3 个难度等级、{len(kps)} 个学习星球：\n" + "\n".join(parts) +
        f"\n全站共 {total_q} 道题；除“看图猜词”按主题分套（题数不等）外，其它星球基本每套 15 题。"
    )
    return _res(answer, sources=[_src("首页 · 星球地图", "/home")])


def _ans_exchange() -> dict:
    return _res(
        f"三层奖励这样换：答对 1 题得 1 朵花 🌸；{FLOWERS_PER_STAR} 朵花换 1 颗星 ⭐；"
        f"{STARS_PER_MEDAL} 颗星换 1 个星球徽记。全程手动兑换，去「🧾 兑换」页操作。"
        f"一套 15 题全对 = 15 花 = 5 星 = 1 徽记。"
        "（例外：看图猜词不产花、不记星，一套全部答对直接得 1 枚徽记。）",
        sources=[_src("兑换页", "/exchange")],
    )


def _ans_planet_medal(db: Session, user: User, question: str, context: dict) -> dict:
    kp = _find_kp(db, user, question, context)
    if kp is None:
        return _res(
            "你想问哪个星球的徽记？它们分别是：破壳蛋、小熊、铅笔、小鸟、水晶球、耳机、眼力侠。",
            suggestions=["破壳蛋徽记怎么拿？", "小熊徽记怎么拿？", "小鸟徽记怎么拿？"],
        )
    new_ctx = {"last_intent": "planet_medal", "last_kp_id": str(kp.id)}

    if kp.gate_mode == "completion" or ((not kp.produces_flowers) and kp.question_type != "picquiz"):
        answer = f"「{kp.name}」是纯练星球，不产花也不产徽记，只有「已完成/未完成」；15 题全对算完成。"
        return _res(answer, sources=[_src(kp.name, "/home")], context=new_ctx)

    have = planet_medal_count(db, user.id, kp.id)
    medal = kp.medal_name or "徽记"
    if kp.question_type == "picquiz":
        answer = (
            f"「{kp.name}」的徽记是{medal}：**一套全部答对 = 1 枚徽记**（不产花、不记星）。"
            f"它共有 {len(kp_set_numbers(db, kp.id))} 套；要解锁下一级需要 {kp.gate_required} 枚，你现在有 {have} 枚。"
        )
        return _res(answer, sources=[_src(kp.name, "/home")], context=new_ctx,
                    suggestions=["那我还差几枚？", "L2 怎么解锁？"])
    if not kp.counts_for_gate:
        answer = (
            f"「{kp.name}」的徽记是{medal}，共需 {len(kp_set_numbers(db, kp.id))} 枚可拿满；"
            f"它不参与升级门槛。你现在有 {have} 枚。"
        )
    else:
        need = int(kp.gate_required or 0) - have
        answer = (
            f"「{kp.name}」的徽记是{medal}。要解锁下一级，本级需要 {kp.gate_required} 枚，"
            f"你现在有 {have} 枚，还差 {max(need, 0)} 枚。"
            f"1 枚 = 该星球 1 套 15 题全对（15 花 → 5 星 → 1 徽记）。"
        )
    return _res(
        answer,
        sources=[_src(kp.name, "/exchange")],
        context=new_ctx,
        suggestions=["那我还差几枚？", "花星徽记怎么换？"],
    )


def _ans_achievement(db: Session, user: User, question: str, context: dict) -> dict:
    badges = db.execute(select(Badge).order_by(Badge.code)).scalars().all()
    found = None
    for b in badges:
        if (b.name and b.name in question) or (b.code and b.code in question):
            found = b
            break
    if found is None and context.get("last_badge_code"):
        found = db.execute(
            select(Badge).where(Badge.code == context["last_badge_code"])
        ).scalar_one_or_none()

    if found is None:
        names = [b.name for b in badges]
        answer = (
            "「成就徽章」是荣誉墙上的奖励（区别于用来解锁的「星球徽记」）。"
            "你想问哪一个？比如：" + "、".join(names[:6]) + "。"
        )
        return _res(answer, sources=[_src("徽章墙", "/achievements")], suggestions=names[:6])

    cond = _badge_condition_text(found.condition_type, int(found.condition_value or 0))
    earned = db.execute(
        select(Achievement).where(
            Achievement.user_id == user.id, Achievement.badge_id == found.id
        )
    ).scalar_one_or_none()
    text = f"「{found.name}」条件：{cond}。"
    if earned is not None:
        text += "你已经拿到啦 🎉"
    else:
        prog = _badge_progress(db, user, found)
        if prog is not None:
            cur, target = prog
            text += f"你当前 {cur}，还差 {max(target - cur, 0)}。"
    return _res(
        text,
        sources=[_src("徽章墙", "/achievements")],
        context={"last_intent": "achievement_badge", "last_badge_code": found.code},
    )


def _ans_daily_task(db: Session, user: User) -> dict:
    if not user.has_tested:
        return _res(
            "你还没做水平测试，暂时没有每日任务。先完成水平测试就能开始学习啦。",
            sources=[_src("首页", "/test")],
        )
    kp = resolve_current_kp(db, user)
    if kp is None:
        return _res("你还没有可学习的内容。")
    set_no = current_set_no(db, user.id, kp.id)
    total_sets = len(kp_set_numbers(db, kp.id))
    today = local_today(db)
    task = db.execute(
        select(DailyTask).where(DailyTask.user_id == user.id, DailyTask.task_date == today)
    ).scalar_one_or_none()
    correct_count = _today_correct(db, user.id, today)

    if set_no is None:
        return _res(
            f"「{kp.name}」的 {total_sets} 套都做完啦，今天可以去别的星球或做错题练习。",
            sources=[_src("首页", "/home")],
        )

    set_total, set_done = _set_counts(db, user, kp.id, set_no)
    target = max(set_total - set_done, 0)
    done_flag = bool(task.is_completed) if task else False
    head = "✅ 今天的任务已经完成啦！" if done_flag else "今天的任务是把当前这一套做完。"
    answer = (
        f"{head}当前在「{kp.name}」第 {set_no}/{total_sets} 套，"
        f"这一套共 {set_total} 题，已做 {set_done} 题，还剩 {target} 题。"
        f"今天已答对 {correct_count} 题。"
    )
    return _res(answer, sources=[_src("首页", "/home")])


def _ans_progress(db: Session, user: User) -> dict:
    if not user.has_tested:
        return _res(
            "你还没做水平测试，所以还没有等级和进度。先完成水平测试吧。",
            sources=[_src("首页", "/test")],
        )
    kp = resolve_current_kp(db, user)
    if kp is None:
        return _res("你还没有可学习的内容。")
    set_no = current_set_no(db, user.id, kp.id)
    total_sets = len(kp_set_numbers(db, kp.id))
    done = len(completed_set_numbers(db, user.id, kp.id))
    answer = (
        f"你现在是 {user.level} 级（已解锁到 {user.max_level or user.level}）。"
        f"正在学「{kp.name}」，已完成 {done}/{total_sets} 套；"
        f"当前套：{('第 ' + str(set_no) + ' 套') if set_no else '全部完成'}。"
    )
    return _res(answer, sources=[_src("首页", "/home")])


def _ans_kp_question_count(db: Session, user: User, question: str, context: dict) -> dict:
    kp = _find_kp(db, user, question, context)
    if kp is None:
        names = [
            k.name
            for k in db.execute(
                select(KnowledgePoint).order_by(KnowledgePoint.level, KnowledgePoint.sort_order)
            ).scalars()
        ]
        return _res(
            "你想问哪个星球的题量？比如：" + "、".join(names[:6]) + "。",
            suggestions=[f"{n}有多少题？" for n in names[:4]],
        )
    total = int(
        db.execute(
            select(func.count())
            .select_from(Question)
            .where(Question.knowledge_point_id == kp.id)
        ).scalar_one()
    )
    sets = len(kp_set_numbers(db, kp.id))
    answer = f"「{kp.name}」一共 {sets} 套、约 {total} 道题（每套 15 题）。"
    if user.has_tested and user.level == kp.level:
        done = len(completed_set_numbers(db, user.id, kp.id))
        answer += f"你已经完成 {done} 套。"
    return _res(
        answer,
        sources=[_src(kp.name, "/home")],
        context={"last_intent": "kp_question_count", "last_kp_id": str(kp.id)},
    )


def _ans_mastery() -> dict:
    return _res(
        f"错题在错题本里连续答对 {MASTERY_STREAK} 次，就补回这道题的 1 朵花并移出错题本；"
        f"同一道题两次答对要间隔至少 {PRACTICE_COOLDOWN_MINUTES} 分钟才算一次连对（防止连点抢记）。",
        sources=[_src("错题本", "/wrong")],
    )


def _set_counts(db: Session, user: User, kp_id, set_no: int) -> tuple[int, int]:
    total = int(
        db.execute(
            select(func.count())
            .select_from(Question)
            .where(Question.knowledge_point_id == kp_id, Question.set_no == set_no)
        ).scalar_one()
    )
    qids = select(Question.id).where(
        Question.knowledge_point_id == kp_id, Question.set_no == set_no
    )
    done = int(
        db.execute(
            select(func.count(func.distinct(Attempt.question_id))).where(
                Attempt.user_id == user.id,
                Attempt.question_id.in_(qids),
                Attempt.question_type != "practice",
            )
        ).scalar_one()
    )
    return total, done


# ---------------------------------------------------------------- 组装返回

def _res(answer, *, mode="rule", sources=None, context=None, suggestions=None) -> dict:
    return {
        "answer": answer,
        "mode": mode,
        "sources": sources or [],
        "context": context or {},
        "suggestions": suggestions or [],
    }


def _answer_impl(db: Session, user: User, question: str, context: dict | None = None) -> dict:
    """入口：意图识别 → 分发查询 → 模板答案。对应 RAG 的「检索 + 生成」两段。"""
    context = dict(context or {})
    q = (question or "").strip()
    if not q:
        return _res(
            "你想问点什么？我可以回答关于本站的问题，比如怎么解锁、怎么兑换、今天任务有没有完成。",
            mode="refuse",
            suggestions=DEFAULT_SUGGESTIONS,
        )

    intent = detect_intent(q)
    # 多轮：只有"像追问"的短句才继承上一轮意图；但 faq/kb 不是可分发意图，
    # 继承它们会落空 → 这里不放行，交给下面的知识库检索按"新问题"再查一遍。
    if intent is None and _is_followup(db, q, context):
        inherited = context.get("last_intent")
        if inherited and inherited not in ("faq", "kb"):
            intent = inherited

    if intent is None:
        # A 层没命中 → 独立 RAG 引擎（rag_kb 语料）：混合检索 +（可选）LLM 多片段综合
        try:
            import rag_engine

            chat_fn = llm.chat if (settings.help_llm_enabled and llm.is_configured()) else None
            res = rag_engine.query(q, chat=chat_fn)
        except Exception:  # noqa: BLE001 — 引擎异常不影响可用，降级为拒答
            logger.exception("rag_engine query failed")
            res = None
        if res:
            return _res(
                res["answer"],
                mode="faq",
                sources=[_src(s["title"], s["path"]) for s in res["sources"]],
                context={"last_intent": "kb"},
                suggestions=[],
            )
        _log_unmatched(q)
        return _res(
            "抱歉！该问题不在提问范围内\n"
            "我主要能回答关于本站使用的问题，比如怎么解锁、怎么兑换、今天任务完成了没。你要问的是哪一种？",
            mode="refuse",
            suggestions=DEFAULT_SUGGESTIONS,
        )

    if intent == "test_pass":
        result = _ans_test_pass()
        result["context"] = {**result["context"], "last_intent": intent}
        return result
    if intent == "capability_test":
        result = _ans_capability(db, user)
    elif intent == "exchange":
        result = _ans_exchange()
    elif intent == "kp_question_count":
        result = _ans_kp_question_count(db, user, q, context)
    elif intent == "site_overview":
        result = _ans_site_overview(db)
    elif intent == "planet_medal":
        result = _ans_planet_medal(db, user, q, context)
    elif intent == "achievement_badge":
        result = _ans_achievement(db, user, q, context)
    elif intent == "daily_task":
        result = _ans_daily_task(db, user)
    elif intent == "progress":
        result = _ans_progress(db, user)
    elif intent == "mastery":
        result = _ans_mastery()
    else:  # 理论到不了
        result = _res("我没太明白，换个说法试试？", mode="refuse", suggestions=DEFAULT_SUGGESTIONS)

    # 保底把 last_intent 写回 context，供下一轮追问使用
    result["context"] = {**result.get("context", {}), "last_intent": intent}
    return result


def answer(db: Session, user: User, question: str, context: dict | None = None) -> dict:
    """对外入口。包一层异常兜底：任何查询/取数抛错都降级为友好提示，绝不 500。"""
    try:
        return _answer_impl(db, user, question, context)
    except Exception:  # noqa: BLE001 — 兜底：不让助手因单条查询异常拖垮页面
        logger.exception("help.answer failed: question=%r", question)
        return _res(
            "抱歉，我这边暂时出了点小状况，没查到结果。你可以稍后再问，或直接到对应页面查看。",
            mode="refuse",
            suggestions=DEFAULT_SUGGESTIONS,
        )
