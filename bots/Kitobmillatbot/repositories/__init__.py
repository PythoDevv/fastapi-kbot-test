from bots.Kitobmillatbot.repositories.channel_repo import (
    ChannelRepository,
    ZayafkaRepository,
)
from bots.Kitobmillatbot.repositories.content_repo import (
    BookRepository,
    ContentRepository,
    ScoreLogRepository,
)
from bots.Kitobmillatbot.repositories.quiz_repo import QuizRepository
from bots.Kitobmillatbot.repositories.user_repo import UserRepository

__all__ = [
    "ChannelRepository",
    "ZayafkaRepository",
    "BookRepository",
    "ContentRepository",
    "ScoreLogRepository",
    "QuizRepository",
    "UserRepository",
]
