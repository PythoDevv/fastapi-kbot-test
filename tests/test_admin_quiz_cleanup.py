"""Regression tests for admin quiz cleanup actions shared by all bots."""

import asyncio
import importlib
from types import SimpleNamespace

import pytest


BOTS = [
    "Barakali_tanlov_bot",
    "Kitobmillatbot",
    "Manfaadli_konkurs_bot",
    "Millatchiroqlaribot",
    "kitobxon",
]


class FakeUsers:
    def __init__(self) -> None:
        self.updated_values = None

    async def update_all(self, **values) -> None:
        self.updated_values = values


class FakeQuiz:
    def __init__(self) -> None:
        self.has_active_session = True
        self.deleted_questions = []
        self.delete_all_sessions_calls = 0
        self.delete_all_questions_calls = 0

    async def delete_all_sessions(self) -> int:
        self.delete_all_sessions_calls += 1
        self.has_active_session = False
        return 3

    async def count_active_sessions_with_question(self, question_id: int) -> int:
        return int(self.has_active_session)

    async def count_active_sessions(self) -> int:
        return int(self.has_active_session)

    async def get(self, question_id: int):
        return SimpleNamespace(id=question_id)

    async def delete(self, question) -> None:
        self.deleted_questions.append(question.id)

    async def delete_all_questions(self) -> int:
        self.delete_all_questions_calls += 1
        return 7


def _make_service(bot_name: str):
    module = importlib.import_module(f"bots.{bot_name}.services.admin_service")
    service = module.AdminService(session=None)
    service.users = FakeUsers()
    service.quiz = FakeQuiz()
    return service


@pytest.mark.parametrize("bot_name", BOTS)
def test_clear_all_solved_removes_sessions_then_question_can_be_deleted(bot_name):
    service = _make_service(bot_name)

    async def run_scenario() -> int:
        deleted_sessions = await service.clear_all_solved()
        await service.delete_question(42)
        return deleted_sessions

    deleted_sessions = asyncio.run(run_scenario())

    assert deleted_sessions == 3
    assert service.users.updated_values == {"test_solved": False}
    assert service.quiz.delete_all_sessions_calls == 1
    assert service.quiz.deleted_questions == [42]


@pytest.mark.parametrize("bot_name", BOTS)
def test_delete_all_questions_uses_repository_and_returns_count(bot_name):
    service = _make_service(bot_name)

    async def run_scenario() -> int:
        await service.clear_all_solved()
        return await service.delete_all_questions()

    deleted_count = asyncio.run(run_scenario())

    assert deleted_count == 7
    assert service.quiz.delete_all_questions_calls == 1


@pytest.mark.parametrize("bot_name", BOTS)
def test_delete_all_questions_is_blocked_while_a_test_is_active(bot_name):
    service = _make_service(bot_name)
    errors = importlib.import_module(f"bots.{bot_name}.exceptions")

    with pytest.raises(errors.QuestionDeletionBlockedError):
        asyncio.run(service.delete_all_questions())

    assert service.quiz.delete_all_questions_calls == 0


@pytest.mark.parametrize("bot_name", BOTS)
def test_questions_keyboard_has_confirmed_delete_all_action(bot_name):
    inline = importlib.import_module(f"bots.{bot_name}.keyboards.inline")
    question = SimpleNamespace(id=1, text="Test savoli")

    list_keyboard = inline.questions_list_keyboard([question])
    list_callbacks = {
        button.callback_data
        for row in list_keyboard.inline_keyboard
        for button in row
    }
    confirm_keyboard = inline.questions_delete_all_confirm_keyboard()
    confirm_callbacks = {
        button.callback_data
        for row in confirm_keyboard.inline_keyboard
        for button in row
    }

    assert "q_delete_all" in list_callbacks
    assert confirm_callbacks == {"q_delete_all_confirm", "q_delete_all_cancel"}
