import { apiClient } from "./api-client";

export interface ExtractedItem { supplier_sku?: string; barcode?: string; description?: string; quantity?: number; unit?: string; package_quantity?: number; unit_price?: number; discount?: number; tax?: number; }
export interface ExtractedData { document_type?: string; supplier?: { name?: string; customer_number?: string }; document_number?: string; document_date?: string; currency?: string; totals?: { subtotal?: number; tax?: number; total?: number }; items?: ExtractedItem[]; }
export interface DocumentAnalysis { id: number; filename: string; mime_type: string; document_type: string | null; status: string; extracted_data: ExtractedData | null; error_message: string | null; provider: string | null; model: string | null; created_at: string; analyzed_at: string | null; applied_at: string | null; applied_by: number | null; }

export const documentIntelligenceService = {
  upload: async (file: File, onProgress?: (percent: number) => void) => {
    const form = new FormData(); form.append("file", file);
    const { data } = await apiClient.post<{ success: boolean; analysis: DocumentAnalysis }>("/api/document-intelligence/upload", form, {
      onUploadProgress: (event) => {
        if (!event.total) return;
        onProgress?.(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      },
    });
    onProgress?.(100);
    return data.analysis;
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
        active = current.status === "ANALYZED" || current.status === "FAILED" || current.status === "AI_UNAVAILABLE" || current.status === "APPLIED";
      } catch {
        // The analyze request remains authoritative; do not fail the UI poller.
      }
      if (!active) break;
    }
    const result = await analyzePromise;
    onAnalysisStatus?.(result);
    return result;
  },
  uploadManyAndAnalyze: async (files: File[], onFileStatus?: (file: File, analysis: DocumentAnalysis | null, stage: "uploading" | "uploaded" | "processing" | "done", percent: number) => void) => {
    const results: DocumentAnalysis[] = [];
    for (const file of files) {
      const result = await documentIntelligenceService.uploadAndAnalyze(
        file,
        (percent) => onFileStatus?.(file, null, "uploading", percent),
        (analysis) => onFileStatus?.(file, analysis, analysis.status === "UPLOADED" ? "uploaded" : analysis.status === "PROCESSING" ? "processing" : "done", analysis.status === "UPLOADED" ? 100 : 0),
      );
      results.push(result);
      onFileStatus?.(file, result, "done", 100);
    }
    return results;
  },
  analyze: async (id: number) => {
    const { data } = await apiClient.post<{ success: boolean; analysis: DocumentAnalysis }>(`/api/document-intelligence/${id}/analyze`);
    return data.analysis;
  },
  get: async (id: number) => {
    const { data } = await apiClient.get<{ success: boolean; analysis: DocumentAnalysis }>(`/api/document-intelligence/${id}`);
    return data.analysis;
  },
  apply: async (id: number, lines: Array<Record<string, unknown>>) => {
    const { data } = await apiClient.post<{ success: boolean; analysis: DocumentAnalysis }>(`/api/document-intelligence/${id}/apply`, { lines });
    return data.analysis;
  },
};
