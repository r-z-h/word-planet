from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

QuestionType = Literal["letter", "word", "spelling", "listening", "pronunciation"]


class RegisterRequest(BaseModel):
    account: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=72)
    nickname: str = Field(min_length=1, max_length=64)
    agreed_terms: bool = True
    captcha_token: str | None = None
    captcha_code: str | None = None


class LoginRequest(BaseModel):
    account: str
    password: str
    captcha_token: str | None = None
    captcha_code: str | None = None


class CaptchaOut(BaseModel):
    token: str
    question: str


class DeleteAccountRequest(BaseModel):
    password: str


class TokenResponse(BaseModel):
    user_id: str
    access_token: str
    token_type: str = "bearer"
    has_tested: bool
    level: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    has_tested: bool
    level: str | None = None


class MeResponse(BaseModel):
    user_id: str
    nickname: str
    level: str | None
    has_tested: bool


class QuestionOut(BaseModel):
    id: str
    question_type: str
    stem: str
    options: dict | None = None
    knowledge_point_id: str | None = None
    # 拼写题：打乱后的字母砖（答案字母各 1 块 + 4 干扰，可重复点）
    tiles: list[str] | None = None


class QuestionNextResponse(BaseModel):
    question: QuestionOut
    set_no: int = 1
    set_total: int = 15
    set_done: int = 0
    knowledge_point_name: str = ""


class TestQuestionOut(BaseModel):
    id: str
    question_type: str
    stem: str
    options: dict | None = None


class TestStartResponse(BaseModel):
    question: TestQuestionOut
    question_index: int


class TestAnswerRequest(BaseModel):
    question_id: str
    answer: str


class TestAnswerResponse(BaseModel):
    is_finished: bool
    next_question: TestQuestionOut | None = None
    level: str | None = None


class AnswerSubmitRequest(BaseModel):
    question_id: str
    answer: str
    idempotency_key: str = Field(min_length=8, max_length=64)


class KnowledgePointOut(BaseModel):
    id: str
    level: str
    name: str
    question_type: str


class WordSenseOut(BaseModel):
    text: str
    source: str


class AnswerWordOut(BaseModel):
    """答错时前端要展示的单词信息（正确答案 + 音标 + 全部义项）。"""

    word: str
    phonetic: str | None = None
    senses: list[WordSenseOut] = []
    definition_en: str | None = None


class AnswerSubmitResponse(BaseModel):
    is_correct: bool
    correct_answer: str
    progress_advanced: bool
    current_knowledge_point: KnowledgePointOut | None = None
    new_badges: list[str] = []
    duplicated: bool = False
    answer_text: str | None = None
    word: AnswerWordOut | None = None


class TodayTaskOut(BaseModel):
    is_completed: bool
    correct_count: int
    target_count: int


class ProgressResponse(BaseModel):
    level: str | None
    max_level: str | None = None
    current_knowledge_point: KnowledgePointOut | None
    completed_knowledge_points: list[str]
    today_task: TodayTaskOut
    kp_total: int = 0
    kp_done: int = 0
    set_no: int | None = None
    completed_sets: int = 0
    total_sets: int = 0
    # --- 三层奖励（当前套） ---
    set_flowers: int = 0          # 本套已得花（0-15）
    set_stars: int = 0            # 本套已兑星（0-5）
    set_medals: int = 0           # 本套已产徽记（0/1）
    exchangeable_stars: int = 0   # 当前可兑星数
    can_exchange_medal: bool = False
    planet_medals: int = 0        # 当前星球累计徽记


class StreakResponse(BaseModel):
    current_streak: int
    longest_streak: int
    last_study_date: date | None


# ---------------------------------------------------------------- 星球地图

class MapPlanetOut(BaseModel):
    id: str
    name: str
    level: str
    question_type: str
    total_sets: int = 0
    completed_sets: int = 0
    current_set: int | None = None
    medals: int = 0          # 该星球已获得徽记
    max_medals: int = 0      # 该星球徽记上限（= 套数）
    pure: bool = False       # 纯练星球（不产奖励）
    is_complete: bool = False  # 纯练星球「已完成」
    locked: bool = False
    is_current: bool = False


class MapResponse(BaseModel):
    level: str | None = None
    max_level: str | None = None
    current_planet_id: str | None = None
    planets: list[MapPlanetOut] = []
    today_flowers: int = 0
    today_stars: int = 0
    total_flowers: int = 0
    # 底部 CTA 条用的真实统计
    today_attempts: int = 0
    today_correct: int = 0
    today_max_combo: int = 0
    week_counts: list[int] = []  # 本周一→周日 每天作答数
    gate_ready: bool = False     # 本级是否已达能力测试门槛
    next_level: str | None = None


# ---------------------------------------------------------------- 三层奖励

