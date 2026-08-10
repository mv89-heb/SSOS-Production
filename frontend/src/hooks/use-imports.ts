"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { importService, MappingDecision } from "@/services/import-service";

const sessionKey = (id: number) => ["import-session", id] as const;
const sessionsKey = ["import-sessions"] as const;
const analysisKey = (id: number) => ["import-analysis", id] as const;
const mappingKey = (id: number) => ["import-mapping", id] as const;
const templatesKey = (id: number) => ["import-templates", id] as const;
const validationKey = (id: number) => ["import-validation", id] as const;
const previewKey = (id: number) => ["import-preview", id] as const;
const executionKey = (id: number) => ["import-execution", id] as const;

export function useImportSessions() {
  return useQuery({ queryKey: sessionsKey, queryFn: importService.list });
}

export function useImportSession(sessionId: number | null) {
  return useQuery({
    queryKey: sessionKey(sessionId ?? -1),
    queryFn: () => importService.get(sessionId as number),
    enabled: sessionId != null,
  });
}

export function useUploadImport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, supplierId, sheetName }: { file: File; supplierId?: number; sheetName?: string }) =>
      importService.upload(file, { supplierId, sheetName }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: sessionsKey }),
  });
}

export function useImportRows(sessionId: number | null, limit = 50) {
  return useQuery({
    queryKey: ["import-rows", sessionId, limit],
    queryFn: () => importService.getRows(sessionId as number, limit),
    enabled: sessionId != null,
  });
}

export function useAnalyzeImport(sessionId: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => importService.analyze(sessionId as number),
    onSuccess: (analysis) => {
      queryClient.setQueryData(analysisKey(sessionId as number), analysis);
      queryClient.invalidateQueries({ queryKey: sessionKey(sessionId as number) });
    },
  });
}

export function useImportAnalysis(sessionId: number | null) {
  return useQuery({
    queryKey: analysisKey(sessionId ?? -1),
    queryFn: () => importService.getAnalysis(sessionId as number),
    enabled: sessionId != null,
  });
}

export function useImportMapping(sessionId: number | null) {
  return useQuery({
    queryKey: mappingKey(sessionId ?? -1),
    queryFn: () => importService.getMapping(sessionId as number),
    enabled: sessionId != null,
  });
}

export function useUpdateMapping(sessionId: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (decisions: MappingDecision[]) => importService.updateMapping(sessionId as number, decisions),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: mappingKey(sessionId as number) }),
  });
}

export function useApproveMapping(sessionId: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => importService.approveMapping(sessionId as number),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: mappingKey(sessionId as number) }),
  });
}

export function useImportTemplates(sessionId: number | null) {
  return useQuery({
    queryKey: templatesKey(sessionId ?? -1),
    queryFn: () => importService.listTemplates(sessionId as number),
    enabled: sessionId != null,
  });
}

export function useSaveTemplate(sessionId: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, supplierId }: { name: string; supplierId?: number }) =>
      importService.saveTemplate(sessionId as number, name, supplierId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: templatesKey(sessionId as number) }),
  });
}

export function useApplyTemplate(sessionId: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (templateId: number) => importService.applyTemplate(sessionId as number, templateId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: mappingKey(sessionId as number) }),
  });
}

export function useValidateImport(sessionId: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => importService.validate(sessionId as number),
    onSuccess: (validation) => {
      queryClient.setQueryData(validationKey(sessionId as number), validation);
      queryClient.invalidateQueries({ queryKey: previewKey(sessionId as number) });
    },
  });
}

export function useImportValidationDetails(sessionId: number | null, enabled = true) {
  return useQuery({
    queryKey: [...validationKey(sessionId ?? -1), "details"],
    queryFn: () => importService.getValidation(sessionId as number),
    enabled: sessionId != null && enabled,
    retry: false,
  });
}

export function useImportPreview(sessionId: number | null, enabled = true) {
  return useQuery({
    queryKey: previewKey(sessionId ?? -1),
    queryFn: () => importService.getPreview(sessionId as number, 500),
    enabled: sessionId != null && enabled,
    retry: false,
  });
}

export function useCommitImport(sessionId: number | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => importService.commit(sessionId as number),
    onSuccess: (execution) => {
      queryClient.setQueryData(executionKey(sessionId as number), execution);
      queryClient.invalidateQueries({ queryKey: ["suppliers"] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
  });
}

export function useRollbackExecution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (executionId: number) => importService.rollback(executionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["suppliers"] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
  });
}
