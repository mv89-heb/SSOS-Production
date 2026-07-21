"""
Shared Header Detection — single source of truth.

Both ImportService (Staging, Phase 3.1) and ImportAnalysisService (Analysis,
Phase 3.2A) need to answer the same question — "where does the real header
end and real data begin in this sheet?" — for the SAME uploaded file. Until
this module existed, each had its own independent answer: Staging used a
naive "first non-empty row is the header" rule, while Analysis had this
more careful multi-tier-aware detector. That meant a two-tier-header file
(a merged supplier-name row above a real column-label row — a common
pattern in real supplier price lists) got staged with its second header
row misread as if it were a product, producing garbage Validation errors
that had nothing to do with the actual data.

This function is that shared answer. Extracted verbatim from
ImportAnalysisService.WorkbookAnalyzer._detect_header (Phase 3.2A) — the
detection heuristic itself is unchanged, tested since that phase, and now
empirically confirmed (Phase "Header Detection Root Cause" investigation)
to correctly predict exactly which staged rows are header artifacts. Only
its location changed: it now lives here, and both services call into it,
instead of each having their own copy (Analysis) or a cruder substitute
(Staging).
"""
import re

_NUMERIC_RE = re.compile(r"^-?\d+(\.\d+)?$")
_CURRENCY_SYMBOLS = ["\u20aa", "$", "\u20ac"]  # ₪, $, €


def _clean_str(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _looks_numeric(value) -> bool:
    if isinstance(value, (int, float)):
        return True
    s = _clean_str(value)
    if not s:
        return False
    stripped = s
    for sym in _CURRENCY_SYMBOLS:
        stripped = stripped.replace(sym, "")
    stripped = stripped.replace(",", "").strip()
    return bool(_NUMERIC_RE.match(stripped))


def _row_signature(row: list) -> dict:
    non_empty = [v for v in row if _clean_str(v) != ""]
    numeric = [v for v in non_empty if _looks_numeric(v)]
    return {
        "non_empty_count": len(non_empty),
        "numeric_ratio": (len(numeric) / len(non_empty)) if non_empty else 0.0,
    }


def detect_header(rows: list, max_tiers: int = 3) -> tuple:
    """Returns (header_start_row_1based, tier_count, reason).

    Heuristic: the first non-empty row starts the header. A candidate next
    row is only treated as ANOTHER header tier (not real data) if there's
    a positive signal it's a label row rather than an all-text data row —
    low numeric ratio alone isn't enough, since a table with no numeric
    columns at all (e.g. text-only notes) would otherwise look
    "header-like" forever and swallow every row. The two positive signals:
    (a) the row before it was noticeably SPARSER (a classic merged-cell
    group-label pattern, e.g. only 3 of 6 cells filled because a supplier
    name spans several columns), or (b) the row AFTER it has a
    meaningfully higher numeric ratio (real data genuinely starts later,
    not here). This is a heuristic, not a certainty — the reason string
    always explains what was observed so a human can override it in the
    Mapping Engine.

    For a file with a single header row (the common case), this always
    returns tier_count=1 — unchanged from the original single-row rule
    Staging used before, so simple files are completely unaffected.
    """
    header_start = None
    for i, row in enumerate(rows):
        if _row_signature(row)["non_empty_count"] > 0:
            header_start = i
            break
    if header_start is None:
        return 1, 1, "No non-empty rows found; defaulting header to row 1."

    tier_count = 1
    reasons = []
    prev_sig = _row_signature(rows[header_start])
    for offset in range(1, max_tiers):
        idx = header_start + offset
        if idx >= len(rows):
            break
        sig = _row_signature(rows[idx])
        if sig["non_empty_count"] == 0:
            break
        if sig["numeric_ratio"] > 0.25:
            break

        sparser_before = sig["non_empty_count"] > prev_sig["non_empty_count"]
        next_idx = idx + 1
        next_more_numeric = (
            next_idx < len(rows)
            and _row_signature(rows[next_idx])["numeric_ratio"] > sig["numeric_ratio"] + 0.25
        )
        if not (sparser_before or next_more_numeric):
            break

        tier_count += 1
        reasons.append(f"row {idx + 1} looks header-like (numeric_ratio={sig['numeric_ratio']:.2f})")
        prev_sig = sig

    if tier_count > 1:
        reason = (
            f"Detected a {tier_count}-tier header starting at row {header_start + 1}: "
            + "; ".join(reasons)
            + ". If this is wrong (e.g. a merged supplier-name row followed by a real "
              "sub-header), the Mapping Engine should let a person override the header row."
        )
    else:
        reason = f"Detected a single header row at row {header_start + 1}."
    return header_start + 1, tier_count, reason
