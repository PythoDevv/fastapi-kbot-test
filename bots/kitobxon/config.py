import enum


class QuizType(str, enum.Enum):
    WEB = "web"
    QUIZ = "quiz"
    WEBAPP = "webapp"


BOT_NAME = "kitobxon"
TABLE_PREFIX = "kitobxon_"
