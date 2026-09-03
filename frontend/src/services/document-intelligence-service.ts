import { apiClient } from "./api-client";

export interface ProcessingProgress { phase?: string; percent?: number; pages_total?: number | null; pages_processed?: number; elapsed_seconds?: number; eta_seconds?: number | null; }
export interface ExtractedItem { supplier_sku?: string; barcode?: string; description?: string; quantity?: number; unit?: string; package_quantity?: number; unit_price?: number; discount?: number; tax?: number; page_number?: number; product_matching?: { decision?: string; best_match?: { product_id?: number; product_name?: string; supplier_id?: number; supplier_name?: string; confidence?: number; method?: string }; suggestions?: Array<Record<string, unknown>> }; }
export interface ExtractedData { document_type?: string; supplier?: { name?: string; customer_number?: string }; document_number?: string; document_date?: string; currency?: string; totals?: { subtotal?: number; tax?: number; total?: number }; items?: ExtractedItem[]; processing?: ProcessingProgress; page_count?: number; pages_processed?: number; extraction_mode?: string; supplier_matching?: Record<string, unknown> | null; matching_version?: string; }
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
    const analyzePromise = documentIntelligenceService.analyze(uploaded.id);
    let active = true;
    while (active) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      try {
        const current = await documentIntelligenceService.get(uploaded.id);
        onAnalysisStatus?.(current);
        active = !["ANALYZED", "FAILED", "AI_UNAVAILABLE", "APPLIED"].includes(current.status);
      } catch { /* The analyze request remains authoritative. */ }
      if (!active) break;
    }
    const result = await analyzePromise; onAnalysisStatus?.(result); return result;
  },
  uploadManyAndAnalyze: async (files: File[], onFileStatus?: (file: File, analysis: DocumentAnalysis | null, stage: "uploading" | "uploaded" | "processing" | "done", percent: number) => void) => {
    const results: DocumentAnalysis[] = [];
    for (const file of files) {
      const result = await documentIntelligenceService.uploadAndAnalyze(file, (percent) => onFileStatus?.(file, null, "uploading", percent), (analysis) => onFileStatus?.(file, analysis, analysis.status === "UPLOADED" ? "uploaded" : analysis.status === "PROCESSING" ? "processing" : "done", analysis.status === "UPLOADED" ? 100 : 0));
      results.push(result); onFileStatus?.(file, result, "done", 100);
    }
    return results;
  },
  analyze: async (id: number) => { const { data } = await apiClient.post<{ success: boolean; analysis: DocumentAnalysis }>(`/api/document-intelligence/${id}/analyze`); return data.analysis; },
  get: async (id: number) => { const { data } = await apiClient.get<{ success: boolean; analysis: DocumentAnalysis }>(`/api/document-intelligence/${id}`); return data.analysis; },
  apply: async (id: number, lines: Array<Record<string, unknown>>) => { const { data } = await apiClient.post<{ success: boolean; analysis: DocumentAnalysis }>(`/api/document-intelligence/${id}/apply`, { lines }); return data.analysis; },
};
