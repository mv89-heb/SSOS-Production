# Migration recovery strategy

Production may contain schema objects created by an earlier deployment while Alembic has not recorded the corresponding revision. Migrations that reconcile such state should check for existing columns, tables, and indexes before creating them.

Revision identifiers must remain within the `alembic_version.version_num` column limit used by the production database.
