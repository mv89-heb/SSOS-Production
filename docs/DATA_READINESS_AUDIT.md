# Procurement Data Readiness Audit

## Production snapshot

Audited the Neon `SSOS-Production` production branch on 2026-09-09 using read-only queries.

| Entity | Rows | Readiness |
|---|---:|---|
| tenants | 1 | OK |
| suppliers | 52 | Partial |
| products | 837 | Needs cleanup |
| supplier_product_offers | 723 | Needs normalization |
| price_history | 0 | Blocker |
| price_observations | 0 | Blocker |
| orders | 9 | Blocker for spend analytics |
| document_analyses | 10 | Partial |

## Key findings

- 837 active products exist, but only 292 have a non-zero current price.
- 284 products have no category.
- All 837 products currently have no SKU and no barcode in the production dataset.
- 31 products have no unit.
- No products currently have stock, minimum-stock, or recommended-stock values.
- 723 supplier offers exist across 16 suppliers and 547 products.
- All 723 supplier offers currently have a price and currency, but none has a unit value.
- Price history contains 0 rows and price observations contain 0 rows, so historical price trends cannot be calculated yet.
- There are 9 orders containing items, but all have zero monetary totals. Seven are drafts and two are submitted. This is insufficient for trustworthy spend analytics.
- Supplier records contain 52 active suppliers; 34 have a phone number and none currently has an email in the production snapshot.

## Consequence for Procurement Intelligence

The current database is sufficient to power a live catalog and basic supplier-offer comparison, but it is not yet sufficient for trustworthy procurement intelligence such as:

- historical price trends;
- realized spend by supplier/category;
- supplier performance based on transaction history;
- quantified savings from historical purchasing;
- stock-risk alerts;
- normalized price-per-unit comparisons.

The UI should not fabricate these metrics. It should expose data-readiness gaps explicitly until the underlying data is populated and normalized.

## Recommended implementation order

1. Normalize product and supplier master data.
2. Establish a canonical unit/comparison-unit model for products and supplier offers.
3. Populate price observations/history from imports, invoices, price lists, and subsequent price changes.
4. Ensure order items resolve to canonical products and that order totals are calculated from validated line items.
5. Populate inventory fields only when a real inventory source exists.
6. Add deterministic analytics queries for spend, price movement, supplier concentration, anomalies, and savings opportunities.
7. Upgrade the Procurement Intelligence screen to consume those analytics and display explicit readiness states when a metric lacks sufficient data.

## Safety principle

Do not backfill fake business data merely to make dashboards look populated. Any synthetic/demo dataset should be isolated from production and clearly labeled.
