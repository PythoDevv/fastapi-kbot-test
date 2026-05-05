from pydantic import BaseModel


class AuthRequest(BaseModel):
    init_data: str


class AuthResponse(BaseModel):
    token: str


class StartResponse(BaseModel):
    session_id: int
    question: "QuestionOut"
    total: int
    time_limit_seconds: int


class QuestionOut(BaseModel):
    index: int
    text: str
    options: list[str]


class AnswerRequest(BaseModel):
    session_id: int
    question_index: int
    selected_option: str | None  # None = timeout
    time_taken_ms: int


class AnswerResponse(BaseModel):
    is_correct: bool
    correct_answer: str
    score: int
    is_last: bool
    next_question: QuestionOut | None = None
    total_questions: int


StartResponse.model_rebuild()
