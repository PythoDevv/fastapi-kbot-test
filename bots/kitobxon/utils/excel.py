import io
from typing import Any

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def export_users_to_excel(users: list) -> io.BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Foydalanuvchilar"

    headers = [
        "№", "Telegram ID", "FIO", "Username",
        "Telefon", "Ball", "Referallar",
        "Test yechganmi", "Ro'yxatdan o'tgan sana",
    ]
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(fill_type="solid", fgColor="2E4057")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws.row_dimensions[1].height = 30
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    for row_idx, user in enumerate(users, 2):
        ws.cell(row=row_idx, column=1, value=row_idx - 1)
        ws.cell(row=row_idx, column=2, value=user.telegram_id)
        ws.cell(row=row_idx, column=3, value=user.fio or "")
        ws.cell(row=row_idx, column=4, value=f"@{user.username}" if user.username else "")
        ws.cell(row=row_idx, column=5, value=user.mobile_number or "")
        ws.cell(row=row_idx, column=6, value=user.score)
        ws.cell(row=row_idx, column=7, value=user.referrals_count)
        ws.cell(row=row_idx, column=8, value="Ha" if user.test_solved else "Yo'q")
        ws.cell(
            row=row_idx,
            column=9,
            value=user.created_at.strftime("%Y-%m-%d %H:%M") if user.created_at else "",
        )

    col_widths = [5, 14, 30, 20, 16, 8, 10, 12, 18]
    for col_idx, width in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def export_questions_to_excel(questions: list) -> io.BytesIO:
    """Export questions to Excel with columns: Question, Correct, Wrong1, Wrong2, Wrong3"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Savollar"

    headers = ["Savol", "To'g'ri javob", "Noto'g'ri 1", "Noto'g'ri 2", "Noto'g'ri 3"]
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(fill_type="solid", fgColor="2E4057")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws.row_dimensions[1].height = 30
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    for row_idx, q in enumerate(questions, 2):
        ws.cell(row=row_idx, column=1, value=q.text or "")
        ws.cell(row=row_idx, column=2, value=q.correct_answer or "")
        ws.cell(row=row_idx, column=3, value=q.answer_2 or "")
        ws.cell(row=row_idx, column=4, value=q.answer_3 or "")
        ws.cell(row=row_idx, column=5, value=q.answer_4 or "")

    col_widths = [50, 30, 30, 30, 30]
    for col_idx, width in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def import_questions_from_excel(path: str) -> list[dict[str, Any]]:
    """
    Excel format:
    Column A: Question text
    Column B: Correct answer
    Column C: Wrong answer 1
    Column D: Wrong answer 2
    Column E: Wrong answer 3
    """
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    questions = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        text, correct, w1, w2, w3 = (str(v).strip() if v else "" for v in (row[:5] + ("",) * 5)[:5])
        if not text or not correct:
            continue
        questions.append(
            dict(
                text=text,
                correct=correct,
                wrong_1=w1 or "—",
                wrong_2=w2 or "—",
                wrong_3=w3 or "—",
            )
        )
    return questions


def import_users_from_excel(path: str) -> list[dict[str, Any]]:
    """
    Excel format for importing users:
    Column A: Telegram ID
    Column B: FIO
    Column C: Username
    Column D: Mobile number
    Column E: Referrals count
    Column F: Score
    Column G: Referred by (user ID)
    """
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    users = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or not row[0]:  # Skip empty rows
            continue
        try:
            telegram_id = int(row[0]) if row[0] else None
            fio = str(row[1]).strip() if row[1] else None
            username = str(row[2]).strip() if row[2] else None
            mobile_number = str(row[3]).strip() if row[3] else None
            referrals_count = int(row[4]) if row[4] else 0
            score = int(row[5]) if row[5] else 0
            referred_by = int(row[6]) if row[6] else None

            if not telegram_id:
                continue

            users.append({
                "telegram_id": telegram_id,
                "fio": fio,
                "username": username,
                "mobile_number": mobile_number,
                "referrals_count": referrals_count,
                "score": score,
                "referred_by": referred_by,
            })
        except (ValueError, IndexError):
            continue
    return users
