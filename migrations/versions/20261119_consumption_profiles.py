"""Create tenant-scoped recurring consumption and reinforcement profiles.

Revision ID: 20261119_consumption_profiles
Revises: 20261119_credit_adjustments
"""
from alembic import op
import sqlalchemy as sa
from decimal import Decimal

revision = "20261119_consumption_profiles"
down_revision = "20261119_credit_adjustments"
branch_labels = None
depends_on = None


SEED_ROWS = [
    ("צלחות קלקר (גודל 9)", "חד\"פ", 5, 10, 5, 2, 4, 3, 4.5, "healthy", "both"),
    ("כוסות נייר (שתייה חמה/קרה)", "חד\"פ", 4, 8, 4, 1.5, 3, 3, 4.5, "healthy", "both"),
    ("מרקיות (קלקר / פלסטיק קשיח)", "חד\"פ", 2, 8, 2, 1, 2.5, 3, 4.5, "reorder", "both"),
    ("סכו\"ם (כפות, מזלגות, סכינים)", "חד\"פ", 2, 5, 2, 1, 2, 3, 4.5, "healthy", "both"),
    ("כוסות פלסטיק קשיח / פשוטות", "חד\"פ", 2, 5, 2, 1, 2, 3, 4.5, "healthy", "pamit"),
    ("לפטניות / קסרול אובלי", "חד\"פ", 2, 4, 2, 1, 2, 3, 4.5, "healthy", "pamit"),
    ("קערות פירות גדולות", "חד\"פ", 2, 3, 2, 0.5, 1.5, 3, 4.5, "healthy", "pamit"),
    ("מגבות נייר (165 מ׳ למתקנים)", "נייר", 6, 10, 6, 2, 3.5, 3, 4.5, "healthy", "pamit"),
    ("נייר טואלט (צץ-רץ / פטנט)", "נייר", 3, 5, 3, 1, 2, 3, 4.5, "healthy", "pamit"),
    ("סבון ידיים / מקציף", "ניקיון", 1, 3, 1, 0.5, 1, 3, 4.5, "healthy", "pamit"),
    ("נוזל לניקוי כלים", "ניקיון", 1, 12, 1, 1, 2, 3, 4.5, "healthy", "pamit"),
    ("אקונומיקה וחומצה לשירותים", "ניקיון", 3, 6, 3, 1, 2, 3, 4.5, "healthy", "pamit"),
    ("שקיות אשפה (שחורות / קומפקט)", "תחזוקה", 1, 3, 1, 1, 2, 3, 4.5, "healthy", "pamit"),
    ("כפפות (לטקס / ניטריל)", "תחזוקה", 1, 12, 1, 1, 2, 3, 4.5, "healthy", "pamit"),
    ("פח שובך 50 ליטר", "תחזוקה", 5, 10, 5, 0.2, 0.5, 3, 4.5, "healthy", "pamit"),
    ("מגבים, מטאטאים ויאה", "ציוד", 5, 10, 5, 0.2, 0.5, 3, 4.5, "healthy", "pamit"),
    ("תבניות גסטרונום / אלומיניום", "אפייה", 3, 10, 3, 1, 3, 3, 4.5, "healthy", "pamit"),
    ("תבנית אינגליש קייק / A8", "אפייה", 1, 3, 1, 0.5, 1, 3, 4.5, "healthy", "pamit"),
]


