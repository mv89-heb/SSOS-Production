from types import SimpleNamespace

from app.services.import_validation_integrity import (
    DEFAULT_IMPORT_UNIT,
    DUPLICATE_ERROR_CODE,
    DUPLICATE_ERROR_MESSAGE,
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
