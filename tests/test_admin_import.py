def test_admin_routes_import_cleanly():
    """Keep deployment from regressing on a missing admin model/module import."""
    from app.routes.admin import admin_bp

    assert admin_bp.name == "admin"
    assert admin_bp.url_prefix == "/api/admin"
