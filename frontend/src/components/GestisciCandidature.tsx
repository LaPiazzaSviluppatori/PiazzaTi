import React, { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { FileText } from "lucide-react";
import { toast } from "@/hooks/use-toast";

import type { JobDescription } from "@/types";

interface GestisciCandidatureProps {
  onCreateJd?: (jd: Omit<JobDescription, "id" | "createdAt">) => void;
  jobDescriptions: JobDescription[];
  companyName?: string | null;
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

const GestisciCandidature: React.FC<GestisciCandidatureProps> = ({ onCreateJd, jobDescriptions, companyName }) => {
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [jdForm, setJdForm] = useState({
    title: "",
    company: "",
    department: "",
    description: "",
    min_experience_years: "",
    location_city: "",
    location_country: "",
    location_remote: false,
    constraints_visa: false,
    constraints_relocation: false,
    constraints_seniority: "junior",
    languages_min: "",
    dei_gender: "",
    dei_underrepresented: "",
    salary_min: "",
    salary_max: "",
    salary_currency: "",
    contract: "full_time",
  });

  const [requirements, setRequirements] = useState<{ text: string; type: "must" | "nice" }[]>([]);
  const [newReq, setNewReq] = useState("");
  const [reqType, setReqType] = useState<"must" | "nice">("must");

  const handleAddRequirement = () => {
    if (newReq.trim()) {
      setRequirements([...requirements, { text: newReq.trim(), type: reqType }]);
      setNewReq("");
    }
  };

  const handleRemoveRequirement = (index: number) => {
    setRequirements(requirements.filter((_, i) => i !== index));
  };

  const handleCreateJd = () => {
    if (!jdForm.title || !jdForm.company || requirements.length === 0) {
      toast({
        title: "Campi obbligatori mancanti",
        description: "Compila almeno titolo, azienda e un requisito",
        variant: "destructive",
      });
      return;
    }

    const allowedSeniorities = ["junior", "mid", "senior"] as const;
    const seniority = allowedSeniorities.includes(jdForm.constraints_seniority as typeof allowedSeniorities[number])
      ? (jdForm.constraints_seniority as "junior" | "mid" | "senior")
      : "junior";

    // Controllo di coerenza base tra seniority e anni di esperienza inseriti
    const experienceYears = Number(jdForm.min_experience_years) || 0;
    if (seniority === "senior" && experienceYears < 3) {
      toast({
        title: "Dati non coerenti",
        description: "Per un ruolo senior imposta almeno qualche anno di esperienza (es. "+
          "3+ anni) oppure scegli una seniority più bassa.",
        variant: "destructive",
      });
      return;
    }
    if (seniority === "junior" && experienceYears > 7) {
      toast({
        title: "Dati non coerenti",
        description: "Per un ruolo junior evita di richiedere troppi anni di esperienza (es. 10+).",
        variant: "destructive",
      });
      return;
    }

    const allowedLevels = ["A1","A2","B1","B2","C1","C2"] as const;
    const languages_min = (jdForm.languages_min || "").split(",").map(s => {
      const [lang, level] = s.split(":");
      const lvl = level ? level.trim().toUpperCase() : undefined;
      if (lang && lvl && allowedLevels.includes(lvl as typeof allowedLevels[number])) {
        return { lang: lang.trim(), level: lvl as typeof allowedLevels[number] };
      }
      return null;
    }).filter(Boolean) as { lang: string; level: "A1"|"A2"|"B1"|"B2"|"C1"|"C2" }[];

    const jdData = {
      jd_id: "",
      title: jdForm.title,
      company: jdForm.company,
      department: jdForm.department,
      description: jdForm.description,
      min_experience_years: experienceYears,
      requirements: requirements.filter(r => r.type === "must").map(r => r.text),
      nice_to_have: requirements.filter(r => r.type === "nice").map(r => r.text),
      location: { city: jdForm.location_city, country: jdForm.location_country, remote: !!jdForm.location_remote },
      constraints: { visa: !!jdForm.constraints_visa, relocation: !!jdForm.constraints_relocation, seniority, languages_min },
      dei_requirements: { target_balance: { gender: jdForm.dei_gender ? Number(jdForm.dei_gender) : undefined, underrepresented: jdForm.dei_underrepresented ? Number(jdForm.dei_underrepresented) : undefined } },
      metadata: { salary_range: { min: jdForm.salary_min ? Number(jdForm.salary_min) : undefined, max: jdForm.salary_max ? Number(jdForm.salary_max) : undefined, currency: jdForm.salary_currency }, contract: jdForm.contract },
    };

    onCreateJd?.(jdData);

    setJdForm({
      title: "",
      company: "",
      department: "",
      description: "",
      min_experience_years: "",
      location_city: "",
      location_country: "",
      location_remote: false,
      constraints_visa: false,
      constraints_relocation: false,
      constraints_seniority: "junior",
      languages_min: "",
      dei_gender: "",
      dei_underrepresented: "",
      salary_min: "",
      salary_max: "",
      salary_currency: "",
      contract: "full_time",
    });
    setRequirements([]);

    toast({ title: "Job Description creata", description: `"${jdForm.title}" aggiunta con successo` });
  };

  const myJobDescriptions = jobDescriptions.filter((jd) => {
    if (!companyName) return true;
    return jd.company === companyName;
  });

  type JDMatchCandidate = { rank: number; user_id: string; score: number; preview: string };
  const [matchJdId, setMatchJdId] = useState<string | null>(null);
  const [matchLoading, setMatchLoading] = useState(false);
  const [matchError, setMatchError] = useState<string | null>(null);
  const [matchCandidates, setMatchCandidates] = useState<JDMatchCandidate[] | null>(null);

  // Stato XAI per spiegare perché un candidato è adatto alla JD
  const [xaiByCandidate, setXaiByCandidate] = useState<Record<string, XAIData | null>>({});
  const [xaiLoadingKey, setXaiLoadingKey] = useState<string | null>(null);
  const [xaiError, setXaiError] = useState<string | null>(null);

  const [contactDialogOpen, setContactDialogOpen] = useState(false);
  const [contactDraft, setContactDraft] = useState("");
  const [contactTarget, setContactTarget] = useState<{
    candidate: JDMatchCandidate;
    jdId: string;
    jdTitle: string;
  } | null>(null);

  const handleShowMatches = async (jdId: string) => {
    setMatchJdId(jdId);
    setMatchLoading(true);
    setMatchError(null);
    setMatchCandidates(null);
    try {
      const res = await fetch(`/api/jd/matches/${jdId}`);
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Errore dal server");
      }
      const data = await res.json();
      const candidates = (data.candidates || []) as JDMatchCandidate[];
      setMatchCandidates(candidates);
    } catch (err) {
      console.error("Errore caricamento risultati match", err);
      setMatchError("Impossibile caricare i risultati di matching per questa JD.");
    } finally {
      setMatchLoading(false);
    }
  };

  const extractScoreFromXaiResult = (result: unknown): number | null => {
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

  const handleLoadXaiForCandidate = async (jdId: string, candidate: JDMatchCandidate) => {
    const key = `${jdId}:${candidate.user_id}`;
    setXaiLoadingKey(key);
    setXaiError(null);
    try {
      const response = await fetch("/api/match_cv_jd", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cv_path: candidate.user_id, jd_path: jdId }),
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || "Errore dal servizio di matching");
      }
      const result = (await response.json()) as Record<string, unknown>;

      let candidateXai: XAIData | null = null;
      if (result.candidate && typeof result.candidate === "object") {
        const c = result.candidate as Record<string, unknown>;
        if (c.xai && typeof c.xai === "object") {
          candidateXai = c.xai as XAIData;
        }
      }
      if (!candidateXai && result.xai && typeof result.xai === "object") {
        candidateXai = result.xai as XAIData;
      }
      if (!candidateXai) {
        candidateXai = result as XAIData;
      }

      setXaiByCandidate((prev) => ({ ...prev, [key]: candidateXai }));

      const rawScore = extractScoreFromXaiResult(result);
      if (rawScore !== null) {
        // Se vuoi, potresti anche aggiornare localmente lo score di matchCandidates qui
        // ma per ora usiamo solo lo score proveniente da jd_cv_matches.json
        console.debug("XAI score per candidato", candidate.user_id, Math.round(rawScore * 100));
      }
    } catch (err) {
      console.error("Errore caricamento XAI per candidato", err);
      setXaiError("Impossibile caricare la spiegazione del match per questo candidato.");
      setXaiByCandidate((prev) => ({ ...prev, [key]: null }));
    } finally {
      setXaiLoadingKey(null);
    }
  };

  const handleContactCandidate = (candidate: JDMatchCandidate, jdId: string, jdTitle: string) => {
    const defaultMessage = `Ciao, stiamo valutando il tuo profilo per la posizione "${jdTitle}". Se ti va, possiamo fissare una breve call per conoscerci meglio e raccontarti il ruolo.`;
    setContactTarget({ candidate, jdId, jdTitle });
    setContactDraft(defaultMessage);
    setContactDialogOpen(true);
  };

  const handleSendContact = async () => {
    if (!contactTarget) return;
    const message = contactDraft.trim();
    if (!message) {
      toast({
        title: "Messaggio vuoto",
        description: "Scrivi un breve messaggio prima di inviare.",
        variant: "destructive",
      });
      return;
    }

    try {
      const res = await fetch("/api/contact/candidate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          jd_id: contactTarget.jdId,
          candidate_id: contactTarget.candidate.user_id,
          message,
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Errore dal server");
      }

      toast({
        title: "Messaggio inviato",
        description: "Il candidato riceverà il tuo messaggio nella sua inbox.",
      });
      setContactDialogOpen(false);
      setContactTarget(null);
      setContactDraft("");
    } catch (err) {
      console.error("Errore invio messaggio al candidato", err);
      toast({
        title: "Errore invio messaggio",
        description: "Non è stato possibile inviare il messaggio. Riprova più tardi.",
        variant: "destructive",
      });
    }
  };

  return (
    <>
    <Card className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <FileText className="h-5 w-5 text-primary" />
          Crea Job Description
        </h3>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setIsFormOpen((prev) => !prev)}
        >
          {isFormOpen ? "Nascondi form" : "Nuova JD"}
        </Button>
      </div>

      {isFormOpen && (
        <>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="title">Titolo Posizione *</Label>
          <Input id="title" value={jdForm.title} onChange={e => setJdForm({ ...jdForm, title: e.target.value })} placeholder="es. Senior Frontend Developer" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="company">Azienda *</Label>
          <Input id="company" value={jdForm.company} onChange={e => setJdForm({ ...jdForm, company: e.target.value })} placeholder="es. TechCorp Italia" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="department">Dipartimento</Label>
          <Input id="department" value={jdForm.department || ""} onChange={e => setJdForm({ ...jdForm, department: e.target.value })} placeholder="es. R&D" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="min_experience_years">Esperienza minima (anni) *</Label>
          <Input id="min_experience_years" type="number" min={0} value={jdForm.min_experience_years || ""} onChange={e => setJdForm({ ...jdForm, min_experience_years: e.target.value })} placeholder="es. 3" />
        </div>
        <div className="space-y-2 md:col-span-2">
          <Label htmlFor="description">Descrizione *</Label>
          <Textarea id="description" value={jdForm.description} onChange={e => setJdForm({ ...jdForm, description: e.target.value })} placeholder="Descrivi la posizione, il team e le responsabilità..." rows={3} />
        </div>

        {/* Location and constraints */}
        <div className="space-y-2">
          <Label htmlFor="location_city">Città</Label>
          <Input id="location_city" value={jdForm.location_city || ""} onChange={e => setJdForm({ ...jdForm, location_city: e.target.value })} placeholder="es. Milano" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="location_country">Paese *</Label>
          <Input id="location_country" value={jdForm.location_country || ""} onChange={e => setJdForm({ ...jdForm, location_country: e.target.value })} placeholder="es. IT" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="location_remote">Remote</Label>
          <input id="location_remote" type="checkbox" checked={jdForm.location_remote || false} onChange={e => setJdForm({ ...jdForm, location_remote: e.target.checked })} />
        </div>

        <div className="space-y-2">
          <Label htmlFor="constraints_visa">Visto richiesto</Label>
          <input id="constraints_visa" type="checkbox" checked={jdForm.constraints_visa || false} onChange={e => setJdForm({ ...jdForm, constraints_visa: e.target.checked })} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="constraints_relocation">Disponibilità trasferimento</Label>
          <input id="constraints_relocation" type="checkbox" checked={jdForm.constraints_relocation || false} onChange={e => setJdForm({ ...jdForm, constraints_relocation: e.target.checked })} />
        </div>

        <div className="space-y-2">
          <Label htmlFor="constraints_seniority">Seniority *</Label>
          <Select value={jdForm.constraints_seniority || "junior"} onValueChange={v => setJdForm({ ...jdForm, constraints_seniority: v })}>
            <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="junior">Junior</SelectItem>
              <SelectItem value="mid">Mid</SelectItem>
              <SelectItem value="senior">Senior</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2 md:col-span-2">
          <Label>Lingue minime richieste</Label>
          <Input id="languages_min" value={jdForm.languages_min || ""} onChange={e => setJdForm({ ...jdForm, languages_min: e.target.value })} placeholder="es. english:B2, italian:C1" />
        </div>

        <div className="space-y-2">
          <Label htmlFor="dei_gender">Target genere (%)</Label>
          <Input id="dei_gender" type="number" min={0} max={1} step={0.01} value={jdForm.dei_gender || ""} onChange={e => setJdForm({ ...jdForm, dei_gender: e.target.value })} placeholder="es. 0.5" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="dei_underrepresented">Target underrepresented (%)</Label>
          <Input id="dei_underrepresented" type="number" min={0} max={1} step={0.01} value={jdForm.dei_underrepresented || ""} onChange={e => setJdForm({ ...jdForm, dei_underrepresented: e.target.value })} placeholder="es. 0.2" />
        </div>

        <div className="space-y-2">
          <Label htmlFor="salary_min">RAL Minima</Label>
          <Input id="salary_min" type="number" min={0} value={jdForm.salary_min || ""} onChange={e => setJdForm({ ...jdForm, salary_min: e.target.value })} placeholder="es. 35000" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="salary_max">RAL Massima</Label>
          <Input id="salary_max" type="number" min={0} value={jdForm.salary_max || ""} onChange={e => setJdForm({ ...jdForm, salary_max: e.target.value })} placeholder="es. 55000" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="salary_currency">Valuta</Label>
          <Input id="salary_currency" value={jdForm.salary_currency || ""} onChange={e => setJdForm({ ...jdForm, salary_currency: e.target.value })} placeholder="es. EUR" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="contract">Tipo contratto</Label>
          <Select value={jdForm.contract || "full_time"} onValueChange={v => setJdForm({ ...jdForm, contract: v })}>
            <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="full_time">Full Time</SelectItem>
              <SelectItem value="part_time">Part Time</SelectItem>
              <SelectItem value="internship">Internship</SelectItem>
              <SelectItem value="consultant">Consultant</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="mt-6">
        <Label>Requisiti *</Label>
        <div className="flex gap-2 mt-2">
          <Input
            value={newReq}
            onChange={(e) => setNewReq(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAddRequirement()}
            placeholder="es. React, 5+ anni esperienza..."
          />
          <Select value={reqType} onValueChange={(v) => setReqType(v as "must" | "nice")}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="must">Must</SelectItem>
              <SelectItem value="nice">Nice</SelectItem>
            </SelectContent>
          </Select>
          <Button onClick={handleAddRequirement}>Aggiungi</Button>
        </div>

        <div className="flex flex-wrap gap-2 mt-3">
          {requirements.map((req, i) => (
            <div key={i} className="flex items-center gap-2 p-2 border rounded">
              <span className="text-sm">{req.text}</span>
              <button onClick={() => handleRemoveRequirement(i)} className="ml-2 text-xs text-destructive">rimuovi</button>
            </div>
          ))}
        </div>
      </div>

      <Button onClick={handleCreateJd} className="mt-6 w-full">Crea Job Description</Button>
      </>
      )}

      {/* Elenco JD dell'azienda */}
      <div className="mt-8 border-t pt-4">
        <h4 className="text-md font-semibold mb-3">Le tue Job Description</h4>
        {myJobDescriptions.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nessuna JD pubblicata al momento.</p>
        ) : (
          <div className="space-y-3 max-h-80 overflow-y-auto">
            {myJobDescriptions.map((jd) => (
              <div key={jd.jd_id} className="p-3 border rounded-lg bg-muted/50 flex flex-col gap-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="space-y-0.5">
                    <span className="font-medium text-sm">{jd.title}</span>
                    {jd.company && (
                      <p className="text-xs text-muted-foreground">Azienda: {jd.company}</p>
                    )}
                    {jd.location?.city || jd.location?.country ? (
                      <p className="text-xs text-muted-foreground">
                        {[jd.location?.city, jd.location?.country].filter(Boolean).join(", ")}
                      </p>
                    ) : null}
                    {jd.requirements?.length ? (
                      <p className="text-xs text-muted-foreground truncate">
                        Requisiti principali: {jd.requirements.slice(0, 3).join(", ")}
                        {jd.requirements.length > 3 ? "…" : ""}
                      </p>
                    ) : null}
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="text-xs whitespace-nowrap"
                    onClick={() => handleShowMatches(jd.jd_id)}
                  >
                    Mostra risultati match
                  </Button>
                </div>
                {matchJdId === jd.jd_id && (
                  <div className="mt-1 border-t pt-2 space-y-1 text-xs">
                    {matchLoading ? (
                      <p className="text-muted-foreground">Caricamento risultati...</p>
                    ) : matchError ? (
                      <p className="text-destructive">{matchError}</p>
                    ) : !matchCandidates || matchCandidates.length === 0 ? (
                      <p className="text-muted-foreground">Nessun risultato di matching disponibile.</p>
                    ) : (
                      <div className="space-y-1 max-h-56 overflow-y-auto pr-1">
                        {matchCandidates.map((c) => (
                          <div
                            key={`${c.user_id}-${c.rank}`}
                            className="flex items-start justify-between gap-2 rounded border bg-background px-2 py-1.5"
                          >
                            <div className="space-y-0.5 flex-1">
                              <p className="font-medium text-[11px]">
                                Candidato #{c.rank}
                              </p>
                              {(() => {
                                const key = `${jd.jd_id}:${c.user_id}`;
                                const xai = xaiByCandidate[key];
                                if (xaiLoadingKey === key) {
                                  return (
                                    <p className="text-[11px] text-muted-foreground">
                                      Caricamento spiegazione...
                                    </p>
                                  );
                                }
                                if (xai) {
                                  const reasons = xai.top_reasons || [];
                                  return (
                                    <div className="text-[11px] text-muted-foreground">
                                      <p className="font-semibold">
                                        Perché pensiamo possa essere un buon candidato:
                                      </p>
                                      {reasons.length > 0 ? (
                                        <ul className="list-disc ml-4 mt-1 space-y-0.5">
                                          {reasons.slice(0, 2).map((r, idx) => (
                                            <li key={idx}>
                                              <span>{r.text || ""}</span>
                                              {r.evidence && (
                                                <span className="ml-1 text-muted-foreground">
                                                  ({r.evidence})
                                                </span>
                                              )}
                                            </li>
                                          ))}
                                        </ul>
                                      ) : (
                                        <p className="text-[11px] text-muted-foreground">
                                          Nessuna spiegazione dettagliata disponibile, ma il modello considera alto il match.
                                        </p>
                                      )}
                                    </div>
                                  );
                                }
                                return (
                                  <button
                                    type="button"
                                    className="text-[11px] text-primary underline"
                                    onClick={() => handleLoadXaiForCandidate(jd.jd_id, c)}
                                  >
                                    Perché pensiamo possa essere un buon candidato
                                  </button>
                                );
                              })()}
                              {xaiError && (
                                <p className="text-[10px] text-destructive mt-1">{xaiError}</p>
                              )}
                            </div>
                            <div className="flex flex-col items-end gap-1">
                              <span className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-[11px] font-semibold">
                                Match {Math.round(c.score * 100)}%
                              </span>
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                className="h-6 px-2 text-[10px]"
                                onClick={() => handleContactCandidate(c, jd.jd_id, jd.title)}
                              >
                                Contatta
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
    <Dialog open={contactDialogOpen} onOpenChange={(open) => {
      setContactDialogOpen(open);
      if (!open) {
        setContactTarget(null);
        setContactDraft("");
      }
    }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Invia un messaggio al candidato</DialogTitle>
          <DialogDescription>
            Scrivi un messaggio personalizzato. Sarà visibile al candidato nella sezione "Feedback ricevuti".
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          {contactTarget && (
            <p className="text-xs text-muted-foreground">
              Posizione: <span className="font-semibold">{contactTarget.jdTitle}</span>
            </p>
          )}
          <div className="space-y-2">
            <Label htmlFor="contact-message">Messaggio</Label>
            <Textarea
              id="contact-message"
              rows={5}
              value={contactDraft}
              onChange={(e) => setContactDraft(e.target.value)}
              placeholder="Presentati brevemente, spiega perché il profilo ti interessa e proponi i prossimi passi (es. call conoscitiva)."
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setContactDialogOpen(false);
              setContactTarget(null);
              setContactDraft("");
            }}
          >
            Annulla
          </Button>
          <Button type="button" onClick={handleSendContact}>
            Invia messaggio
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    </>
  );
};

export default GestisciCandidature;


//aggiunta delle candidature 