import enum


class QuizType(str, enum.Enum):
    WEB = "web"
    QUIZ = "quiz"
    WEBAPP = "webapp"


BOT_NAME = "manfaadli_konkurs_bot"
TABLE_PREFIX = "manfaadli_konkurs_bot_"
