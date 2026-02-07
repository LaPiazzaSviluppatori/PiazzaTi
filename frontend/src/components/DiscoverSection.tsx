import React from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from "@/components/ui/dialog";
import { Candidate, Opportunity, JobDescription } from "@/types";

import { Users, Lightbulb, Briefcase, Plus, ExternalLink, TrendingUp, Calendar } from "lucide-react";
import { toast } from "@/hooks/use-toast";

interface DiscoverSectionProps {
  suggestedProfiles: Candidate[];
  opportunities: Opportunity[];
  jobDescriptions: JobDescription[];
  activeCandidate?: Candidate;
  onConnect: (candidateId: string) => void;
  onAddOpportunity: () => void;
  onEvaluateMatch: (jdId: string) => void;
  role: "candidate" | "company";
}

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

export const DiscoverSection = ({
  suggestedProfiles,
  opportunities,
  jobDescriptions,
  activeCandidate,
  onConnect,
  onAddOpportunity,
  onEvaluateMatch,
  role,
}: DiscoverSectionProps) => {
  const getOpportunityIcon = (type: string) => {
    switch (type) {
      case "grant":
        return "💰";
      case "hackathon":
        return "🏆";
      case "course":
        return "📚";
      case "fellowship":
        return "🎓";
      default:
        return "✨";
    }
  };

  // Mostra tutte le JD senza score mock, solo con score reale (se calcolato)
  let matchedJd: Array<{ jd: JobDescription; mustRequirements: string[]; niceRequirements: string[] }> = [];
  if (activeCandidate) {
    matchedJd = jobDescriptions
      .map((jd) => {
        const mustRequirements = Array.isArray(jd.requirements) ? jd.requirements : [];
        const niceRequirements = Array.isArray(jd.nice_to_have) ? jd.nice_to_have : [];
        return { jd, mustRequirements, niceRequirements };
      });
  }

  const [openDialog, setOpenDialog] = React.useState<string | null>(null);
  const [xaiData, setXaiData] = React.useState<XAIData | null>(null);
  const [loadingXai, setLoadingXai] = React.useState(false);
  // Stato per score reali calcolati dal backend
  const [realScores, setRealScores] = React.useState<Record<string, number>>({});

  // Estrae lo score numerico dalla risposta del matcher
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
    if (typeof res.score === "number") return res.score;
    if (typeof res.overall_score === "number") return res.overall_score;
    return null;
  };

  // Funzione per calcolare il match reale (fase 1)
  const handleCalcolaMatch = async (jdId: string) => {
    if (!activeCandidate) {
      toast({ title: "Nessun candidato attivo", description: "Seleziona prima un candidato.", variant: "destructive" });
      return;
    }
    setLoadingXai(true);
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
      console.error("Errore match (CalcolaMatch)", err);
      toast({
        title: "Errore match",
        description: "Si è verificato un problema durante il calcolo.",
        variant: "destructive",
      });
    } finally {
      setLoadingXai(false);
    }
  };

  const handleDiscoverMore = async (jdId: string) => {
    if (!activeCandidate) {
      toast({ title: "Nessun candidato attivo", description: "Seleziona prima un candidato.", variant: "destructive" });
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
        console.error("Errore risposta matcher (DiscoverMore)", text);
        throw new Error("Errore dal servizio di matching");
      }
      const result = await response.json() as Record<string, unknown>;
      
      // XAI: preferisci il blocco xai annidato nel candidato, se presente
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
      const score = rawScore !== null ? Math.round(rawScore * 100) : 0;
      onEvaluateMatch(jdId);
    } catch (err) {
      console.error("Errore match (DiscoverMore)", err);
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

  return (
    <div className="space-y-6">
      {/* Se azienda: mostra profili candidati */}
      {role === "company" && (
        <Card className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Users className="h-5 w-5 text-primary" />
              Profili Consigliati
            </h3>
            <Badge variant="outline">{suggestedProfiles.length} profili</Badge>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {suggestedProfiles.map((profile) => (
              <Card key={profile.id} className="p-4 hover:shadow-lg transition-shadow">
                <div className="flex items-start gap-3 mb-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground flex-shrink-0">
                    {profile.name.split(" ").map((n) => n[0]).join("")}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold truncate">{profile.name}</p>
                    <p className="text-xs text-muted-foreground truncate">{profile.location}</p>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground mb-3 line-clamp-2">{profile.summary}</p>
                <div className="flex flex-wrap gap-1 mb-3">
                  {profile.skills.slice(0, 4).map((skill, i) => (
                    <Badge key={i} variant="secondary" className="text-xs">
                      {skill.name}
                    </Badge>
                  ))}
                  {profile.skills.length > 4 && (
                    <Badge variant="outline" className="text-xs">
                      +{profile.skills.length - 4}
                    </Badge>
                  )}
                </div>
                <Button size="sm" className="w-full" onClick={() => onConnect(profile.id)}>
                  Connetti
                </Button>
              </Card>
            ))}
          </div>
        </Card>
      )}

      {/* Opportunità: visibili a tutti */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Lightbulb className="h-5 w-5 text-primary" />
            Opportunità
          </h3>
          <Button variant="outline" size="sm" onClick={onAddOpportunity}>
            <Plus className="h-4 w-4 mr-1" /> Nuova
          </Button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {opportunities.map((opp) => (
            <Card key={opp.id} className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xl">{getOpportunityIcon(opp.type)}</span>
                <span className="font-semibold">{opp.title}</span>
              </div>
              <p className="text-xs text-muted-foreground mb-2">{opp.organization}</p>
              <p className="text-sm mb-2">{opp.description}</p>
              {opp.deadline && (
                <p className="text-xs text-muted-foreground mb-2">
                  <Calendar className="inline h-3 w-3 mr-1" />
                  Scadenza: {opp.deadline}
                </p>
              )}
              {opp.link && (
                <a href={opp.link} target="_blank" rel="noopener noreferrer" className="text-xs text-primary underline flex items-center gap-1">
                  <ExternalLink className="h-3 w-3" /> Vai al sito
                </a>
              )}
            </Card>
          ))}
        </div>
      </Card>

      {/* JD Top 20 - Lavori a cui posso candidarmi: solo per candidati */}
      {role === "candidate" && activeCandidate && matchedJd.length > 0 && (
        <Card className="p-6 mt-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Briefcase className="h-5 w-5 text-primary" />
              Lavori consigliati per te (Top 20)
            </h3>
            <Badge variant="outline">{matchedJd.length} lavori</Badge>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {matchedJd.map(({ jd, mustRequirements, niceRequirements }) => {
              // Score reale calcolato dal backend, '--' se non ancora calcolato
              const realScore = realScores[jd.jd_id];
              return (
                <Card key={jd.jd_id} className="p-4 border-2 border-muted shadow-sm">
                  <>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="inline-flex items-center px-2 py-0.5 rounded bg-muted text-xs font-medium text-muted-foreground mr-2">
                        <Briefcase className="h-4 w-4 mr-1 inline" /> job
                      </span>
                      <span className="ml-auto text-xs font-semibold text-primary">
                        Score match: {realScore !== undefined ? realScore : '--'}%
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold text-base">{jd.title}</span>
                    </div>
                    <div className="text-xs text-muted-foreground mb-1">
                      {(jd.company || "Azienda")} &middot; {jd.location?.city || ""} {jd.location?.country ? "/ " + jd.location.country : ""} {jd.location?.remote ? ' / Remote' : ''}
                    </div>
                    {/* Progress bar rimossa perché non c'è più score mock */}
                    <div className="mb-2 text-xs text-muted-foreground line-clamp-2">{jd.description}</div>
                    <div className="mb-2">
                      <span className="font-semibold text-xs">Requisiti:</span>
                      <ul className="list-disc ml-4 mt-1">
                        {mustRequirements.slice(0, 3).map((req, i) => (
                          <li key={i} className="text-xs text-emerald-700">{req}</li>
                        ))}
                        {niceRequirements.slice(0, 2).map((req, i) => (
                          <li key={i} className="text-xs text-blue-700">{req}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="flex gap-2 mt-2">
                      {realScore === undefined ? (
                        <Button
                          size="sm"
                          className="flex-1"
                          variant="default"
                          onClick={() => handleCalcolaMatch(jd.jd_id)}
                          disabled={loadingXai}
                        >
                          {loadingXai ? 'Calcolo...' : 'Calcola match'}
                        </Button>
                      ) : (
                        <Dialog open={openDialog === jd.jd_id} onOpenChange={(open) => {
                          if (!open) {
                            setOpenDialog(null);
                            setXaiData(null);
                          }
                        }}>
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
                                  <strong>Valutazione complessiva:</strong> {xaiData.quality_label || '-'}
                                </div>
                                {xaiData.top_reasons && xaiData.top_reasons.length > 0 && (
                                  <div className="mb-2">
                                    <strong>Motivi principali del match:</strong>
                                    <ul className="list-disc ml-5 mt-1">
                                      {xaiData.top_reasons.map((r, i) => (
                                        <li key={i} className="mb-1">
                                          <span className="font-semibold text-green-700">{r.text || ''}</span>
                                          {r.evidence && <span className="ml-2 text-muted-foreground">({r.evidence})</span>}
                                          {typeof r.contribution === 'number' && (
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
                                          <span className="font-semibold text-red-700">{r.text || ''}</span>
                                          {r.evidence && <span className="ml-2 text-muted-foreground">({r.evidence})</span>}
                                          {typeof r.contribution === 'number' && (
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
                      <Button size="sm" className="flex-1" variant="outline">Aggiungi ai preferiti</Button>
                    </div>
                  </>
                </Card>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );
};