from app.services.import_supplier_detection import install_supplier_detection_patch
from app.services.import_analysis_service import WorkbookAnalyzer


def test_mixed_supplier_column_is_flagged_ambiguous_not_majority_voted():
    install_supplier_detection_patch()
    analyzer = WorkbookAnalyzer({"ספק א": (1, "ספק א"), "ספק ב": (2, "ספק ב")})
    columns = [{
        "index": 0,
        "header": "שם ספק",
        "detected_type": "SUPPLIER",
        "sample_values": ["ספק א", "ספק א", "ספק ב"],
    }]

    result = analyzer._detect_suppliers(columns)

    assert len(result) == 1
    assert result[0]["ambiguous"] is True
    assert result[0]["matched_supplier_id"] is None
    assert result[0]["detected_supplier_name"] is None
    assert result[0]["candidate_supplier_names"] == ["ספק א", "ספק ב"]


def test_single_supplier_value_is_matched_exactly():
    install_supplier_detection_patch()
    analyzer = WorkbookAnalyzer({"ספק א": (1, "ספק א")})
    columns = [{
        "index": 0,
        "header": "שם ספק",
        "detected_type": "SUPPLIER",
        "sample_values": ["ספק א", "ספק א", "ספק א"],
    }]

    result = analyzer._detect_suppliers(columns)

    assert len(result) == 1
    assert result[0]["ambiguous"] is False
    assert result[0]["matched_supplier_id"] == 1
    assert result[0]["detected_supplier_name"] == "ספק א"
