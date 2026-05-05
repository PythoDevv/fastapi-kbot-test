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
                KeyboardButton(text="Reklama jo'natish"),
                KeyboardButton(text="📩 Excel yuklash"),
            ],
            [
                KeyboardButton(text="📋 Taklif qilinganlar"),
                KeyboardButton(text="Javoblarni olish"),
            ],
            [
                KeyboardButton(text="Savol yuklash 📥"),
                KeyboardButton(text="Namuna olish 📄"),
            ],
            [
                KeyboardButton(text="Savolni export qilish 📤"),
                KeyboardButton(text="Userlarni import 📤"),
            ],
            [
                KeyboardButton(text="Kanallar 📈"),
                KeyboardButton(text="Test va kontent"),
            ],
            [
                KeyboardButton(text="👥 Adminlar"),
                KeyboardButton(text="🏠 Asosiy menyu"),
            ],
        ],
        resize_keyboard=True,
    )


def admin_channels_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Kanal +"),
                KeyboardButton(text="Kanal -"),
            ],
            [KeyboardButton(text="Kanallar 📈")],
            [
                KeyboardButton(text="Yopiq kanal qo'shish"),
                KeyboardButton(text="Yopiq kanal o'chirish"),
            ],
            [KeyboardButton(text="Yopiq kanallar ro'yxati")],
            [KeyboardButton(text="🔙 Admin panel")],
        ],
        resize_keyboard=True,
    )


def admin_content_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="Testni stop qilish"),
                KeyboardButton(text="Testni start qilish"),
            ],
            [
                KeyboardButton(text="Test stop posti"),
                KeyboardButton(text="Test stop postini o'chirish"),
            ],
            [
                KeyboardButton(text="Kitob qo'shish"),
                KeyboardButton(text="Kitoblarni o'chirish"),
            ],
            [
                KeyboardButton(text="Viktorina sovg'alari qo'shish"),
                KeyboardButton(text="Viktorina sovg'alari postini o'chirish"),
            ],
            [
                KeyboardButton(text="Do'stlarni taklif post"),
                KeyboardButton(text="Do'stlarni taklif postini o'chirish"),
            ],
            [KeyboardButton(text="Taklif postlarini tozalash")],
            [
                KeyboardButton(text="Tanlov shartlari post"),
                KeyboardButton(text="Tanlov shartlari postini o'chirish"),
            ],
            [KeyboardButton(text="⚙️ Test sozlamalari")],
            [KeyboardButton(text="🔙 Admin panel")],
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
