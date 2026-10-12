export type ProductSortDirection = "asc" | "desc";

/** Stable, locale-aware alphabetical sorting for Hebrew and Latin product names. */
export function sortByHebrewName<T>(items: readonly T[], getName: (item: T) => string, direction: ProductSortDirection = "asc"): T[] {
  const sign = direction === "asc" ? 1 : -1;
  return [...items].sort((a, b) => sign * getName(a).localeCompare(getName(b), "he", { sensitivity: "base", numeric: true }));
}
