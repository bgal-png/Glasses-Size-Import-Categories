"""The import file: no header row, column A global ID, column B ";"-joined IDs."""

from io import BytesIO

from openpyxl import Workbook


def export_filename(today):
    """The import filename for the given date."""
    return f"Sizes-{today:%y%m%d}-import.xlsx"


def build_workbook(rows):
    """Build the import workbook from rows; kept separate from `to_bytes` as a testing seam."""
    workbook = Workbook()
    sheet = workbook.active
    for global_id, category_ids in rows:
        sheet.append([global_id, category_ids])
    return workbook


def to_bytes(rows):
    """Serialise rows for Streamlit's download button."""
    buffer = BytesIO()
    build_workbook(rows).save(buffer)
    return buffer.getvalue()
