import enum


class QuizType(str, enum.Enum):
    WEB = "web"
    QUIZ = "quiz"
    WEBAPP = "webapp"


BOT_NAME = "kitobxonmillattbot"
TABLE_PREFIX = "kitobxonmillattbot_"
