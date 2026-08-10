import { ImportPreviewRow, ImportPreviewOffer } from "@/types";

/**
 * Offer Counting UX fix (Frontend-only — see areas/ssos-supplier-orders
 * discussion). The backend's own validation summary counts every entry in
 * a row's `offers` list, including the one that becomes that row's
 * PRIMARY listing (Product.supplier_id/current_price) — which never
 * becomes a separate SupplierProductOffer row. This mirrors the exact
 * `is_primary` check ImportExecutionService.commit() already applies at
 * actual write time, just re-applied here to the same /preview data for
 * accurate display before commit ever runs. No backend change needed —
 * every field used here already exists on ImportPreviewRow.
 */

function isPrimaryOffer(row: ImportPreviewRow, offer: ImportPreviewOffer): boolean {
  return offer.supplier_name === row.supplier_name && offer.price === row.price;
}

export interface OfferBreakdown {
  /** Every price-bearing cell detected across all WIDE-format rows,
   * including each row's own primary entry — matches the backend's raw
   * (currently inflated) offers.created count, kept for transparency. */
  priceRecordsDetected: number;
  /** One per row that has at least one supplier-offer column — this
   * becomes that product's Product.current_price/supplier_id, not a
   * separate SupplierProductOffer row. */
  primarySupplierPrices: number;
  /** The true count of SupplierProductOffer rows a commit will actually
   * create — matches ImportExecution.summary.offers_created exactly. */
  additionalSupplierOffers: number;
}

export function computeOfferBreakdown(rows: ImportPreviewRow[] | undefined): OfferBreakdown {
  let priceRecordsDetected = 0;
  let primarySupplierPrices = 0;
  let additionalSupplierOffers = 0;

  for (const row of rows ?? []) {
    const offers = row.offers ?? [];
    if (offers.length === 0) continue;
    primarySupplierPrices += 1;
    for (const offer of offers) {
      priceRecordsDetected += 1;
      if (!isPrimaryOffer(row, offer)) {
        additionalSupplierOffers += 1;
      }
    }
  }

  return { priceRecordsDetected, primarySupplierPrices, additionalSupplierOffers };
}

/** Same exclusion, applied to a single row — for Preview's per-row
 * "+N הצעות נוספות" hint, so it doesn't count that row's own primary. */
export function countAdditionalOffersForRow(row: ImportPreviewRow): number {
  const offers = row.offers ?? [];
  return offers.filter((o) => !isPrimaryOffer(row, o)).length;
}
