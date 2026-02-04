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

type UserRole = "candidate" | "company";
import { Users, Lightbulb, Briefcase, Plus, ExternalLink, TrendingUp, Calendar } from "lucide-react";
import { toast } from "@/hooks/use-toast";

// AGGIUNTA: props per candidato attivo
interface DiscoverSectionProps {
  suggestedProfiles: Candidate[];
  opportunities: Opportunity[];
  jobDescriptions: JobDescription[];
  activeCandidate?: Candidate;
  onConnect: (candidateId: string) => void;
  onAddOpportunity: () => void;
  onEvaluateMatch: (jdId: string) => void;
  role: UserRole;
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

  // Calcola i match solo se c'è un candidato attivo
  let matchedJd: Array<{ jd: JobDescription; score: number; mustRequirements: string[]; niceRequirements: string[] }> = [];
  if (activeCandidate) {
    matchedJd = jobDescriptions
      .map((jd) => {
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
        return { jd, score, mustRequirements, niceRequirements };
      })
      .sort((a, b) => b.score - a.score)
      .slice(0, 20);
  }

  const [openDialog, setOpenDialog] = React.useState<string | null>(null);
  const [xaiData, setXaiData] = React.useState<unknown>(null);
  const [loadingXai, setLoadingXai] = React.useState(false);

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
        throw new Error(text || "Errore dal servizio di matching");
      }
      const result = await response.json();
      setXaiData(result);
      const score = Math.round(result.score ?? result.overall_score ?? 0);
      toast({
        title: "Match calcolato",
        description: `Score da motore NLP: ${score}%`,
      });
      onEvaluateMatch(jdId);
    } catch (err) {
      toast({ title: "Errore match", description: String(err), variant: "destructive" });
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
            {matchedJd.map(({ jd, score, mustRequirements, niceRequirements }) => (
              <Card key={jd.jd_id} className="p-4 border-2 border-muted shadow-sm">
                <div className="flex items-center gap-2 mb-1">
                  <span className="inline-flex items-center px-2 py-0.5 rounded bg-muted text-xs font-medium text-muted-foreground mr-2">
                    <Briefcase className="h-4 w-4 mr-1 inline" /> job
                  </span>
                  <span className="ml-auto text-xs font-semibold text-primary">Score match: {score}%</span>
                </div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-semibold text-base">{jd.title}</span>
                  {score >= 80 && <span className="ml-2 text-yellow-500 font-bold">★</span>}
                </div>
                <div className="text-xs text-muted-foreground mb-1">
                  {(jd.company || "Azienda")} &middot; {jd.location?.city || ""} {jd.location?.country ? "/ " + jd.location.country : ""} {jd.location?.remote ? ' / Remote' : ''}
                </div>
                <div className="w-full bg-muted-foreground/10 rounded h-2 mb-2">
                  <div className="bg-primary h-2 rounded" style={{ width: `${score}%` }} />
                </div>
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
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Spiegazione del Match (XAI)</DialogTitle>
                      </DialogHeader>
                      {loadingXai && <div>Caricamento...</div>}
                      {!loadingXai && xaiData && (
                        <div style={{ maxHeight: 400, overflowY: 'auto', fontSize: 14 }}>
                          {(() => {
                            let xai: Record<string, unknown> = {};
                            if (typeof xaiData === 'object' && xaiData !== null) {
                              if ('xai' in xaiData && typeof (xaiData as Record<string, unknown>).xai === 'object') {
                                xai = (xaiData as Record<string, unknown>).xai as Record<string, unknown>;
                              } else {
                                xai = xaiData as Record<string, unknown>;
                              }
                            }
                            return (
                              <>
                                <div className="mb-3">
                                  <strong>Valutazione complessiva:</strong> {String(xai.quality_label || '-')}
                                </div>
                                <div className="mb-2">
                                  <strong>Motivi principali del match:</strong>
                                  <ul className="list-disc ml-5 mt-1">
                                    {Array.isArray(xai.top_reasons) ? xai.top_reasons.map((r: Record<string, unknown>, i: number) => (
                                      <li key={i} className="mb-1">
                                        <span className="font-semibold">{String(r.text ?? '')}</span>
                                        {r.evidence && <span className="ml-2 text-muted-foreground">({String(r.evidence)})</span>}
                                        {typeof r.contribution === 'number' && <span className="ml-2 text-xs text-primary">+{Math.round((r.contribution as number) * 100)}%</span>}
                                      </li>
                                    )) : null}
                                  </ul>
                                </div>
                                {Array.isArray(xai.main_risks) && xai.main_risks.length > 0 && (
                                  <div className="mb-2">
                                    <strong>Rischi/GAP principali:</strong>
                                    <ul className="list-disc ml-5 mt-1">
                                      {xai.main_risks.map((r: Record<string, unknown>, i: number) => (
                                        <li key={i} className="mb-1">
                                          <span className="font-semibold text-red-700">{String(r.text ?? '')}</span>
                                          {r.evidence && <span className="ml-2 text-muted-foreground">({String(r.evidence)})</span>}
                                          {typeof r.contribution === 'number' && <span className="ml-2 text-xs text-red-700">-{Math.abs(Math.round((r.contribution as number) * 100))}%</span>}
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                                {xai.evidence && (
                                  <div className="mt-3">
                                    <strong>Riepilogo evidenze:</strong>
                                    <ul className="list-disc ml-5 mt-1">
                                      {Object.entries(xai.evidence).map(([k, v]: [string, unknown], i) => (
                                        <li key={i}><span className="font-semibold">{k}:</span> {String(v)}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </>
                            );
                          })()}
                        </div>
                      )}
                      {!loadingXai && !xaiData && <div>Nessun dato XAI disponibile.</div>}
                      <DialogClose asChild>
                        <Button variant="outline">Chiudi</Button>
                      </DialogClose>
                    </DialogContent>
                  </Dialog>
                  <Button size="sm" className="flex-1" variant="outline">Aggiungi ai preferiti</Button>
                </div>
              </Card>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};
