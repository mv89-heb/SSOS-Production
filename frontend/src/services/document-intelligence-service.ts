import { apiClient } from "./api-client";

export interface ProcessingProgress { phase?: string; percent?: number; pages_total?: number | null; pages_processed?: number; elapsed_seconds?: number; eta_seconds?: number | null; }
export interface SupplierMatching { supplier_id?: number; supplier_name?: string; confidence?: number; method?: string; decision?: string; }
export interface ProductSuggestion { product_id: number; product_name: string; supplier_id?: number; supplier_name?: string; confidence?: number; method?: string; decision?: string; }
export interface ExtractedItem { supplier_sku?: string; barcode?: string; description?: string; quantity?: number; unit?: string; package_quantity?: number; unit_price?: number; discount?: number; tax?: number; page_number?: number; supplier_section_index?: number; supplier_context?: { name?: string; customer_number?: string }; supplier_matching?: SupplierMatching | null; product_matching?: { decision?: string; best_match?: ProductSuggestion; suggestions?: ProductSuggestion[] }; }
export interface SupplierSection { supplier?: { name?: string; customer_number?: string }; items?: ExtractedItem[]; page_numbers?: number[]; supplier_matching?: SupplierMatching | null; }
export interface OrderReconciliationLine { line_index: number; description?: string; matched: boolean; status: string; order_item_id?: number; product_id?: number; product_name?: string; expected_quantity?: number; extracted_quantity?: number; quantity_delta?: number | null; expected_unit_price?: number; extracted_unit_price?: number; price_delta?: number | null; catalog_unit_price?: number | null; catalog_price_delta?: number | null; currency?: string; unit?: string; confidence?: number; flags?: string[]; reason?: string; }
export interface OrderReconciliation { order_id: number; order_number: string; supplier_id?: number; supplier_name?: string; supplier_check: string; document_type?: string; document_number?: string; document_date?: string; lines: OrderReconciliationLine[]; unmatched_count: number; review_count: number; compared_at?: string; }
export interface ExtractedData { document_type?: string; supplier?: { name?: string; customer_number?: string }; supplier_sections?: SupplierSection[]; supplier_count?: number; document_number?: string; document_date?: string; currency?: string; totals?: { subtotal?: number; tax?: number; total?: number }; items?: ExtractedItem[]; applied_line_indexes?: number[]; processing?: ProcessingProgress; page_count?: number; pages_processed?: number; extraction_mode?: string; supplier_matching?: SupplierMatching | SupplierMatching[] | null; matching_version?: string; order_reconciliation?: OrderReconciliation; invoice_reconciliation_result?: { invoice_id: number; invoice_number: string; automatic_price_updates: Array<{ product_id: number; product_name: string; old_price: number; new_price: number; supplier_id: number }>; prices_updated_count: number }; delivery_note_result?: { receipt_id: number; receipt_number: string; replayed: boolean }; }
export interface DocumentAnalysis { id: number; filename: string; mime_type: string; document_type: string | null; status: string; extracted_data: ExtractedData | null; error_message: string | null; provider: string | null; model: string | null; created_at: string; analyzed_at: string | null; applied_at: string | null; applied_by: number | null; }

