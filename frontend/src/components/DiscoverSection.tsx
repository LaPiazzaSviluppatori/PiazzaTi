import React from "react";
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
  jwtToken?: string | null;
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
  jwtToken,
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
  const [applyDialogOpen, setApplyDialogOpen] = React.useState(false);
  const [applyJob, setApplyJob] = React.useState<JobDescription | null>(null);
  const [applyMessage, setApplyMessage] = React.useState("");
  const [sendingApplication, setSendingApplication] = React.useState(false);

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

  const handleApply = async (jd: JobDescription) => {
    if (role !== "candidate") return;
    if (!activeCandidate) {
      toast({
        title: "Nessun candidato attivo",
        description: "Seleziona o crea prima un profilo candidato.",
        variant: "destructive",
      });
      return;
    }
    const defaultMessage = `Ciao, mi piacerebbe candidarmi per la posizione "${jd.title}". Credo che le mie competenze siano in linea con i requisiti indicati e sarei felice di confrontarmi con voi.`;
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
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (jwtToken) {
        headers["Authorization"] = `Bearer ${jwtToken}`;
      }
      const res = await fetch("/api/contact/apply", {
        method: "POST",
        headers,
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
      console.error("Errore invio candidatura", err);
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

      {/* Sezione "Lavori consigliati per te" è stata rimossa da Discover: ora vive nella sezione Pipeline */}
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