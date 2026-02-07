import React, { useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import { Briefcase, TrendingUp } from "lucide-react";
import { toast } from "@/hooks/use-toast";
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
  const scoredJd = useMemo(() => {
    return jobDescriptions.map((jd) => {
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
  }, [jobDescriptions, activeCandidate]);

  const top20 = useMemo(
    () =>
      scoredJd
        .slice()
        .sort((a, b) => b.score - a.score)
        .slice(0, 20),
    [scoredJd]
  );

  // Stato per score reali calcolati dal backend matcher
  const [realScores, setRealScores] = useState<Record<string, number>>({});
  const [loadingMatchId, setLoadingMatchId] = useState<string | null>(null);

  interface XAIReason {
    text?: string;
    evidence?: string;
    contribution?: number;
  }

  interface XAIRisk {
    text?: string;
    evidence?: string;
    contribution?: number;
  }

  interface XAIData {
    quality_label?: string;
    top_reasons?: XAIReason[];
    main_risks?: XAIRisk[];
    evidence?: Record<string, unknown>;
  }

  const [openDialog, setOpenDialog] = useState<string | null>(null);
  const [xaiData, setXaiData] = useState<XAIData | null>(null);
  const [loadingXai, setLoadingXai] = useState(false);
  const [applyDialogOpen, setApplyDialogOpen] = useState(false);
  const [applyJob, setApplyJob] = useState<JobDescription | null>(null);
  const [applyMessage, setApplyMessage] = useState("");
  const [sendingApplication, setSendingApplication] = useState(false);

  const extractScore = (result: unknown): number | null => {
    if (!result || typeof result !== "object") return null;
    const res = result as Record<string, unknown>;

    if (typeof res.candidate === "object" && res.candidate !== null) {
      const candidate = res.candidate as Record<string, unknown>;
      if (typeof candidate.score === "number") return candidate.score;
    }
    if (typeof res.quality_assessment === "object" && res.quality_assessment !== null) {
      const qa = res.quality_assessment as Record<string, unknown>;
      if (typeof qa.final_score === "number") return qa.final_score;
    }
    if (typeof (res as any).score === "number") return (res as any).score as number;
    if (typeof (res as any).overall_score === "number") return (res as any).overall_score as number;
    return null;
  };

  const handleCalcolaMatch = async (jdId: string) => {
    if (!activeCandidate) {
      toast({
        title: "Nessun candidato attivo",
        description: "Seleziona prima un candidato.",
        variant: "destructive",
      });
      return;
    }
    setLoadingMatchId(jdId);
    try {
      const response = await fetch("/api/match_cv_jd", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cv_path: activeCandidate.id, jd_path: jdId }),
      });
      if (!response.ok) throw new Error(await response.text());
      const result = await response.json();
      const rawScore = extractScore(result);
      const score = rawScore !== null ? Math.round(rawScore * 100) : 0;
      setRealScores((prev) => ({ ...prev, [jdId]: score }));
    } catch (err) {
      console.error("Errore match (PipelineSection)", err);
      toast({
        title: "Errore match",
        description: "Si è verificato un problema durante il calcolo.",
        variant: "destructive",
      });
    } finally {
      setLoadingMatchId(null);
    }
  };

  const handleDiscoverMore = async (jdId: string) => {
    if (!activeCandidate) {
      toast({
        title: "Nessun candidato attivo",
        description: "Seleziona prima un candidato.",
        variant: "destructive",
      });
      return;
    }
    setLoadingXai(true);
    setOpenDialog(jdId);
    try {
      const response = await fetch("/api/match_cv_jd", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cv_path: activeCandidate.id, jd_path: jdId }),
      });
      if (!response.ok) {
        const text = await response.text();
        console.error("Errore risposta matcher (PipelineSection DiscoverMore)", text);
        throw new Error("Errore dal servizio di matching");
      }
      const result = (await response.json()) as Record<string, unknown>;

      let candidateXai: XAIData | null = null;
      if (result.candidate && typeof result.candidate === "object") {
        const candidate = result.candidate as Record<string, unknown>;
        if (candidate.xai && typeof candidate.xai === "object") {
          candidateXai = candidate.xai as XAIData;
        }
      }
      if (!candidateXai && result.xai && typeof result.xai === "object") {
        candidateXai = result.xai as XAIData;
      }
      if (!candidateXai) {
        candidateXai = result as XAIData;
      }

      setXaiData(candidateXai);
      const rawScore = extractScore(result);
      if (rawScore !== null) {
        const pct = Math.round(rawScore * 100);
        setRealScores((prev) => ({ ...prev, [jdId]: pct }));
      }
    } catch (err) {
      console.error("Errore match (PipelineSection DiscoverMore)", err);
      toast({
        title: "Errore match",
        description: "Si è verificato un problema durante il calcolo.",
        variant: "destructive",
      });
      setXaiData(null);
    } finally {
      setLoadingXai(false);
    }
  };

  const handleApply = async (jd: JobDescription) => {
    if (!activeCandidate) {
      toast({
        title: "Nessun candidato attivo",
        description: "Seleziona o crea prima un profilo candidato.",
        variant: "destructive",
      });
      return;
    }
    const defaultMessage = `Ciao, mi piacerebbe candidarmi per la posizione "${jd.title}". Credo che il mio profilo sia in linea con quanto richiesto e sarei felice di approfondire in una call.`;
    setApplyJob(jd);
    setApplyMessage(defaultMessage);
    setApplyDialogOpen(true);
  };

  const handleConfirmApply = async () => {
    if (!applyJob || !activeCandidate) return;
    const message = applyMessage.trim();
    if (!message) {
      toast({
        title: "Messaggio vuoto",
        description: "Scrivi un breve messaggio di presentazione prima di inviare.",
        variant: "destructive",
      });
      return;
    }

    try {
      setSendingApplication(true);
      const res = await fetch("/api/contact/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jd_id: applyJob.jd_id, message }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Errore dal server");
      }
      toast({
        title: "Candidatura inviata",
        description: "La tua candidatura è stata inviata all'azienda.",
      });
      setApplyDialogOpen(false);
      setApplyJob(null);
      setApplyMessage("");
    } catch (err) {
      console.error("Errore invio candidatura (PipelineSection)", err);
      toast({
        title: "Errore candidatura",
        description: "Non è stato possibile inviare la candidatura. Riprova più tardi.",
        variant: "destructive",
      });
    } finally {
      setSendingApplication(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Briefcase className="h-5 w-5 text-primary" />
            Lavori consigliati per te (Top 20)
          </h3>
          <Badge variant="outline">{top20.length} lavori</Badge>
        </div>
        {!activeCandidate && (
          <p className="text-sm text-muted-foreground mb-2">
            Nessun candidato attivo. Seleziona o crea un candidato per vedere le offerte consigliate.
          </p>
        )}
        {top20.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nessuna Job Description disponibile al momento.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {top20.map(({ jd }) => {
              const mustRequirements = Array.isArray(jd.requirements) ? jd.requirements : [];
              const niceRequirements = Array.isArray(jd.nice_to_have) ? jd.nice_to_have : [];
              const realScore = realScores[jd.jd_id];
              return (
                <Card key={jd.jd_id} className="p-4 border-2 border-muted shadow-sm flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="inline-flex items-center px-2 py-0.5 rounded bg-muted text-xs font-medium text-muted-foreground mr-2">
                        <Briefcase className="h-4 w-4 mr-1 inline" /> job
                      </span>
                      <span className="ml-auto text-xs font-semibold text-primary">
                        Score match: {realScore !== undefined ? realScore : "--"}%
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold text-base">{jd.title}</span>
                    </div>
                    <div className="text-xs text-muted-foreground mb-1">
                      {(jd.company || "Azienda")} &middot; {jd.location?.city || ""} {jd.location?.country ? "/ " + jd.location.country : ""} {jd.location?.remote ? " / Remote" : ""}
                    </div>
                    <div className="mb-2 text-xs text-muted-foreground line-clamp-2">{jd.description}</div>
                    <div className="mb-2">
                      <span className="font-semibold text-xs">Requisiti:</span>
                      <ul className="list-disc ml-4 mt-1">
                        {mustRequirements.slice(0, 3).map((req, i) => (
                          <li key={i} className="text-xs text-emerald-700">
                            {req}
                          </li>
                        ))}
                        {niceRequirements.slice(0, 2).map((req, i) => (
                          <li key={i} className="text-xs text-blue-700">
                            {req}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                  <div className="flex gap-2 mt-2">
                    {realScore === undefined ? (
                      <Button
                        size="sm"
                        className="flex-1"
                        variant="default"
                        onClick={() => handleCalcolaMatch(jd.jd_id)}
                        disabled={loadingMatchId === jd.jd_id || loadingXai}
                      >
                        {loadingMatchId === jd.jd_id || loadingXai ? "Calcolo..." : "Calcola match"}
                      </Button>
                    ) : (
                      <Dialog
                        open={openDialog === jd.jd_id}
                        onOpenChange={(open) => {
                          if (!open) {
                            setOpenDialog(null);
                            setXaiData(null);
                          }
                        }}
                      >
                        <DialogTrigger asChild>
                          <Button
                            size="sm"
                            className="flex-1"
                            variant="default"
                            onClick={() => handleDiscoverMore(jd.jd_id)}
                          >
                            Scopri di più
                          </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
                          <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                              <TrendingUp className="h-5 w-5 text-primary" />
                              Spiegazione del Match (XAI)
                            </DialogTitle>
                            <DialogDescription>
                              Analisi dettagliata della compatibilità tra il tuo profilo e questa posizione
                            </DialogDescription>
                          </DialogHeader>
                          {loadingXai && <div>Caricamento...</div>}
                          {!loadingXai && xaiData && (
                            <div className="space-y-4 text-sm">
                              <div className="mb-3">
                                <strong>Valutazione complessiva:</strong> {xaiData.quality_label || "-"}
                              </div>
                              {xaiData.top_reasons && xaiData.top_reasons.length > 0 && (
                                <div className="mb-2">
                                  <strong>Motivi principali del match:</strong>
                                  <ul className="list-disc ml-5 mt-1">
                                    {xaiData.top_reasons.map((r, i) => (
                                      <li key={i} className="mb-1">
                                        <span className="font-semibold text-green-700">{r.text || ""}</span>
                                        {r.evidence && (
                                          <span className="ml-2 text-muted-foreground">({r.evidence})</span>
                                        )}
                                        {typeof r.contribution === "number" && (
                                          <span className="ml-2 text-xs text-green-700">
                                            +{Math.round(r.contribution * 100)}%
                                          </span>
                                        )}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                              {xaiData.main_risks && xaiData.main_risks.length > 0 && (
                                <div className="mb-2">
                                  <strong>Rischi/GAP principali:</strong>
                                  <ul className="list-disc ml-5 mt-1">
                                    {xaiData.main_risks.map((r, i) => (
                                      <li key={i} className="mb-1">
                                        <span className="font-semibold text-red-700">{r.text || ""}</span>
                                        {r.evidence && (
                                          <span className="ml-2 text-muted-foreground">({r.evidence})</span>
                                        )}
                                        {typeof r.contribution === "number" && (
                                          <span className="ml-2 text-xs text-red-700">
                                            -{Math.abs(Math.round(r.contribution * 100))}%
                                          </span>
                                        )}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                              {xaiData.evidence && (
                                <div className="mt-3">
                                  <strong>Riepilogo evidenze:</strong>
                                  <ul className="list-disc ml-5 mt-1">
                                    {Object.entries(xaiData.evidence).map(([k, v], i) => (
                                      <li key={i}>
                                        <span className="font-semibold">{k}:</span> {String(v)}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>
                          )}
                          {!loadingXai && !xaiData && <div>Nessun dato XAI disponibile.</div>}
                          <DialogClose asChild>
                            <Button variant="outline">Chiudi</Button>
                          </DialogClose>
                        </DialogContent>
                      </Dialog>
                    )}
                    <Button
                      size="sm"
                      className="flex-1"
                      variant="outline"
                      onClick={() => handleApply(jd)}
                    >
                      Candidati
                    </Button>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </Card>
      <Dialog
        open={applyDialogOpen}
        onOpenChange={(open) => {
          setApplyDialogOpen(open);
          if (!open) {
            setApplyJob(null);
            setApplyMessage("");
          }
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Invia candidatura</DialogTitle>
            <DialogDescription>
              Scrivi un breve messaggio di presentazione che accompagnerà la tua candidatura.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            {applyJob && (
              <p className="text-xs text-muted-foreground">
                Posizione: <span className="font-semibold">{applyJob.title}</span>
              </p>
            )}
            <div className="space-y-2">
              <Label htmlFor="apply-message">Messaggio</Label>
              <Textarea
                id="apply-message"
                rows={5}
                value={applyMessage}
                onChange={(e) => setApplyMessage(e.target.value)}
                placeholder="Presentati brevemente, evidenzia le competenze più rilevanti per questa posizione e proponi un eventuale prossimo passo (es. call)."
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setApplyDialogOpen(false);
                setApplyJob(null);
                setApplyMessage("");
              }}
            >
              Annulla
            </Button>
            <Button
              type="button"
              onClick={handleConfirmApply}
              disabled={sendingApplication}
            >
              {sendingApplication ? "Invio..." : "Invia candidatura"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};