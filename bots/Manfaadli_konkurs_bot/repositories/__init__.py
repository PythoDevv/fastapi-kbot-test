from bots.Manfaadli_konkurs_bot.repositories.channel_repo import (
    ChannelRepository,
    ZayafkaRepository,
)
from bots.Manfaadli_konkurs_bot.repositories.content_repo import (
    BookRepository,
    ContentRepository,
    ScoreLogRepository,
)
from bots.Manfaadli_konkurs_bot.repositories.quiz_repo import QuizRepository
from bots.Manfaadli_konkurs_bot.repositories.user_repo import UserRepository

__all__ = [
    "ChannelRepository",
    "ZayafkaRepository",
    "BookRepository",
    "ContentRepository",
    "ScoreLogRepository",
    "QuizRepository",
    "UserRepository",
]
