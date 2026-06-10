class KitobxonError(Exception):
    """Base error for kitobxon bot domain."""


class UserNotFoundError(KitobxonError):
    def __init__(self, telegram_id: int):
        super().__init__(f"User {telegram_id} not found")
        self.telegram_id = telegram_id


class UserNotRegisteredError(KitobxonError):
    def __init__(self, message: str = "Avval ro'yxatdan o'ting."):
        super().__init__(message)


class QuizAlreadyStartedError(KitobxonError):
    def __init__(self, message: str = "Sizda faol test mavjud."):
        super().__init__(message)


class QuizNotActiveError(KitobxonError):
    def __init__(self, message: str = "Test hozircha faol emas. Iltimos keyinroq urinib ko'ring."):
        super().__init__(message)


class QuizFinishedError(KitobxonError):
    def __init__(self, message: str = "Test yakunlandi."):
        super().__init__(message)


class QuizWaitingError(KitobxonError):
    def __init__(self, message: str = "Test hali boshlanmagan. Kuting."):
        super().__init__(message)


class SubscriptionRequiredError(KitobxonError):
    def __init__(self, message: str = "Avval kanallarga obuna bo'ling."):
        super().__init__(message)


class NoQuestionsError(KitobxonError):
    def __init__(self, message: str = "Hozircha savollar mavjud emas. Admin savol qo'shishi kerak."):
        super().__init__(message)


class AlreadySolvedError(KitobxonError):
    def __init__(self, message: str = "Siz testni allaqachon yakunladingiz."):
        super().__init__(message)


class QuestionDeletionBlockedError(KitobxonError):
    def __init__(self, question_id: int, active_sessions_count: int):
        super().__init__(
            f"Question {question_id} is used in {active_sessions_count} active session(s)"
        )
        self.question_id = question_id
        self.active_sessions_count = active_sessions_count
