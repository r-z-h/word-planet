from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

QuestionType = Literal["letter", "word", "spelling", "listening", "pronunciation"]


class RegisterRequest(BaseModel):
    account: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=72)
    nickname: str = Field(min_length=1, max_length=64)


class LoginRequest(BaseModel):
    account: str
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


class QuestionNextResponse(BaseModel):
    question: QuestionOut


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


class AnswerSubmitResponse(BaseModel):
    is_correct: bool
    correct_answer: str
    progress_advanced: bool
    current_knowledge_point: KnowledgePointOut | None = None
    new_badges: list[str] = []
    duplicated: bool = False


class TodayTaskOut(BaseModel):
    is_completed: bool
    correct_count: int
    target_count: int


class ProgressResponse(BaseModel):
    level: str | None
    current_knowledge_point: KnowledgePointOut | None
    completed_knowledge_points: list[str]
    today_task: TodayTaskOut
    kp_total: int = 0
    kp_done: int = 0


class StreakResponse(BaseModel):
    current_streak: int
    longest_streak: int
    last_study_date: date | None


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


class PronunciationNextResponse(BaseModel):
    question: PronunciationQuestionOut


class PronunciationResultRequest(BaseModel):
    word_id: str
    is_correct: bool
    idempotency_key: str = Field(min_length=8, max_length=64)


class PronunciationResultResponse(BaseModel):
    recorded: bool
    progress_advanced: bool = False
    new_badges: list[str] = []
    duplicated: bool = False


class PushSubscribeRequest(BaseModel):
    subscription: dict


class OkResponse(BaseModel):
    ok: bool = True


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
