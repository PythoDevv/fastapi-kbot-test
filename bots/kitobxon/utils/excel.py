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
