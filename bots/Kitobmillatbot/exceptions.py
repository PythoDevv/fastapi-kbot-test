class KitobxonError(Exception):
    """Base error for kitobxon bot domain."""


class UserNotFoundError(KitobxonError):
    def __init__(self, telegram_id: int):
        super().__init__(f"User {telegram_id} not found")
        self.telegram_id = telegram_id


class UserNotRegisteredError(KitobxonError):
    pass


class QuizAlreadyStartedError(KitobxonError):
    pass


class QuizNotActiveError(KitobxonError):
    pass


class QuizFinishedError(KitobxonError):
    pass


class QuizWaitingError(KitobxonError):
    pass


class SubscriptionRequiredError(KitobxonError):
    pass


class NoQuestionsError(KitobxonError):
    pass


class AlreadySolvedError(KitobxonError):
    pass


class QuestionDeletionBlockedError(KitobxonError):
    def __init__(self, question_id: int, active_sessions_count: int):
        super().__init__(
            f"Question {question_id} is used in {active_sessions_count} active session(s)"
        )
        self.question_id = question_id
        self.active_sessions_count = active_sessions_count
