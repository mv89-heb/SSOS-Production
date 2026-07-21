import { apiClient } from "./api-client";
import {
  ImportSession, ImportAnalysisSheet, ImportMapping, ImportMappingTemplate,
  ImportValidation, ImportPreviewRow, ImportExecution, MappingTarget, PriceType,
} from "@/types";

export interface MappingDecision {
  column_index: number;
  target?: MappingTarget;
  supplier_id?: number | null;
  supplier_name?: string;
  price_type?: PriceType;
}

export const importService = {
  list: async () => {
    const { data } = await apiClient.get<{ success: boolean; sessions: ImportSession[] }>("/api/imports");
    return data.sessions;
  },

  get: async (sessionId: number) => {
    const { data } = await apiClient.get<{ success: boolean; session: ImportSession }>(`/api/imports/${sessionId}`);
    return data.session;
  },

  upload: async (file: File, opts?: { supplierId?: number; sheetName?: string }) => {
    const form = new FormData();
    form.append("file", file);
    if (opts?.supplierId) form.append("supplier_id", String(opts.supplierId));
    if (opts?.sheetName) form.append("sheet_name", opts.sheetName);
    // Must NOT send Content-Type: application/json (apiClient's default) —
    // clearing it lets axios auto-detect FormData and set the correct
    // multipart boundary itself.
    const { data } = await apiClient.post<{ success: boolean; session: ImportSession }>(
      "/api/imports/upload",
      form,
      { headers: { "Content-Type": undefined } }
    );
    return data.session;
  },

  getRows: async (sessionId: number, limit = 50, offset = 0) => {
    const { data } = await apiClient.get<{ success: boolean; rows: { row_number: number; raw_data: Record<string, string> }[]; total: number }>(
      `/api/imports/${sessionId}/rows`,
      { params: { limit, offset } }
    );
    return data;
  },

  analyze: async (sessionId: number) => {
    const { data } = await apiClient.post<{ success: boolean; analysis: ImportAnalysisSheet[] }>(`/api/imports/${sessionId}/analyze`);
    return data.analysis;
  },

  getAnalysis: async (sessionId: number) => {
    const { data } = await apiClient.get<{ success: boolean; analysis: ImportAnalysisSheet[] }>(`/api/imports/${sessionId}/analysis`);
    return data.analysis;
  },

  getMapping: async (sessionId: number) => {
    const { data } = await apiClient.get<{ success: boolean; mapping: ImportMapping; matching_templates: ImportMappingTemplate[] }>(
      `/api/imports/${sessionId}/mapping`
    );
    return data;
  },

  updateMapping: async (sessionId: number, decisions: MappingDecision[]) => {
    const { data } = await apiClient.post<{ success: boolean; mapping: ImportMapping }>(
      `/api/imports/${sessionId}/mapping`,
      { decisions }
    );
    return data.mapping;
  },

  approveMapping: async (sessionId: number) => {
    const { data } = await apiClient.post<{ success: boolean; mapping: ImportMapping }>(`/api/imports/${sessionId}/mapping/approve`);
    return data.mapping;
  },

  listTemplates: async (sessionId: number) => {
    const { data } = await apiClient.get<{ success: boolean; templates: ImportMappingTemplate[] }>(`/api/imports/${sessionId}/mapping/templates`);
    return data.templates;
  },

  saveTemplate: async (sessionId: number, name: string, supplierId?: number) => {
    const { data } = await apiClient.post<{ success: boolean; template: ImportMappingTemplate }>(
      `/api/imports/${sessionId}/mapping/templates`,
      { name, supplier_id: supplierId }
    );
    return data.template;
  },

  applyTemplate: async (sessionId: number, templateId: number) => {
    const { data } = await apiClient.post<{ success: boolean; mapping: ImportMapping }>(
      `/api/imports/${sessionId}/mapping/templates/${templateId}/apply`
    );
    return data.mapping;
  },

  validate: async (sessionId: number) => {
    const { data } = await apiClient.post<{ success: boolean; validation: ImportValidation }>(`/api/imports/${sessionId}/validate`);
    return data.validation;
  },

  getValidation: async (sessionId: number) => {
    const { data } = await apiClient.get<{ success: boolean; validation: ImportValidation }>(`/api/imports/${sessionId}/validation`);
    return data.validation;
  },

  getPreview: async (sessionId: number, limit = 200, offset = 0) => {
    const { data } = await apiClient.get<{ success: boolean; validation_id: number; summary: ImportValidation["summary"]; rows: ImportPreviewRow[] }>(
      `/api/imports/${sessionId}/preview`,
      { params: { limit, offset } }
    );
    return data;
  },

  commit: async (sessionId: number) => {
    const { data } = await apiClient.post<{ success: boolean; execution: ImportExecution }>(`/api/imports/${sessionId}/commit`);
    return data.execution;
  },

  getExecution: async (sessionId: number) => {
    const { data } = await apiClient.get<{ success: boolean; execution: ImportExecution }>(`/api/imports/${sessionId}/execution`);
    return data.execution;
  },

  rollback: async (executionId: number) => {
    const { data } = await apiClient.post<{ success: boolean; execution: ImportExecution }>(`/api/imports/executions/${executionId}/rollback`);
    return data.execution;
  },
};
