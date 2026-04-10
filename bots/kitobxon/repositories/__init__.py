from bots.kitobxon.repositories.channel_repo import (
    ChannelRepository,
    ZayafkaRepository,
)
from bots.kitobxon.repositories.content_repo import (
    BookRepository,
    ContentRepository,
    ScoreLogRepository,
)
from bots.kitobxon.repositories.quiz_repo import QuizRepository
from bots.kitobxon.repositories.user_repo import UserRepository

__all__ = [
    "ChannelRepository",
    "ZayafkaRepository",
    "BookRepository",
    "ContentRepository",
    "ScoreLogRepository",
    "QuizRepository",
    "UserRepository",
]
