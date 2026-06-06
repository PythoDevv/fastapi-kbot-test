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
