import enum


class QuizType(str, enum.Enum):
    WEB = "web"
    QUIZ = "quiz"
    WEBAPP = "webapp"


BOT_NAME = "barakali_tanlov_bot"
TABLE_PREFIX = "barakali_tanlov_bot_"
