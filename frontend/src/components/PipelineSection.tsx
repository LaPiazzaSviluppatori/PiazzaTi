import { Card } from "@/components/ui/card";
import { AuditLogEntry, Candidate, JobDescription } from "@/types";
import GestisciCandidature from "./GestisciCandidature";
import { ArrowRight, Database, FileText, Filter, MessageSquare, Shield } from "lucide-react";

type PipelineMode = "candidate" | "company";
interface PipelineSectionProps {
  candidates: Candidate[];
  jobDescriptions: JobDescription[];
  auditLog: AuditLogEntry[];
  deiMode: boolean;
  isParsing?: boolean;
  mode?: PipelineMode;
  onCreateJd?: (jd: Omit<JobDescription, "id" | "createdAt">) => void;
  companyName?: string | null;
}

export const PipelineSection = ({ candidates, jobDescriptions, auditLog, deiMode, isParsing, mode = "candidate", onCreateJd, companyName }: PipelineSectionProps) => {
  const pipelineStagesCandidate = [
    { name: "CV Ingest", icon: FileText, input: "CV, Portfolio", output: "Profilo Strutturato" },
    { name: "Screening", icon: Filter, input: "Profili + JD", output: "Punteggi Match" },
    { name: "Feedback", icon: MessageSquare, input: "Decision", output: "Feedback Template" },
    { name: "Audit", icon: Shield, input: "Azioni", output: "Compliance Log" },
  ];
  const pipelineStagesJD = [
    { name: "JD Creation", icon: Database, input: "Job Description", output: "Requisiti Strutturati" },
    { name: "Screening", icon: Filter, input: "Profili + JD", output: "Punteggi Match" },
    { name: "Feedback", icon: MessageSquare, input: "Decision", output: "Feedback Template" },
    { name: "Audit", icon: Shield, input: "Azioni", output: "Compliance Log" },
  ];
  const pipelineStages = mode === "company" ? pipelineStagesJD : pipelineStagesCandidate;

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-6">{mode === 'company' ? 'Gestisci Job Description' : 'Pipeline del Processo'}</h3>
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
          {pipelineStages.map((stage, index) => {
            const isGlow = (mode === "candidate" && stage.name === "CV Ingest" && isParsing) ||
              (mode === "company" && stage.name === "JD Creation" && isParsing);
            return (
              <div key={stage.name} className="flex items-center gap-4 w-full md:w-auto">
                <div className="flex flex-col items-center gap-2 flex-1">
                  <div className={`flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 ${isGlow ? "glow-anim" : ""}`}> 
                    <stage.icon className="h-8 w-8 text-primary" />
                  </div>
                  <div className="text-center">
                    <p className="font-semibold text-sm flex items-center justify-center gap-2">
                      {stage.name}
                    </p>
                    {isGlow && (
                      <span className="inline-block mt-1 px-2 py-0.5 rounded bg-primary text-primary-foreground text-xs font-bold">Parsing...</span>
                    )}
                    <p className="text-xs text-muted-foreground mt-1">
                      <span className="font-medium">In:</span> {stage.input}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      <span className="font-medium">Out:</span> {stage.output}
                    </p>
                  </div>
                </div>
                {index < pipelineStages.length - 1 && (
                  <ArrowRight className="h-6 w-6 text-muted-foreground hidden md:block" />
                )}
              </div>
            );
          })}
        </div>
        <style>{`
          .glow-anim {
            box-shadow: 0 0 0 0 rgba(219,39,119,0.7), 0 0 16px 8px rgba(219,39,119,0.5);
            animation: glow-blink 1s infinite alternate;
          }
          @keyframes glow-blink {
            0% { box-shadow: 0 0 0 0 rgba(219,39,119,0.7), 0 0 16px 8px rgba(219,39,119,0.5); }
            100% { box-shadow: 0 0 0 8px rgba(219,39,119,0.1), 0 0 32px 16px rgba(219,39,119,0.7); }
          }
        `}</style>
      </Card>
      {mode === "company" && (
          <div>
            <GestisciCandidature
              onCreateJd={onCreateJd}
              jobDescriptions={jobDescriptions}
              companyName={companyName}
            />
          </div>
        )}
    </div>
  );
};