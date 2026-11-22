import csv
from io import StringIO

from django.http import HttpResponse


def csv_response(*, filename, columns, rows):
    buffer = StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow([header for _, header in columns])
    for row in rows:
        writer.writerow(
            [_safe_csv_value(row.get(field, "")) for field, _ in columns]
        )
    response = HttpResponse(
        buffer.getvalue(),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _safe_csv_value(value):
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{value}"
    return value
