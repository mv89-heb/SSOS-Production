from types import SimpleNamespace

from app.services.import_validation_integrity import (
    DEFAULT_IMPORT_UNIT,
    DUPLICATE_ERROR_CODE,
    DUPLICATE_ERROR_MESSAGE,
    find_duplicate_groups,
    find_duplicate_row_numbers,
)
from app.models.import_mapping import TARGET_PRODUCT_NAME, TARGET_SUPPLIER_NAME


def _row(number, product, supplier):
    return SimpleNamespace(row_number=number, raw_values=[product, supplier])


def _columns():
    return {
        0: SimpleNamespace(column_index=0, final_target=TARGET_PRODUCT_NAME),
        1: SimpleNamespace(column_index=1, final_target=TARGET_SUPPLIER_NAME),
    }


def test_duplicate_product_supplier_marks_all_rows():
    rows = [
        _row(2, "אסאדו", "אריאל"),
        _row(3, "אסאדו", "אריאל"),
        _row(4, "חזה עוף", "אריאל"),
        _row(5, "אסאדו", "אריאל "),
    ]
    assert find_duplicate_row_numbers(rows, _columns()) == {2, 3, 5}


def test_duplicate_groups_isolate_rows_per_product_supplier():
    rows = [
        _row(4, "אסאדו", "ספק א"),
        _row(5, "אסאדו", "ספק א"),
        _row(7, "שניצל", "ספק א"),
        _row(8, "שניצל", "ספק א"),
        _row(9, "שניצל", "ספק א"),
        _row(11, "אסאדו", "ספק ב"),
        _row(12, "אסאדו", "ספק ב"),
    ]

    groups = find_duplicate_groups(rows, _columns())

    assert len(groups) == 3
    assert sorted(groups[("אסאדו", "ספק א")]) == [4, 5]
    assert sorted(groups[("שניצל", "ספק א")]) == [7, 8, 9]
    assert sorted(groups[("אסאדו", "ספק ב")]) == [11, 12]


def test_duplicate_group_rows_do_not_leak_between_errors():
    rows = [
        _row(4, "אסאדו", "ספק א"),
        _row(5, "אסאדו", "ספק א"),
        _row(7, "שניצל", "ספק א"),
        _row(8, "שניצל", "ספק א"),
    ]

    groups = find_duplicate_groups(rows, _columns())

    asado_rows = groups[("אסאדו", "ספק א")]
    schnitzel_rows = groups[("שניצל", "ספק א")]

    asado_message = f"{DUPLICATE_ERROR_MESSAGE} (שורות: {', '.join(map(str, asado_rows))})"
    schnitzel_message = f"{DUPLICATE_ERROR_MESSAGE} (שורות: {', '.join(map(str, schnitzel_rows))})"

    assert "4, 5" in asado_message
    assert "7, 8" not in asado_message
    assert "7, 8" in schnitzel_message
    assert "4, 5" not in schnitzel_message


def test_resolved_supplier_id_catches_aliases_for_same_supplier():
    rows = [_row(2, "אסאדו", "אריאל"), _row(3, "אסאדו", "אריאל שיווק בשר")]
    assert find_duplicate_row_numbers(
        rows,
        _columns(),
        resolved_supplier_by_row={2: 17, 3: 17},
    ) == {2, 3}


def test_different_suppliers_are_not_duplicate():
    rows = [_row(2, "אסאדו", "אריאל"), _row(3, "אסאדו", "תנובה")]
    assert find_duplicate_row_numbers(rows, _columns()) == set()


def test_integrity_contract_constants():
    assert DEFAULT_IMPORT_UNIT == 'ק"ג'
    assert DUPLICATE_ERROR_CODE == "CRITICAL_ERROR"
    assert "כל השורות המעורבות ידולגו" in DUPLICATE_ERROR_MESSAGE
