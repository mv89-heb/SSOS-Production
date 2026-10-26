import { redirect } from "next/navigation";

/**
 * Canonical master-product comparison and supplier-review experience lives at
 * /dashboard/master-products. Keep this historical URL as a redirect so users
 * and bookmarks reach the single source of truth instead of a duplicate screen.
 */
export default function CatalogMasterProductsRedirect() {
  redirect("/dashboard/master-products");
}
