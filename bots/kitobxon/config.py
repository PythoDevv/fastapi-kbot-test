import enum


class QuizType(str, enum.Enum):
    WEB = "web"
    QUIZ = "quiz"


BOT_NAME = "kitobxon"
TABLE_PREFIX = "kitobxon_"
