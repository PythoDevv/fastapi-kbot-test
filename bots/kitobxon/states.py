from aiogram.fsm.state import State, StatesGroup


class AuthStates(StatesGroup):
    awaiting_name = State()
    awaiting_phone = State()
    changing_name = State()
    awaiting_how_did_find = State()


class QuizStates(StatesGroup):
    answering = State()


class BroadcastStates(StatesGroup):
    waiting_message = State()
    waiting_confirmation = State()


class AdminChannelStates(StatesGroup):
    waiting_name = State()
    waiting_link = State()
    waiting_channel_id = State()


class AdminZayafkaStates(StatesGroup):
    waiting_name = State()
    waiting_link = State()
    waiting_channel_id = State()


class AdminContentStates(StatesGroup):
    waiting_content_message = State()
    waiting_referral_link_choice = State()
    waiting_book_title = State()
    waiting_book_button_text = State()
    waiting_book_button_url = State()


class AdminQuestionStates(StatesGroup):
    waiting_text = State()
    waiting_correct = State()
    waiting_wrong_1 = State()
    waiting_wrong_2 = State()
    waiting_wrong_3 = State()
    waiting_confirmation = State()


class AdminQuestionImportStates(StatesGroup):
    waiting_file = State()


class AdminScoreStates(StatesGroup):
    waiting_user_id = State()
    waiting_new_score = State()
    waiting_reason = State()


class AdminUserSearchStates(StatesGroup):
    waiting_user_id = State()


class AdminAdminStates(StatesGroup):
    waiting_id = State()


class AdminImportStates(StatesGroup):
    waiting_users_file = State()


class AdminExportStates(StatesGroup):
    waiting_referral_id = State()
    waiting_answers_id = State()


class AdminReferralStates(StatesGroup):
    waiting_new_count = State()
    waiting_reason = State()


class AdminTestResetStates(StatesGroup):
    waiting_user_id = State()
