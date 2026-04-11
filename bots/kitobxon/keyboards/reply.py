from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

REMOVE = ReplyKeyboardRemove()


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💠 Do'stlarni taklif qilish")],
            [
                KeyboardButton(text="Test savollarini ishlash 🧑‍💻"),
                KeyboardButton(text="🌟 Natijalar"),
            ],
            [
                KeyboardButton(text="📝 Tanlov shartlari"),
                KeyboardButton(text="Tanlov kitoblari 📚"),
            ],
            [KeyboardButton(text="Viktorina sovg'alari 🎁")],
            [KeyboardButton(text="Ismni o'zgartirish ✏️")],
        ],
        resize_keyboard=True,
    )


def phone_request() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)],
            [KeyboardButton(text="Bekor qilish")],
        ],
        resize_keyboard=True,
    )


def cancel_only() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Bekor qilish")]],
        resize_keyboard=True,
    )


def admin_panel() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Statistika"),
                KeyboardButton(text="👥 Foydalanuvchilar"),
            ],
            [
                KeyboardButton(text="📢 Broadcast"),
                KeyboardButton(text="❓ Savollar"),
            ],
            [
                KeyboardButton(text="📡 Kanallar"),
                KeyboardButton(text="🔗 Zayafka kanallar"),
            ],
            [
                KeyboardButton(text="⚙️ Test sozlamalari"),
                KeyboardButton(text="📥 Excel yuklash"),
            ],
            [
                KeyboardButton(text="👥 Adminlar"),
                KeyboardButton(text="Userlarni import 📤"),
            ],
            [
                KeyboardButton(text="📝 Kontentlar"),
            ],
            [
                KeyboardButton(text="🏠 Asosiy menyu"),
            ],
        ],
        resize_keyboard=True,
    )


def broadcast_confirm() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Yuborish"), KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )


def confirm_action() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Qo'shish"), KeyboardButton(text="❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )
