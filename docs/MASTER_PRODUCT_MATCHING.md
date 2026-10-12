# Master product matching and supplier catalog

## Purpose

The legacy `products` table is kept intact because orders, stock, and historical snapshots currently depend on it. The canonical catalog is an additive layer:

- `master_products`: one tenant-scoped canonical identity for a generic product.
- `supplier_products`: the supplier's own name, SKU/barcode, unit, pack information and current price, with an optional link to a master product.
- Existing `products` and `supplier_product_offers` are backfilled as separate approved supplier listings. The migration deliberately does **not** fuzzy-merge historic products.

The application uses Flask + SQLAlchemy + Alembic against PostgreSQL/Neon and Next.js. There is no active Prisma schema in this repository; adding a second ORM would create competing schema ownership.

## Matching pipeline

1. **Exact identity**: a real (non-synthetic) barcode that uniquely matches a master product can be linked automatically. A supplier SKU is scoped to its supplier and updates that supplier listing; it is never treated as a global product identity.
2. **Normalization**: Unicode NFKC/casefold, punctuation/whitespace cleanup, Hebrew apostrophe normalization, common Hebrew/English unit aliases, and percent/size extraction.
3. **Fuzzy candidates**: RapidFuzz scores normalized names. A conflicting explicit package size (for example 1 L vs 2 L) or variant percentage (3% vs 1.5%) is a hard mismatch, regardless of text similarity.
4. **Human review**: high-scoring names are suggestions only; they are not silently assigned. A manager chooses an existing master or creates a new master. Every approval/rejection is audit logged.
5. **Optional semantic AI**: if enabled in a future iteration, an embedding/LLM adapter may rank candidates only after deterministic matching. It must return candidate IDs, a confidence and a short rationale; it must not create or approve a link. Barcode/size/variant conflicts remain hard blockers and a manager's approval remains the final decision. This keeps AI optional and avoids a paid or network-dependent model in the critical path.

Current fuzzy suggestion thresholds are deliberately conservative: candidates below 0.62 are not shown; a candidate at or above 0.94 with a meaningful lead is labelled a high-confidence suggestion but still requires human approval. Only unique exact barcode matches can be safely auto-linked.

## API workflow

All routes are tenant-scoped. Manager/admin role is required for writes and the review queue.

- `POST /api/catalog/supplier-products/intake`: accepts `supplier_id`, `supplier_name`, optional `supplier_sku`, `barcode`, `price`, `currency`, `unit`, and `units_per_carton`. Returns the stored listing and ranked suggestions.
- `POST /api/catalog/master-products/match-suggestions`: rank existing master products for a name/barcode.
- `GET /api/catalog/supplier-products/pending`: review queue.
- `POST /api/catalog/supplier-products/<id>/approve`: approve with `master_product_id`, or pass `create_master_product: { canonical_name, brand?, category?, barcode?, base_unit?, package_size?, package_unit? }`.
- `POST /api/catalog/supplier-products/<id>/reject`: reject the current suggestion.
- `GET /api/catalog/master-products?q=...`: list/search active canonical products.

The Hebrew UI is available at `/dashboard/catalog/matching` for users who can manage the catalog.

## Data and rollout safety

- Migration `20261012_master_supplier_products` is additive and backfills old catalog records as one master per legacy product; it does not merge products by name.
- Existing order snapshots and current inventory logic remain on their existing tables and are not rewritten by match approvals.
- Prices must be positive when supplied; invalid zero/negative prices are stored as unknown rather than presented as a real offer during legacy backfill.
- Supplier SKU lookup is indexed but not globally unique because historical rows may contain duplicates. New intake reuses an existing listing when a supplier SKU is already present.
- Before merging, run the backend suite and frontend type-check/build. Before production deployment, verify Alembic migration on a Neon branch or staging database, review backfill counts, then deploy through the normal release pipeline. Do not run an ad-hoc production migration from the review screen.
