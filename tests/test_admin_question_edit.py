"""Regression tests for editing individual questions in every bot."""

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


class FakeSession:
    def __init__(self) -> None:
        self.flush_calls = 0

    async def flush(self) -> None:
        self.flush_calls += 1


class FakeQuiz:
    def __init__(self, *, active: bool = False) -> None:
        self.active = active
        self.question = SimpleNamespace(
            id=42,
            text="Eski savol",
            correct_answer="To'g'ri",
            answer_2="Xato 1",
            answer_3="Xato 2",
            answer_4="Xato 3",
        )

    async def count_active_sessions_with_question(self, question_id: int) -> int:
        return int(self.active)

    async def get(self, question_id: int):
        return self.question if question_id == self.question.id else None


class FakeState:
    def __init__(self, data=None) -> None:
        self.data = dict(data or {})
        self.state = None

    async def set_state(self, state) -> None:
        self.state = state

    async def update_data(self, **values) -> None:
        self.data.update(values)

    async def get_data(self) -> dict:
        return dict(self.data)

    async def clear(self) -> None:
        self.data.clear()
        self.state = None


class FakeMessage:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.answers = []
        self.edits = []

    async def answer(self, text, **kwargs) -> None:
        self.answers.append((text, kwargs))

    async def edit_text(self, text, **kwargs) -> None:
        self.edits.append((text, kwargs))


class FakeCallback:
    def __init__(self) -> None:
        self.message = FakeMessage()
        self.answers = []

    async def answer(self, text=None, **kwargs) -> None:
        self.answers.append((text, kwargs))


class RecordingAdminService:
    def __init__(self) -> None:
        self.updates = []

    async def update_question(self, question_id: int, **values) -> bool:
        self.updates.append((question_id, values))
        return True


def _make_service(bot_name: str, *, active: bool = False):
    module = importlib.import_module(f"bots.{bot_name}.services.admin_service")
    session = FakeSession()
    service = module.AdminService(session)
    service.quiz = FakeQuiz(active=active)
    return service, service.quiz.question, session


@pytest.mark.parametrize("bot_name", BOTS)
def test_question_row_has_short_text_edit_and_delete_buttons(bot_name):
    inline = importlib.import_module(f"bots.{bot_name}.keyboards.inline")
    question = SimpleNamespace(
        id=42,
        text="Bu juda uzun savol matni bo'lib tugmada qisqa ko'rinishi kerak",
    )

    keyboard = inline.questions_list_keyboard([question])
    row = keyboard.inline_keyboard[0]

    assert [button.callback_data for button in row] == [
        "q_noop",
        "q_edit:42:0",
        "q_del:42:0",
    ]
    assert row[0].text.startswith("1. ")
    assert len(row[0].text) <= 30


@pytest.mark.parametrize("bot_name", BOTS)
def test_update_question_text_keeps_existing_answers(bot_name):
    service, question, session = _make_service(bot_name)

    updated = asyncio.run(service.update_question(42, text="Yangi savol"))

    assert updated is True
    assert question.text == "Yangi savol"
    assert question.correct_answer == "To'g'ri"
    assert [question.answer_2, question.answer_3, question.answer_4] == [
        "Xato 1",
        "Xato 2",
        "Xato 3",
    ]
    assert session.flush_calls == 1


@pytest.mark.parametrize("bot_name", BOTS)
def test_update_question_can_replace_all_answers(bot_name):
    service, question, session = _make_service(bot_name)

    updated = asyncio.run(
        service.update_question(
            42,
            text="Yangi savol",
            correct="Yangi to'g'ri",
            wrong_1="Yangi xato 1",
            wrong_2="Yangi xato 2",
            wrong_3="Yangi xato 3",
        )
    )

    assert updated is True
    assert question.text == "Yangi savol"
    assert question.correct_answer == "Yangi to'g'ri"
    assert [question.answer_2, question.answer_3, question.answer_4] == [
        "Yangi xato 1",
        "Yangi xato 2",
        "Yangi xato 3",
    ]
    assert session.flush_calls == 1


@pytest.mark.parametrize("bot_name", BOTS)
def test_update_question_is_blocked_during_an_active_test(bot_name):
    service, question, session = _make_service(bot_name, active=True)
    errors = importlib.import_module(f"bots.{bot_name}.exceptions")

    with pytest.raises(errors.QuestionDeletionBlockedError):
        asyncio.run(service.update_question(42, text="Yangi savol"))

    assert question.text == "Eski savol"
    assert session.flush_calls == 0


@pytest.mark.parametrize("bot_name", BOTS)
def test_question_edit_flow_is_registered(bot_name):
    states = importlib.import_module(f"bots.{bot_name}.states")
    inline = importlib.import_module(f"bots.{bot_name}.keyboards.inline")
    handlers = importlib.import_module(f"bots.{bot_name}.handlers.admin.questions")

    assert hasattr(states, "AdminQuestionEditStates")
    assert callable(handlers.start_edit_question)
    assert callable(handlers.choose_edit_answers)
    assert callable(handlers.keep_existing_answers)

    callbacks = {
        button.callback_data
        for row in inline.question_answers_edit_choice_keyboard().inline_keyboard
        for button in row
    }
    assert callbacks == {"q_edit_answers_yes", "q_edit_answers_no"}


@pytest.mark.parametrize("bot_name", BOTS)
def test_no_answer_choice_updates_only_question_text(bot_name, monkeypatch):
    handlers = importlib.import_module(f"bots.{bot_name}.handlers.admin.questions")
    service = RecordingAdminService()
    monkeypatch.setattr(handlers, "AdminService", lambda _session: service)
    state = FakeState({"edit_question_id": 42, "edit_text": "Yangi savol"})
    callback = FakeCallback()

    asyncio.run(handlers.keep_existing_answers(callback, state, session=None))

    assert service.updates == [(42, {"text": "Yangi savol"})]
    assert state.data == {}


@pytest.mark.parametrize("bot_name", BOTS)
def test_yes_answer_choice_collects_and_updates_every_answer(bot_name, monkeypatch):
    handlers = importlib.import_module(f"bots.{bot_name}.handlers.admin.questions")
    states = importlib.import_module(f"bots.{bot_name}.states")
    service = RecordingAdminService()
    monkeypatch.setattr(handlers, "AdminService", lambda _session: service)
    state = FakeState({"edit_question_id": 42, "edit_text": "Yangi savol"})
    callback = FakeCallback()
    message = FakeMessage()

    async def run_flow() -> None:
        await handlers.choose_edit_answers(callback, state)
        assert state.state == states.AdminQuestionEditStates.waiting_correct

        message.text = "Yangi to'g'ri"
        await handlers.edit_question_correct(message, state)
        message.text = "Yangi xato 1"
        await handlers.edit_question_wrong_1(message, state)
        message.text = "Yangi xato 2"
        await handlers.edit_question_wrong_2(message, state)
        message.text = "Yangi xato 3"
        await handlers.edit_question_wrong_3(message, state, session=None)

    asyncio.run(run_flow())

    assert service.updates == [
        (
            42,
            {
                "text": "Yangi savol",
                "correct": "Yangi to'g'ri",
                "wrong_1": "Yangi xato 1",
                "wrong_2": "Yangi xato 2",
                "wrong_3": "Yangi xato 3",
            },
        )
    ]
    assert state.data == {}
