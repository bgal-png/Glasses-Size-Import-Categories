"""The import file: no header row, column A global ID, column B ";"-joined IDs."""

from io import BytesIO

from openpyxl import Workbook


def export_filename(today):
    return f"Sizes-{today:%y%m%d}-import.xlsx"


def build_workbook(rows):
    workbook = Workbook()
    sheet = workbook.active
    for global_id, category_ids in rows:
        sheet.append([global_id, category_ids])
    return workbook


def to_bytes(rows):
    buffer = BytesIO()
    build_workbook(rows).save(buffer)
    return buffer.getvalue()
