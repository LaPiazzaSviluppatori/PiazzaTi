import { useMemo } from "react";
import { Card } from "@/components/ui/card";
import { AuditLogEntry, Candidate, JobDescription } from "@/types";
import GestisciCandidature from "./GestisciCandidature";

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

type CompanyApplication = {
  id: string;
  timestamp: string;
  jd_id: string;
  candidate_user_id: string;
  candidate_name?: string | null;
  candidate_email?: string | null;
  message: string;
  company?: string | null;
};

interface PipelineSectionExtendedProps extends PipelineSectionProps {
  companyApplications?: CompanyApplication[];
}

export const PipelineSection = ({ candidates, jobDescriptions, auditLog, deiMode, isParsing, mode = "candidate", onCreateJd, companyName, companyApplications = [] }: PipelineSectionExtendedProps) => {
  const isCompanyMode = mode === "company";

  // Vista COMPANY: solo gestione JD + Top 20 candidati
  if (isCompanyMode) {
    return (
      <div className="space-y-6">
        <GestisciCandidature
          onCreateJd={onCreateJd}
          jobDescriptions={jobDescriptions}
          companyName={companyName}
        />
        {companyApplications.length > 0 && (
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4">Candidature ricevute</h3>
            <div className="space-y-3 max-h-80 overflow-y-auto pr-1 text-sm">
              {companyApplications.map((app) => {
                const jd = jobDescriptions.find((j) => j.jd_id === app.jd_id);
                return (
                  <div key={app.id} className="border rounded-lg px-3 py-2 bg-muted/50">
                    <div className="flex flex-col mb-1">
                      <span className="font-semibold">Candidato</span>
                      {app.candidate_email && (
                        <span className="text-xs text-muted-foreground">{app.candidate_email}</span>
                      )}
                    </div>
                    {jd && (
                      <div className="text-xs text-muted-foreground mb-1">
                        Per la posizione: {jd.title}
                      </div>
                    )}
                    <p className="text-xs whitespace-pre-wrap">{app.message}</p>
                  </div>
                );
              })}
            </div>
          </Card>
        )}
      </div>
    );
  }

  // Vista CANDIDATE: Top 20 JD consigliate (niente pipeline grafica)
  const activeCandidate = candidates[0];

  const scoredJd = jobDescriptions.map((jd) => {
    if (!activeCandidate) {
      return { jd, score: 0 };
    }
    const mustRequirements = Array.isArray(jd.requirements) ? jd.requirements : [];
    const niceRequirements = Array.isArray(jd.nice_to_have) ? jd.nice_to_have : [];
    const candidateSkillNames = activeCandidate.skills.map((s) => s.name.toLowerCase());
    const mustMatch = mustRequirements.filter((req) =>
      candidateSkillNames.some((skill) => skill.includes(req.toLowerCase()))
    ).length;
    const niceMatch = niceRequirements.filter((req) =>
      candidateSkillNames.some((skill) => skill.includes(req.toLowerCase()))
    ).length;
    const mustPercentage = mustRequirements.length > 0 ? (mustMatch / mustRequirements.length) * 100 : 0;
    const nicePercentage = niceRequirements.length > 0 ? (niceMatch / niceRequirements.length) * 100 : 0;
    const score = Math.round(mustPercentage * 0.7 + nicePercentage * 0.3);
    return { jd, score };
  });

  const top20 = scoredJd
    .sort((a, b) => b.score - a.score)
    .slice(0, 20);

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Top 20 JD consigliate</h3>
        {!activeCandidate && (
          <p className="text-sm text-muted-foreground mb-2">
            Nessun candidato attivo. Seleziona o crea un candidato per vedere le offerte consigliate.
          </p>
        )}
        {top20.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nessuna Job Description disponibile al momento.</p>
        ) : (
          <div className="space-y-3">
            {top20.map(({ jd, score }) => (
              <div key={jd.jd_id} className="flex items-start justify-between border rounded-lg p-3">
                <div className="space-y-1">
                  <p className="font-medium text-sm">{jd.title}</p>
                  {jd.company && <p className="text-xs text-muted-foreground">{jd.company}</p>}
                  {jd.location && (
                    <p className="text-xs text-muted-foreground">
                      {jd.location.city ? `${jd.location.city}, ` : ""}
                      {jd.location.country || ""}
                      {jd.location.remote && " · Remote"}
                    </p>
                  )}
                </div>
                <div className="flex flex-col items-end gap-1">
                  <span className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-semibold">
                    Match {score}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
};