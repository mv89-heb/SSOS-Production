"""Compatibility shim for the legacy import-analysis patch installer.

Supplier value inference now lives directly in WorkbookAnalyzer._detect_suppliers
so it is exercised by the normal analysis pipeline. Keep this installer while
the application factory still invokes it alongside other import integrity
patches.
"""


def install_supplier_detection_patch():
    """No-op: supplier detection is implemented in the analyzer itself."""
    return None
