import enum


class QuizType(str, enum.Enum):
    WEB = "web"
    QUIZ = "quiz"
    WEBAPP = "webapp"


BOT_NAME = "kitobmillatbot"
TABLE_PREFIX = "kitobmillatbot_"