def upgrade():
    op.create_table(
        "inventory_consumption_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("supplier_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("product_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("min_order_quantity", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("max_order_quantity", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("average_order_quantity", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("regular_weekly_consumption", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("reinforced_weekly_consumption", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("reinforcement_cycle_weeks", sa.Numeric(8, 3), nullable=False, server_default="3"),
        sa.Column("safety_stock", sa.Numeric(12, 3), nullable=False, server_default="0"),
        sa.Column("order_status", sa.String(20), nullable=False, server_default="healthy"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "name", name="uq_inventory_consumption_profiles_tenant_name"),
        sa.CheckConstraint("min_order_quantity >= 0", name="ck_inventory_consumption_profiles_min_order_nonnegative"),
        sa.CheckConstraint("max_order_quantity >= min_order_quantity", name="ck_inventory_consumption_profiles_order_range"),
        sa.CheckConstraint("average_order_quantity >= 0", name="ck_inventory_consumption_profiles_average_nonnegative"),
        sa.CheckConstraint("regular_weekly_consumption >= 0", name="ck_inventory_consumption_profiles_regular_nonnegative"),
        sa.CheckConstraint("reinforced_weekly_consumption >= 0", name="ck_inventory_consumption_profiles_reinforced_nonnegative"),
        sa.CheckConstraint("reinforcement_cycle_weeks >= 1", name="ck_inventory_consumption_profiles_cycle_positive"),
        sa.CheckConstraint("safety_stock >= 0", name="ck_inventory_consumption_profiles_safety_nonnegative"),
    )
    op.create_index("ix_inventory_consumption_profiles_tenant_active", "inventory_consumption_profiles", ["tenant_id", "active"])

    bind = op.get_bind()
    tenant_ids = bind.execute(sa.text("""
        SELECT tenant_id
        FROM suppliers
        WHERE active IS TRUE AND (name ILIKE '%שמאי%' OR name ILIKE '%פעמית%')
        GROUP BY tenant_id
        HAVING COUNT(DISTINCT CASE WHEN name ILIKE '%שמאי%' THEN 'shamai' WHEN name ILIKE '%פעמית%' THEN 'pamit' END) = 2
    """)).scalars().all()
    for tenant_id in tenant_ids:
        supplier_ids = bind.execute(sa.text("""
            SELECT id FROM suppliers
            WHERE tenant_id = :tenant_id AND active IS TRUE
              AND (name ILIKE '%שמאי%' OR name ILIKE '%פעמית%')
            ORDER BY CASE WHEN name ILIKE '%שמאי%' THEN 0 ELSE 1 END, id
        """), {"tenant_id": tenant_id}).scalars().all()
        rows = []
        for name, category, minimum, maximum, average, regular, reinforced, cycle, safety, status, supplier_group in SEED_ROWS:
            rows.append({
                "tenant_id": tenant_id, "name": name, "category": category,
                "supplier_ids": [sid for sid in supplier_ids if (supplier_group == "both" or (supplier_group == "shamai" and "שמאי" in bind.execute(sa.text("SELECT name FROM suppliers WHERE id = :id"), {"id": sid}).scalar()) or (supplier_group == "pamit" and "פעמית" in bind.execute(sa.text("SELECT name FROM suppliers WHERE id = :id"), {"id": sid}).scalar()))], "product_ids": [],
                "min_order_quantity": minimum, "max_order_quantity": maximum,
                "average_order_quantity": average, "regular_weekly_consumption": regular,
                "reinforced_weekly_consumption": reinforced, "reinforcement_cycle_weeks": cycle,
                "safety_stock": safety, "order_status": status, "active": True,
                "source_note": "ייבוא טבלת מעקב שבתות חד-פעמי וניקיון; שיוך מוצר לקטלוג ממתין לאישור כדי למנוע התאמה שגויה.",
            })
        existing = bind.execute(sa.text("""
            SELECT name FROM inventory_consumption_profiles WHERE tenant_id = :tenant_id
        """), {"tenant_id": tenant_id}).scalars().all()
        rows = [row for row in rows if row["name"] not in set(existing)]
        if rows:
            op.bulk_insert(sa.table(
                "inventory_consumption_profiles",
                sa.column("tenant_id", sa.Integer()), sa.column("name", sa.String()),
                sa.column("category", sa.String()), sa.column("supplier_ids", sa.JSON()),
                sa.column("product_ids", sa.JSON()), sa.column("min_order_quantity", sa.Numeric()),
                sa.column("max_order_quantity", sa.Numeric()), sa.column("average_order_quantity", sa.Numeric()),
                sa.column("regular_weekly_consumption", sa.Numeric()), sa.column("reinforced_weekly_consumption", sa.Numeric()),
                sa.column("reinforcement_cycle_weeks", sa.Numeric()), sa.column("safety_stock", sa.Numeric()),
                sa.column("order_status", sa.String()), sa.column("active", sa.Boolean()),
                sa.column("source_note", sa.Text()),
            ), rows)


def downgrade():
    op.drop_index("ix_inventory_consumption_profiles_tenant_active", table_name="inventory_consumption_profiles")
    op.drop_table("inventory_consumption_profiles")