export const documentIntelligenceService = {
  upload: async (file: File, onProgress?: (percent: number) => void) => {
    const form = new FormData(); form.append("file", file);
    const { data } = await apiClient.post<{ success: boolean; analysis: DocumentAnalysis }>("/api/document-intelligence/upload", form, { onUploadProgress: (event) => { if (event.total) onProgress?.(Math.min(100, Math.round((event.loaded / event.total) * 100))); } });
    onProgress?.(100); return data.analysis;
  },
  uploadAndAnalyze: async (file: File, onUploadProgress?: (percent: number) => void, onAnalysisStatus?: (analysis: DocumentAnalysis) => void) => {
    const uploaded = await documentIntelligenceService.upload(file, onUploadProgress);
    onAnalysisStatus?.(uploaded);
    // Capture failures immediately. Previously a rejected /analyze request could
    // leave the status-polling loop running forever on an UPLOADED record.
    let analyzeError: unknown = null;
    let analyzeFinished = false;
    const analyzePromise = documentIntelligenceService.analyze(uploaded.id)
      .then((result) => {
        analyzeFinished = true;
        return result;
      })
      .catch((error: unknown) => {
        analyzeError = error;
        analyzeFinished = true;
        return null;
      });
    let active = true;
    let terminalResult: DocumentAnalysis | null = null;
    const pollingStartedAt = Date.now();
    const maxPollingDurationMs = 15 * 60 * 1000;
    while (active) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      try {
        const current = await documentIntelligenceService.get(uploaded.id);
        onAnalysisStatus?.(current);
        active = !["ANALYZED", "PARTIALLY_APPLIED", "FAILED", "AI_UNAVAILABLE", "APPLIED"].includes(current.status);
        if (!active) terminalResult = current;
      } catch { /* Continue polling: the status endpoint may recover before analysis completes. */ }

      // A proxy can return 502/504 while the server-side analysis continues.
      // Trust a persisted terminal status over the outcome of the long-running POST.
      if (terminalResult) return terminalResult;

      if (Date.now() - pollingStartedAt >= maxPollingDurationMs) {
        if (analyzeError) throw analyzeError;
        throw new Error("הניתוח עדיין לא הסתיים לאחר 15 דקות. אפשר לרענן את הרשומה ולבדוק את הסטטוס לפני ניסיון נוסף.");
      }
      if (analyzeError) {
        // Do not mark the file failed just because the analyze request failed:
        // keep checking whether the backend finished and persisted a result.
        continue;
      }
      if (analyzeFinished && active) {
        const result = await analyzePromise;
        if (result) {
          onAnalysisStatus?.(result);
          if (["ANALYZED", "PARTIALLY_APPLIED", "FAILED", "AI_UNAVAILABLE", "APPLIED"].includes(result.status)) return result;
          continue;
        }
        throw new Error("בקשת הניתוח הסתיימה ללא תוצאה");
      }
      if (!active) break;
    }
    if (terminalResult) return terminalResult;
    const result = await analyzePromise;
    if (analyzeError) throw analyzeError;
    if (!result) throw new Error("בקשת הניתוח הסתיימה ללא תוצאה");
    onAnalysisStatus?.(result);
    return result;
  },
  uploadManyAndAnalyze: async (files: File[], onFileStatus?: (file: File, analysis: DocumentAnalysis | null, stage: "uploading" | "uploaded" | "processing" | "done" | "failed", percent: number, error?: string) => void) => {
    const results: Array<DocumentAnalysis | undefined> = new Array(files.length);
    const concurrency = Math.min(2, Math.max(1, files.length));
    let nextIndex = 0;
    async function worker() {
      while (true) {
        const index = nextIndex++;
        if (index >= files.length) return;
        const file = files[index];
        try {
          const result = await documentIntelligenceService.uploadAndAnalyze(
            file,
            (percent) => onFileStatus?.(file, null, "uploading", percent),
            (analysis) => onFileStatus?.(
              file,
              analysis,
              ["FAILED", "AI_UNAVAILABLE"].includes(analysis.status) ? "failed" : analysis.status === "UPLOADED" ? "uploaded" : analysis.status === "PROCESSING" ? "processing" : "done",
              analysis.extracted_data?.processing?.percent ?? (analysis.status === "UPLOADED" ? 100 : 0),
              analysis.error_message || undefined,
            ),
          );
          results[index] = result;
          onFileStatus?.(file, result, result.status === "FAILED" || result.status === "AI_UNAVAILABLE" ? "failed" : "done", 100, result.error_message || undefined);
        } catch (error: unknown) {
          const message = error instanceof Error ? error.message : "העלאת המסמך או ניתוחו נכשלו";
          onFileStatus?.(file, null, "failed", 0, message);
        }
      }
    }
    await Promise.all(Array.from({ length: concurrency }, () => worker()));
    return results.filter((item): item is DocumentAnalysis => Boolean(item));
  },
  analyze: async (id: number) => { const { data } = await apiClient.post<{ success: boolean; analysis: DocumentAnalysis }>(`/api/document-intelligence/${id}/analyze`); return data.analysis; },
  get: async (id: number) => { const { data } = await apiClient.get<{ success: boolean; analysis: DocumentAnalysis }>(`/api/document-intelligence/${id}`); return data.analysis; },
  rematch: async (id: number) => { const { data } = await apiClient.post<{ success: boolean; analysis: DocumentAnalysis }>(`/api/document-intelligence/${id}/rematch`); return data.analysis; },
  apply: async (id: number, lines: Array<Record<string, unknown>>) => { const { data } = await apiClient.post<{ success: boolean; analysis: DocumentAnalysis }>(`/api/document-intelligence/${id}/apply`, { lines }); return data.analysis; },
  createProductFromLine: async (id: number, lineIndex: number, product: Record<string, unknown>) => { const { data } = await apiClient.post<{ success: boolean; analysis: DocumentAnalysis; product: any }>(`/api/document-intelligence/${id}/create-product`, { line_index: lineIndex, product }); return data; },
  compareOrder: async (id: number, orderId: number, confirmSupplier: boolean) => { const { data } = await apiClient.post<{ success: boolean; analysis: DocumentAnalysis; reconciliation: OrderReconciliation }>(`/api/document-intelligence/${id}/compare-order`, { order_id: orderId, confirm_supplier: confirmSupplier }); return data; },
  applyDeliveryNote: async (id: number) => { const { data } = await apiClient.post<{ success: boolean; analysis: DocumentAnalysis; receipt: { id: number; receipt_number: string } }>(`/api/document-intelligence/${id}/apply-delivery-note`); return data; },
  applyInvoice: async (id: number, payload: { invoice_number?: string; invoice_date?: string; amount?: number; currency?: string; allow_price_updates: boolean }) => { const { data } = await apiClient.post<{ success: boolean; analysis: DocumentAnalysis; invoice: { id: number; invoice_number: string }; automatic_price_updates: Array<{ product_id: number; product_name: string; old_price: number; new_price: number; supplier_id: number }> }>(`/api/document-intelligence/${id}/apply-invoice`, payload); return data; },
};
