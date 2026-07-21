// Mirrors app/models/user.py User.to_dict()
export type UserRole = "admin" | "manager" | "employee";

export interface User {
  id: number;
  tenant_id: number;
  email: string;
  full_name: string;
  role: UserRole;
  active: boolean;
  created_at: string | null;
}

export interface AuthResponse {
  success: boolean;
  user: User;
}

// Mirrors app/routes/auth.py register(): either tenant_name (creates a new
// tenant, caller becomes its admin) or tenant_slug (joins an existing
// tenant as an employee) is required — never both.
export type RegisterPayload =
  | { email: string; password: string; full_name: string; tenant_name: string }
  | { email: string; password: string; full_name: string; tenant_slug: string };

export interface RegisterResponse {
  success: boolean;
  user: User;
  tenant: Tenant;
}

// Mirrors app/models/order.py VALID_STATUSES
export type OrderStatus =
  | "draft"
  | "submitted"
  | "approved"
  | "sent"
  | "completed"
  | "cancelled";

export interface OrderItem {
  product_id: number;
  product_name: string;
  sku: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

// Mirrors app/models/order.py Order.to_dict()
export interface Order {
  id: number;
  tenant_id: number;
  user_id: number;
  order_number: string;
  supplier_name: string;
  supplier_contact: string | null;
  supplier_email: string | null;
  status: OrderStatus;
  subtotal: number;
  discount_total: number;
  tax_total: number;
  final_total: number;
  currency: string;
  items: OrderItem[];
  snapshot: unknown | null;
  snapshot_taken_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateOrderItemInput {
  product_id: number;
  quantity: number;
}

export interface CreateOrderInput {
  supplier_id: number;
  currency?: string;
  notes?: string;
  items: CreateOrderItemInput[];
}

// Mirrors app/models/product.py Product.to_dict()
export interface Product {
  id: number;
  supplier_id: number;
  sku: string;
  name: string;
  description: string | null;
  current_price: number;
  currency: string;
  active: boolean;
  created_at: string;
  image_url: string | null;
  barcode: string | null;
  category: string | null;
  unit: string | null;
  units_per_carton: number | null;
  supplier_sku: string | null;
  current_stock: number | null;
  min_stock: number | null;
  recommended_stock: number | null;
}

// Mirrors app/models/supplier.py Supplier.to_dict()
export interface Supplier {
  id: number;
  tenant_id: number;
  name: string;
  contact_name: string | null;
  email: string | null;
  phone: string | null;
  active: boolean;
  created_at: string;
}

// Mirrors app/models/audit.py AuditLog.to_dict()
export interface AuditLogEntry {
  id: number;
  tenant_id: number;
  user_id: number | null;
  user_email: string | null;
  user_full_name: string | null;
  action: string;
  title: string | null;
  metadata: Record<string, unknown>;
  previous_hash: string;
  hash_chain: string;
  created_at: string;
  timestamp_iso: string;
}

// Mirrors app/models/supplier_offer.py SupplierProductOffer.to_dict()
export interface SupplierOffer {
  id: number;
  product_id: number;
  supplier_id: number;
  supplier_name: string | null;
  supplier_sku: string | null;
  price: number;
  currency: string;
  unit: string | null;
  units_per_carton: number | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

// Mirrors app/models/tenant.py Tenant.to_dict()
export interface Tenant {
  id: number;
  name: string;
  slug: string;
  active: boolean;
  created_at: string | null;
}

// ---------------------------------------------------------------------
// Import Wizard — mirrors app/models/import_session.py,
// import_analysis.py, import_mapping.py, import_validation.py,
// import_execution.py (Phase 3.1 – 3.2D-MVP)
// ---------------------------------------------------------------------

export type ImportSessionStatus = "UPLOADED" | "FAILED";

export interface ImportSession {
  id: number;
  filename: string;
  supplier_id: number | null;
  supplier_name: string | null;
  uploaded_by: number;
  uploaded_by_name: string | null;
  status: ImportSessionStatus;
  error_message: string | null;
  row_count: number | null;
  column_headers?: string[] | null;
  workbook_sheet_names: string[] | null;
  workbook_sheet_count: number | null;
  workbook_active_sheet: string | null;
  staged_sheet_name: string | null;
  created_at: string;
  updated_at: string;
}

export type DetectedFormat = "WIDE" | "TALL" | "MIXED" | "UNKNOWN";

export interface ImportAnalysisColumn {
  index: number;
  header: string;
  group_label: string | null;
  detected_type: string;
  confidence: "high" | "medium" | "low" | "none";
  reason: string;
  sample_values: string[];
}

export interface ImportAnalysisSheet {
  id: number;
  import_session_id: number;
  sheet_name: string;
  sheet_index: number;
  is_hidden: boolean;
  row_count: number;
  column_count: number;
  header_row_index: number | null;
  header_tier_count: number | null;
  has_merged_header_cells: boolean;
  detected_format: DetectedFormat;
  format_reason: string | null;
  columns: ImportAnalysisColumn[];
  detected_suppliers: { column_index: number; header: string; matched_supplier_id: number | null; matched_supplier_name: string | null }[];
  detected_units: string[];
  data_quality: Record<string, unknown>;
  warnings: string[];
  created_at: string;
}

export type MappingTarget =
  | "PRODUCT_NAME" | "PRODUCT_CODE" | "BARCODE" | "CATEGORY" | "UNIT"
  | "SUPPLIER_NAME" | "SUPPLIER_CODE"
  | "PRICE" | "PRICE_BEFORE_VAT" | "PRICE_AFTER_VAT" | "DISCOUNT_PRICE"
  | "SUPPLIER_OFFER" | "IGNORE";

export type PriceType = "regular" | "before_vat" | "after_vat" | "discount";

export interface ImportMappingColumn {
  id: number;
  column_index: number;
  column_header: string;
  suggested_target: MappingTarget;
  suggested_confidence: "high" | "medium" | "low" | "none";
  suggested_supplier_id: number | null;
  suggested_supplier_name: string | null;
  suggested_price_type: PriceType | null;
  final_target: MappingTarget;
  final_supplier_id: number | null;
  final_supplier_name: string | null;
  final_price_type: PriceType | null;
  user_reviewed: boolean;
  changed_from_suggestion: boolean;
}

export interface ImportMapping {
  id: number;
  import_session_id: number;
  import_analysis_id: number | null;
  sheet_name: string;
  status: "DRAFT" | "APPROVED";
  created_by: number;
  created_by_name: string | null;
  approved_by: number | null;
  approved_by_name: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
  columns: ImportMappingColumn[];
}

export interface ImportMappingTemplate {
  id: number;
  supplier_id: number | null;
  supplier_name: string | null;
  name: string;
  source_filename: string | null;
  column_mapping: Record<string, { target: MappingTarget; supplier_id: number | null; supplier_name: string | null; price_type: PriceType | null }>;
  created_by: number;
  created_by_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface ImportValidationSummary {
  products: { created: number; updated: number; skipped: number };
  suppliers: { created: number };
  offers: { created: number; updated: number };
  warnings: number;
  errors: number;
}

export interface ImportIssue {
  id: number;
  row_number: number | null;
  field: string | null;
  severity: "ERROR" | "WARNING";
  code: string;
  message: string;
}

export interface ImportValidation {
  id: number;
  import_session_id: number;
  import_mapping_id: number;
  status: "COMPLETED" | "FAILED";
  error_message: string | null;
  summary: ImportValidationSummary;
  created_by: number;
  created_at: string;
  issues?: ImportIssue[];
}

export type PreviewAction = "CREATE" | "UPDATE" | "SKIP" | "EXISTING" | "ERROR";

export interface ImportPreviewOffer {
  supplier_name: string;
  matched_supplier_id: number | null;
  price: number;
  price_type: PriceType | null;
  action: PreviewAction;
}

export interface ImportPreviewRow {
  id: number;
  row_number: number;
  product_action: PreviewAction;
  product_name: string | null;
  matched_product_id: number | null;
  unit: string | null;
  category: string | null;
  supplier_action: PreviewAction | null;
  supplier_name: string | null;
  matched_supplier_id: number | null;
  price: number | null;
  old_price: number | null;
  offers: ImportPreviewOffer[] | null;
  has_errors: boolean;
  has_warnings: boolean;
}

export interface ImportExecution {
  id: number;
  import_session_id: number;
  import_validation_id: number;
  status: "COMMITTED" | "ROLLED_BACK";
  snapshot_before: { suppliers: number; products: number; offers: number };
  summary: { suppliers_created: number; products_created: number; products_updated: number; offers_created: number };
  created_supplier_ids: number[];
  created_product_ids: number[];
  created_offer_ids: number[];
  price_history: { product_id: number; old_price: number | null; new_price: number }[];
  skipped_rows: { row_number: number; reason: string }[];
  executed_by: number;
  executed_at: string;
  rolled_back_by: number | null;
  rolled_back_at: string | null;
}
