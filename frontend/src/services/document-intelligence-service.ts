import { apiClient } from "./api-client";

export interface DocumentAnalysis {
  id: number;
  filename: string;
  mime_type: string;
  document_type: string | null;
  status: string;
  extracted_data: any;
  error_message: string | null;
  provider: string | null;
  model: string | null;
  created_at: string;
  analyzed_at: string | null;
  applied_at: string | null;
  applied_by: number | null;
}

export const documentIntelligenceService = {
  upload: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const { data } = await apiClient.post<{ success: boolean; analysis: DocumentAnalysis }>("/api/document-intelligence/upload", form);
    return data.analysis;
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
