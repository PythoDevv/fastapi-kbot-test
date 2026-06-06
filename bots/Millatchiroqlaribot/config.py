import enum


class QuizType(str, enum.Enum):
    WEB = "web"
    QUIZ = "quiz"
    WEBAPP = "webapp"


BOT_NAME = "millatchiroqlaribot"
TABLE_PREFIX = "millatchiroqlaribot_"
