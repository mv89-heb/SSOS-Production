"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { useAuth } from "@/providers/auth-provider";
import { permissions } from "@/lib/permissions";
import { WizardStepper, WizardStepDef } from "@/components/import-wizard/wizard-stepper";
import { UploadStep } from "@/components/import-wizard/upload-step";
import { ScanStep } from "@/components/import-wizard/scan-step";
import { MappingStep } from "@/components/import-wizard/mapping-step";
import { ValidationStep } from "@/components/import-wizard/validation-step";
import { PreviewStep } from "@/components/import-wizard/preview-step";
import { PlanImportStep } from "@/components/import-wizard/plan-import-step";
import { ReportStep } from "@/components/import-wizard/report-step";
import { useImportSession } from "@/hooks/use-imports";
import { ImportValidation, ImportExecution } from "@/types";

const STEPS: WizardStepDef[] = [
  { key: "upload", label: "העלאה" },
  { key: "scan", label: "סריקה" },
  { key: "mapping", label: "מיפוי עמודות" },
  { key: "validation", label: "בדיקת תקינות" },
  { key: "preview", label: "תצוגה מקדימה" },
  { key: "plan", label: "תוכנית ייבוא" },
  { key: "report", label: "דוח סיום" },
];

export default function ImportWizardPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [stepIndex, setStepIndex] = useState(0);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [validation, setValidation] = useState<ImportValidation | null>(null);
  const [execution, setExecution] = useState<ImportExecution | null>(null);
  const { data: session } = useImportSession(sessionId);

  if (!permissions.canManageImports(user)) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
        אין לך הרשאה לגשת לאשף הייבוא. נדרשת הרשאת מנהל.
      </div>
    );
  }

  const resetWizard = () => {
    setStepIndex(0);
    setSessionId(null);
    setValidation(null);
    setExecution(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.push("/dashboard/settings")}
          className="text-slate-400 hover:text-slate-700"
          aria-label="חזרה להגדרות"
        >
          <ArrowRight size={20} />
        </button>
        <h1 className="text-2xl font-bold text-slate-900">אשף ייבוא מחירוני ספקים</h1>
      </div>

      <div className="overflow-x-auto pb-1">
        <WizardStepper steps={STEPS} currentIndex={stepIndex} />
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        {stepIndex === 0 && (
          <UploadStep
            onUploaded={(id) => {
              setSessionId(id);
              setStepIndex(1);
            }}
          />
        )}

        {stepIndex === 1 && sessionId && (
          <ScanStep sessionId={sessionId} onScanned={() => setStepIndex(2)} onBack={() => setStepIndex(0)} />
        )}

        {stepIndex === 2 && sessionId && (
          <MappingStep sessionId={sessionId} onApproved={() => setStepIndex(3)} onBack={() => setStepIndex(1)} />
        )}

        {stepIndex === 3 && sessionId && (
          <ValidationStep
            sessionId={sessionId}
            onValidated={(v) => {
              setValidation(v);
              setStepIndex(4);
            }}
            onBack={() => setStepIndex(2)}
          />
        )}

        {stepIndex === 4 && sessionId && (
          <PreviewStep sessionId={sessionId} onNext={() => setStepIndex(5)} onBack={() => setStepIndex(3)} />
        )}

        {stepIndex === 5 && sessionId && validation && (
          <PlanImportStep
            sessionId={sessionId}
            validation={validation}
            onImported={(exec) => {
              setExecution(exec);
              setStepIndex(6);
            }}
            onBack={() => setStepIndex(4)}
          />
        )}

        {stepIndex === 6 && execution && <ReportStep session={session} execution={execution} onStartOver={resetWizard} />}
      </div>
    </div>
  );
}