class RewardSummaryOut(BaseModel):
    knowledge_point_id: str
    set_no: int
    flowers: int = 0
    stars: int = 0
    medals: int = 0
    exchangeable_stars: int = 0
    can_exchange_medal: bool = False
    planet_medals: int = 0
    set_completed: bool = False


class RewardExchangeRequest(BaseModel):
    knowledge_point_id: str | None = None
    set_no: int | None = None
    from_kind: Literal["flower", "star"]
    amount: int = Field(default=1, ge=1, le=5)
    idempotency_key: str = Field(min_length=8, max_length=64)


class RewardExchangeResponse(BaseModel):
    ok: bool
    summary: RewardSummaryOut


class WrongItem(BaseModel):
    question_id: str
    stem: str
    knowledge_point_name: str
    error_count: int
    is_mastered: bool
    explanation: str | None = None


class WrongListResponse(BaseModel):
    items: list[WrongItem]


class AchievementItem(BaseModel):
    badge_id: str
    code: str
    name: str
    earned_at: datetime


class AchievementResponse(BaseModel):
    items: list[AchievementItem]
    medals: list['MedalItem'] = []


class MedalItem(BaseModel):
    knowledge_point_id: str
    name: str
    level: str
    medals: int
    max_medals: int


AchievementResponse.model_rebuild()


class DailyAttempt(BaseModel):
    date: date
    count: int


class ReportWrongItem(BaseModel):
    stem: str
    error_count: int
    is_mastered: bool


class ReportResponse(BaseModel):
    level: str | None
    completed_knowledge_points: int
    total_knowledge_points: int
    last_7_days_completed: int
    daily_attempts: list[DailyAttempt]
    wrong_questions: list[ReportWrongItem]


class PronunciationQuestionOut(BaseModel):
    id: str
    stem: str
    answer: str
    phonetic: str | None = None


class PronunciationNextResponse(BaseModel):
    question: PronunciationQuestionOut
    set_no: int = 1
    set_total: int = 15
    set_done: int = 0
    knowledge_point_name: str = ""


class PronunciationResultRequest(BaseModel):
    word_id: str
    is_correct: bool
    idempotency_key: str = Field(min_length=8, max_length=64)


class PronunciationResultResponse(BaseModel):
    recorded: bool
    progress_advanced: bool = False
    new_badges: list[str] = []
    duplicated: bool = False
    answer_text: str | None = None
    word: AnswerWordOut | None = None


class PushSubscribeRequest(BaseModel):
    subscription: dict


class OkResponse(BaseModel):
    ok: bool = True


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=72)


# ---------------- 错题本练习 ----------------


class PracticeQuestionOut(BaseModel):
    id: str
    question_type: str
    stem: str
    options: dict | None = None
    explanation: str | None = None
    error_count: int = 1
    consecutive_correct: int = 0
    knowledge_point_name: str = ""


class PracticeNextResponse(BaseModel):
    question: PracticeQuestionOut
    remaining: int = 0


class PracticeResultRequest(BaseModel):
    question_id: str
    answer: str
    idempotency_key: str = Field(min_length=8, max_length=64)


class PracticeResultResponse(BaseModel):
    is_correct: bool
    correct_answer: str
    explanation: str | None = None
    consecutive_correct: int = 0
    mastered: bool = False
    duplicated: bool = False


# ---------------- 模块 / 套 / 能力测试 ----------------


class KpProgressOut(BaseModel):
    id: str
    name: str
    question_type: str
    counts_for_gate: bool
    total_sets: int
    completed_sets: int
    current_set: int | None = None
    meets_gate: bool = False


class LessonOverview(BaseModel):
    level: str | None
    max_level: str | None
    required_sets: int
    knowledge_points: list[KpProgressOut]
    gate_ready: bool
    can_test: bool
    next_level: str | None = None
    switchable_levels: list[str] = []


class SelectKpRequest(BaseModel):
    knowledge_point_id: str


class SwitchLevelRequest(BaseModel):
    level: str


class LevelTestStartResponse(BaseModel):
    question: TestQuestionOut
    index: int


class LevelTestAnswerRequest(BaseModel):
    question_id: str
    answer: str


class LevelTestAnswerResponse(BaseModel):
    is_finished: bool
    score: int = 0
    total: int = 10
    passed: bool | None = None
    next_level: str | None = None


class LevelTestChooseRequest(BaseModel):
    go_next: bool


class LevelTestChooseResponse(BaseModel):
    level: str
    max_level: str
    knowledge_point: KnowledgePointOut | None = None


# ---------------- 词典 ----------------


class WordItemOut(BaseModel):
    id: str
    word: str
    phonetic: str | None = None
    level: str
    grade: str
    is_phrase: bool
    senses: list[WordSenseOut]
    definition_en: str | None = None
    learned: bool = False
    has_wrong: bool = False


class WordListResponse(BaseModel):
    level: str
    total: int
    items: list[WordItemOut]
    has_more: bool
