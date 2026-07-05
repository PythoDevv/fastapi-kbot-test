from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass(frozen=True)
class ChannelSnapshot:
    id: int
    channel_id: int
    channel_name: str
    channel_link: str | None
    skip_check: bool


@dataclass(frozen=True)
class ZayafkaChannelSnapshot:
    id: int
    channel_id: int
    name: str
    link: str | None
    sequence: int


class RuntimeCache:
    """Small in-memory TTL cache for hot runtime data."""

    _channels_ttl = 60.0
    _zayafka_ttl = 60.0
    _question_ids_ttl = 300.0
    _member_ttl = 120.0

    def __init__(self) -> None:
        self._channels_entry: tuple[float, list[ChannelSnapshot]] | None = None
        self._zayafka_entry: tuple[float, list[ZayafkaChannelSnapshot]] | None = None
        self._question_ids_entry: tuple[float, list[int]] | None = None
        self._member_entries: dict[tuple[int, int], float] = {}

    def _get_valid(self, entry):
        if entry is None:
            return None
        expires_at, value = entry
        if expires_at <= monotonic():
            return None
        return value

    def get_active_channels(self) -> list[ChannelSnapshot] | None:
        return self._get_valid(self._channels_entry)

    def set_active_channels(self, channels: list[ChannelSnapshot]) -> None:
        self._channels_entry = (monotonic() + self._channels_ttl, channels)

    def invalidate_active_channels(self) -> None:
        self._channels_entry = None

    def get_zayafka_channels(self) -> list[ZayafkaChannelSnapshot] | None:
        return self._get_valid(self._zayafka_entry)

    def set_zayafka_channels(
        self, channels: list[ZayafkaChannelSnapshot]
    ) -> None:
        self._zayafka_entry = (monotonic() + self._zayafka_ttl, channels)

    def invalidate_zayafka_channels(self) -> None:
        self._zayafka_entry = None

    def get_question_ids(self) -> list[int] | None:
        return self._get_valid(self._question_ids_entry)

    def set_question_ids(self, question_ids: list[int]) -> None:
        self._question_ids_entry = (monotonic() + self._question_ids_ttl, question_ids)

    def invalidate_question_ids(self) -> None:
        self._question_ids_entry = None

    def has_recent_member(self, chat_id: int, telegram_id: int) -> bool:
        expires_at = self._member_entries.get((chat_id, telegram_id))
        if expires_at is None:
            return False
        if expires_at <= monotonic():
            self._member_entries.pop((chat_id, telegram_id), None)
            return False
        return True

    def remember_member(self, chat_id: int, telegram_id: int) -> None:
        self._member_entries[(chat_id, telegram_id)] = monotonic() + self._member_ttl

    def forget_member(self, chat_id: int, telegram_id: int) -> None:
        self._member_entries.pop((chat_id, telegram_id), None)


runtime_cache = RuntimeCache()
