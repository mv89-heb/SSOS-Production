"""Add optional supplier profile fields and backfill known delivery schedules.

Revision ID: 20261018_supplier_profile
Revises: 20261013_master_product_dedupe, 95371bcfb9b2
"""
from alembic import op
import sqlalchemy as sa

revision = "20261018_supplier_profile"
down_revision = ("20261013_master_product_dedupe", "95371bcfb9b2")
branch_labels = None
depends_on = None


def upgrade():
    columns = [
        sa.Column("mobile", sa.String(50), nullable=True),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("city", sa.String(120), nullable=True),
        sa.Column("tax_id", sa.String(100), nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("supplier_category", sa.String(120), nullable=True),
        sa.Column("payment_terms", sa.String(255), nullable=True),
        sa.Column("credit_days", sa.Integer(), nullable=True),
        sa.Column("minimum_order_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("delivery_fee", sa.Numeric(12, 2), nullable=True),
        sa.Column("lead_time_days", sa.Integer(), nullable=True),
        sa.Column("order_cutoff_time", sa.String(20), nullable=True),
        sa.Column("certification_details", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    ]
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("suppliers")}
    for column in columns:
        if column.name not in existing:
            op.add_column("suppliers", column)

    # Populate only empty values from the repository's maintained supplier
    # schedule master. Existing manually maintained schedules are preserved.
    suppliers = sa.table(
        "suppliers",
        sa.column("name", sa.String),
        sa.column("order_days", sa.String),
        sa.column("delivery_days", sa.String),
        sa.column("supplier_category", sa.String),
    )
    schedule_rows = [
        (("אנג'ל", "אנג'ל בית מאפה"), "מאפה", "ראשון, שני, שלישי, רביעי, חמישי, שישי", "ראשון, שני, שלישי, רביעי, חמישי, שישי"),
        (("תנובה",), "מוצרי חלב", "ראשון, שלישי, חמישי", "שני, רביעי, שישי"),
        (("אוסם",), "יבש וקפוא", "שני, רביעי", "שלישי, חמישי"),
        (("ווגשל",), "מזון", "ראשון, רביעי", "שני, חמישי"),
        (("טמפו",), "משקאות", "שני", "שלישי"),
        (("גידרון",), "קפואים", "ראשון, שלישי", "שני, רביעי"),
        (("בן אנד ג'רי", "בן ג'ריס", "בנז'ריס", "בן אן ג'ריס"), "גלידות", "שני", "שלישי"),
        (("עמית",), "מזון", "ראשון, רביעי", "שני, חמישי"),
    ]
    for names, category, order_days, delivery_days in schedule_rows:
        for name in names:
            bind.execute(
                suppliers.update()
                .where(sa.func.lower(sa.func.trim(suppliers.c.name)) == name.lower())
                .values(
                    supplier_category=sa.func.coalesce(sa.func.nullif(sa.func.trim(suppliers.c.supplier_category), ""), category),
                    order_days=sa.func.coalesce(sa.func.nullif(sa.func.trim(suppliers.c.order_days), ""), order_days),
                    delivery_days=sa.func.coalesce(sa.func.nullif(sa.func.trim(suppliers.c.delivery_days), ""), delivery_days),
                )
            )

    # The committed master file is the authoritative source for legacy
    # contact names and phone numbers. Never replace a non-empty live value.
    from pathlib import Path
    import re
    import unicodedata
    from openpyxl import load_workbook

    def normalize_name(value):
        value = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
        value = value.replace("בן אן ג'ריס", "בן אנד ג'רי").replace("בן ג'ריס", "בן אנד ג'רי").replace("בנז'ריס", "בן אנד ג'רי")
        return re.sub(r"[\\W_]+", "", value, flags=re.UNICODE)

    workbook_path = Path(__file__).resolve().parents[2] / "Fixed_Suppliers_Master.xlsx"
    if workbook_path.exists():
        workbook = load_workbook(workbook_path, read_only=True, data_only=True)
        sheet = workbook.active
        rows = sheet.iter_rows(values_only=True)
        headers = [str(value or "").strip() for value in next(rows, ())]
        index = {header: position for position, header in enumerate(headers)}
        required_headers = {"שם ספק", "טלפון ראשי", "טלפון נוסף", "נייד", "איש קשר"}
        if required_headers.issubset(index):
            contact_table = sa.table(
                "suppliers",
                sa.column("id", sa.Integer),
                sa.column("name", sa.String),
                sa.column("contact_name", sa.String),
                sa.column("phone", sa.String),
                sa.column("phone2", sa.String),
                sa.column("mobile", sa.String),
            )
            existing_rows = bind.execute(sa.select(contact_table)).mappings().all()
            by_name = {}
            for existing in existing_rows:
                by_name.setdefault(normalize_name(existing["name"]), []).append(existing)
            for values in rows:
                source_name = str(values[index["שם ספק"]] or "").strip()
                if not source_name:
                    continue
                matches = by_name.get(normalize_name(source_name), [])
                # Ambiguous normalized names are skipped rather than guessed.
                if len(matches) != 1:
                    continue
                existing = matches[0]
                def source_value(header):
                    value = values[index[header]] if index[header] < len(values) else None
                    text = str(value).strip() if value is not None else ""
                    return text if text and text.casefold() != "nan" else None
                updates = {}
                for source_header, target_column in (
                    ("איש קשר", "contact_name"),
                    ("טלפון ראשי", "phone"),
                    ("טלפון נוסף", "phone2"),
                    ("נייד", "mobile"),
                ):
                    value = source_value(source_header)
                    if value and not str(existing[target_column] or "").strip():
                        updates[target_column] = value
                if updates:
                    bind.execute(
                        contact_table.update()
                        .where(contact_table.c.id == existing["id"])
                        .values(**updates)
                    )
        workbook.close()

    # Public company identity details are taken from the suppliers' own sites.
    # Generic public details are added only when the corresponding field is blank.
    public_profiles = [
        # name aliases, official website, address, city, general phone, general email, tax id, category
        (("אוסם",), "https://www.osem-nestle.co.il", "קריית אסם", "שוהם", None, None, None, "יבש וקפוא"),
        (("תנובה",), "https://www.tnuva.co.il", "יגיע כפיים 21", "פתח תקווה", None, None, None, "מוצרי חלב"),
        (("גידרון",), "https://www.gidron.co.il", None, "חולון", "03-557-0200", None, "510894587", "קפואים"),
        (("יפאורה", "יפאורה תבורי"), "https://www.jafora.co.il", "אלי הורוביץ 4, בית מיקה", "רחובות", "08-9346858", None, None, "משקאות"),
        (("שטראוס",), "https://www.strauss-group.co.il", None, None, None, None, None, "מוצרי מזון"),
        (("אנג'ל",), "https://www.angel.co.il", None, None, None, None, None, "מאפה"),
        (("ווגשל",), "https://www.vagshal.com", "עצמונה 11, מישור אדומים", "מישור אדומים", "02-590-2055", "office@vagshal.com", None, "מזון"),
        (("פעמית.ח",), "https://www.peamitpro.co.il", None, None, "077-9971610", "peamit@peamit.co.il", None, "חד פעמי וציוד מוסדי"),
        (("ר. שמאי",), "https://www.rshamay.co.il", "היצירה 10, אזור התעשייה ברוש", "בית שמש", "02-642-9452", "office@rshamay.co.il", "514212596", "חד פעמי וניקיון"),
    ]
    public_table = sa.table(
        "suppliers",
        sa.column("name", sa.String),
        sa.column("website", sa.String),
        sa.column("address", sa.String),
        sa.column("city", sa.String),
        sa.column("phone", sa.String),
        sa.column("email", sa.String),
        sa.column("tax_id", sa.String),
        sa.column("supplier_category", sa.String),
    )
    for names, website, address, city, phone, email, tax_id, category in public_profiles:
        for name in names:
            values = {
                "website": sa.func.coalesce(sa.func.nullif(sa.func.trim(public_table.c.website), ""), website),
            }
            for column, value in (
                ("address", address),
                ("city", city),
                ("phone", phone),
                ("email", email),
                ("tax_id", tax_id),
                ("supplier_category", category),
            ):
                if value:
                    values[column] = sa.func.coalesce(
                        sa.func.nullif(sa.func.trim(getattr(public_table.c, column)), ""),
                        value,
                    )
            bind.execute(
                public_table.update()
                .where(sa.func.lower(sa.func.trim(public_table.c.name)) == name.lower())
                .values(**values)
            )


def downgrade():
    # The schedule backfill intentionally remains: deleting newly learned
    # supplier data during rollback would be surprising and irreversible.
    bind = op.get_bind()
    existing = {column["name"] for column in sa.inspect(bind).get_columns("suppliers")}
    for name in [
        "notes", "certification_details", "order_cutoff_time", "lead_time_days",
        "delivery_fee", "minimum_order_amount", "credit_days", "payment_terms",
        "supplier_category", "website", "tax_id", "city", "address", "mobile",
    ]:
        if name in existing:
            op.drop_column("suppliers", name)
