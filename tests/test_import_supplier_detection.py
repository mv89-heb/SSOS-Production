from app.services.import_analysis_service import WorkbookAnalyzer


def test_mixed_supplier_column_is_flagged_ambiguous_not_majority_voted():
    analyzer = WorkbookAnalyzer({"ספק א": (1, "ספק א"), "ספק ב": (2, "ספק ב")})
    columns = [{
        "index": 0, "header": "שם ספק", "detected_type": "SUPPLIER",
        "sample_values": ["ספק א", "ספק א", "ספק ב"], "group_label": None,
    }]

    result = analyzer._detect_suppliers(columns)

    assert len(result) == 1
    assert result[0]["ambiguous"] is True
    assert result[0]["matched_supplier_id"] is None
    assert result[0]["detected_supplier_name"] is None
    assert result[0]["candidate_supplier_names"] == ["ספק א", "ספק ב"]


def test_single_supplier_value_is_matched_exactly():
    analyzer = WorkbookAnalyzer({"ספק א": (1, "ספק א")})
    columns = [{
        "index": 0, "header": "שם ספק", "detected_type": "SUPPLIER",
        "sample_values": ["ספק א", "ספק א", "ספק א"], "group_label": None,
    }]

    result = analyzer._detect_suppliers(columns)

    assert len(result) == 1
    assert result[0]["ambiguous"] is False
    assert result[0]["matched_supplier_id"] == 1
    assert result[0]["detected_supplier_name"] == "ספק א"


def test_known_supplier_header_keeps_supplier_specific_column_semantics():
    analyzer = WorkbookAnalyzer({"ספק א": (1, "ספק א")})
    columns = [{
        "index": 0, "header": "ספק א", "detected_type": "SUPPLIER",
        "sample_values": ["10.00", "11.00", "9.50"], "group_label": None,
    }]

    result = analyzer._detect_suppliers(columns)

    assert len(result) == 1
    assert result[0]["matched_supplier_id"] == 1
    assert result[0]["ambiguous"] is False

def test_supplier_column_checks_values_beyond_the_first_five_samples():
    analyzer = WorkbookAnalyzer({"ספק א": (1, "ספק א"), "ספק ב": (2, "ספק ב")})
    rows = [[ "ספק א" ] for _ in range(18)]
    rows.append(["ספק ב"])

    columns = analyzer._detect_columns(["שם ספק"], rows, [])
    result = analyzer._detect_suppliers(columns)

    assert columns[0]["sample_values"] == ["ספק א"] * 5
    assert columns[0]["supplier_values"] == ["ספק א", "ספק ב"]
    assert len(result) == 1
    assert result[0]["ambiguous"] is True
    assert result[0]["matched_supplier_id"] is None
    assert result[0]["detected_supplier_name"] is None
    assert result[0]["candidate_supplier_names"] == ["ספק א", "ספק ב"]

