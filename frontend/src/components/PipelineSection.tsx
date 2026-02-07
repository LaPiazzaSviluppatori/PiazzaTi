import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { AuditLogEntry, Candidate, JobDescription } from "@/types";
import GestisciCandidature from "./GestisciCandidature";
import { ArrowRight, FileText, Filter, MessageSquare, Shield } from "lucide-react";

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
  const isCompanyMode = mode === "company";
  const pipelineStagesCandidate = [
    { name: "CV Ingest", icon: FileText, input: "CV, Portfolio", output: "Profilo Strutturato" },
    { name: "Screening", icon: Filter, input: "Profili + JD", output: "Punteggi Match" },
    { name: "Feedback", icon: MessageSquare, input: "Decision", output: "Feedback Template" },
    { name: "Audit", icon: Shield, input: "Azioni", output: "Compliance Log" },
  ];
  const pipelineStages = pipelineStagesCandidate; // usato solo per la vista candidato

  // --- Stato e derivate per vista COMPANY (Top 20 candidati per JD) ---
  const [selectedJdIdCompany, setSelectedJdIdCompany] = useState<string | null>(null);

  const myJobDescriptions = useMemo(
    () =>
      isCompanyMode
        ? jobDescriptions.filter((jd) => !companyName || jd.company === companyName)
        : [],
    [isCompanyMode, jobDescriptions, companyName]
  );

  useEffect(() => {
    if (!isCompanyMode) return;
    if (myJobDescriptions.length === 0) {
      setSelectedJdIdCompany(null);
      return;
    }
    // Se non c'è selezione o la JD selezionata non esiste più, imposta la prima
    const exists = myJobDescriptions.some((jd) => jd.jd_id === selectedJdIdCompany);
    if (!selectedJdIdCompany || !exists) {
      setSelectedJdIdCompany(myJobDescriptions[0].jd_id);
    }
  }, [isCompanyMode, myJobDescriptions, selectedJdIdCompany]);

  const selectedJdCompany = useMemo(
    () => myJobDescriptions.find((jd) => jd.jd_id === selectedJdIdCompany) || null,
    [myJobDescriptions, selectedJdIdCompany]
  );

  const topCandidatesForSelectedJd = useMemo(() => {
    if (!isCompanyMode || !selectedJdCompany) return [];
    const mustRequirements = Array.isArray(selectedJdCompany.requirements) ? selectedJdCompany.requirements : [];
    const niceRequirements = Array.isArray(selectedJdCompany.nice_to_have) ? selectedJdCompany.nice_to_have : [];

    return candidates
      .map((candidate) => {
        const candidateSkillNames = candidate.skills.map((s) => s.name.toLowerCase());
        const mustMatch = mustRequirements.filter((req) =>
          candidateSkillNames.some((skill) => skill.includes(req.toLowerCase()))
        ).length;
        const niceMatch = niceRequirements.filter((req) =>
          candidateSkillNames.some((skill) => skill.includes(req.toLowerCase()))
        ).length;
        const mustPercentage = mustRequirements.length > 0 ? (mustMatch / mustRequirements.length) * 100 : 0;
        const nicePercentage = niceRequirements.length > 0 ? (niceMatch / niceRequirements.length) * 100 : 0;
        const score = Math.round(mustPercentage * 0.7 + nicePercentage * 0.3);
        return { candidate, score };
      })
      .sort((a, b) => b.score - a.score)
      .slice(0, 20);
  }, [isCompanyMode, selectedJdCompany, candidates]);

  // Vista COMPANY: solo gestione JD + Top 20 candidati
  if (isCompanyMode) {
    return (
      <div className="space-y-6">
        <GestisciCandidature
          onCreateJd={onCreateJd}
          jobDescriptions={jobDescriptions}
          companyName={companyName}
        />
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">Top 20 candidati per le tue JD</h3>
          {myJobDescriptions.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Non hai ancora Job Description salvate. Crea una JD per vedere i candidati consigliati.
            </p>
          ) : (
            <>
              <div className="mb-4 flex flex-col sm:flex-row gap-2 sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm font-medium">Seleziona una JD</p>
                  <p className="text-xs text-muted-foreground">
                    La lista mostra i candidati più affini in base alle skill.
                  </p>
                </div>
                <select
                  className="mt-1 sm:mt-0 border rounded px-2 py-1 text-sm"
                  value={selectedJdIdCompany || ""}
                  onChange={(e) => setSelectedJdIdCompany(e.target.value || null)}
                >
                  {myJobDescriptions.map((jd) => (
                    <option key={jd.jd_id} value={jd.jd_id}>
                      {jd.title}
                    </option>
                  ))}
                </select>
              </div>
              {!selectedJdCompany ? (
                <p className="text-sm text-muted-foreground">
                  Seleziona una Job Description per vedere i candidati consigliati.
                </p>
              ) : topCandidatesForSelectedJd.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Nessun candidato disponibile al momento.
                </p>
              ) : (
                <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                  {topCandidatesForSelectedJd.map(({ candidate, score }, idx) => (
                    <div
                      key={candidate.id}
                      className="flex items-center justify-between border rounded-lg px-3 py-2 text-sm"
                    >
                      <div className="space-y-0.5">
                        <p className="font-medium">
                          {idx + 1}. {candidate.name || "Candidato"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {candidate.location || "Località non specificata"}
                        </p>
                      </div>
                      <span className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-semibold">
                        Match {score}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </Card>
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
                  <p className="text-xs text-muted-foreground">
                    {jd.location.city ? `${jd.location.city}, ` : ""}{jd.location.country}
                    {jd.location.remote && " · Remote"}
                  </p>
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