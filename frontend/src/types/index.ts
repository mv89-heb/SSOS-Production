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

// Mirrors app/models/tenant.py Tenant.to_dict()
export interface Tenant {
  id: number;
  name: string;
  slug: string;
  active: boolean;
  created_at: string | null;
}
