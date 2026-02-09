import React, { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "@/hooks/use-toast";

import type { JobDescription, Skill, Experience } from "@/types";

interface GestisciCandidatureProps {
  onCreateJd?: (jd: Omit<JobDescription, "id" | "createdAt">) => void;
  jobDescriptions: JobDescription[];
  companyName?: string | null;
  jwtToken?: string | null;
  profileSharesMap?: Record<string, { summary?: string; skills?: Skill[]; experiences?: Experience[] }>;
}

type JDMatchCandidate = {
  rank: number;
  user_id: string;
  score: number;
  preview?: string;
};

interface XAIReason {
  text?: string;
  evidence?: string;
  contribution?: number;
}

interface XAIData {
  quality_label?: string;
  top_reasons?: XAIReason[];
  main_risks?: XAIReason[];
  evidence?: Record<string, unknown>;
}

const GestisciCandidature: React.FC<GestisciCandidatureProps> = ({
  onCreateJd,
  jobDescriptions,
  companyName,
  jwtToken,
  profileSharesMap,
}) => {
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
    if (!newReq.trim()) return;
    setRequirements((prev) => [...prev, { text: newReq.trim(), type: reqType }]);
    setNewReq("");
  };

  const handleRemoveRequirement = (index: number) => {
    setRequirements((prev) => prev.filter((_, i) => i !== index));
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
    const seniority = allowedSeniorities.includes(
      jdForm.constraints_seniority as (typeof allowedSeniorities)[number],
    )
      ? (jdForm.constraints_seniority as "junior" | "mid" | "senior")
      : "junior";

    const experienceYears = Number(jdForm.min_experience_years) || 0;

    const allowedLevels = ["A1", "A2", "B1", "B2", "C1", "C2"] as const;
    const languages_min = (jdForm.languages_min || "")
      .split(",")
      .map((s) => {
        const [lang, level] = s.split(":");
        const lvl = level ? level.trim().toUpperCase() : undefined;
        if (lang && lvl && allowedLevels.includes(lvl as (typeof allowedLevels)[number])) {
          return { lang: lang.trim(), level: lvl as (typeof allowedLevels)[number] };
        }
        return null;
      })
      .filter(Boolean) as { lang: string; level: (typeof allowedLevels)[number] }[];

    const jdData = {
      jd_id: "",
      title: jdForm.title,
      company: jdForm.company,
      department: jdForm.department,
      description: jdForm.description,
      min_experience_years: experienceYears,
      requirements: requirements.filter((r) => r.type === "must").map((r) => r.text),
      nice_to_have: requirements.filter((r) => r.type === "nice").map((r) => r.text),
      location: {
        city: jdForm.location_city,
        country: jdForm.location_country,
        remote: !!jdForm.location_remote,
      },
      constraints: {
        visa: !!jdForm.constraints_visa,
        relocation: !!jdForm.constraints_relocation,
        seniority,
        languages_min,
      },
      dei_requirements: {
        target_balance: {
          gender: jdForm.dei_gender ? Number(jdForm.dei_gender) : undefined,
          underrepresented: jdForm.dei_underrepresented
            ? Number(jdForm.dei_underrepresented)
            : undefined,
        },
      },
      metadata: {
        salary_range: {
          min: jdForm.salary_min ? Number(jdForm.salary_min) : undefined,
          max: jdForm.salary_max ? Number(jdForm.salary_max) : undefined,
          currency: jdForm.salary_currency,
        },
        contract: jdForm.contract,
      },
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

    toast({
      title: "Job Description creata",
      description: `"${jdForm.title}" aggiunta con successo`,
    });
  };

  const myJobDescriptions = jobDescriptions.filter((jd) => {
    if (!companyName) return true;
    return jd.company === companyName;
  });

  const [matchJdId, setMatchJdId] = useState<string | null>(null);
  const [matchLoading, setMatchLoading] = useState(false);
  const [matchError, setMatchError] = useState<string | null>(null);
  const [matchCandidates, setMatchCandidates] = useState<JDMatchCandidate[] | null>(null);

  const [xaiByCandidate, setXaiByCandidate] = useState<Record<string, XAIData | null>>({});
  const [xaiLoadingKey, setXaiLoadingKey] = useState<string | null>(null);
  const [xaiErrorByCandidate, setXaiErrorByCandidate] = useState<Record<string, string>>({});

  const [contactDialogOpen, setContactDialogOpen] = useState(false);
  const [contactDraft, setContactDraft] = useState("");
  const [contactTarget, setContactTarget] = useState<{
    candidate: JDMatchCandidate;
    jdId: string;
    jdTitle: string;
  } | null>(null);

  const [profileDialogOpen, setProfileDialogOpen] = useState(false);
  const [profileDialogData, setProfileDialogData] = useState<{
    jdTitle: string;
    candidateLabel: string;
    summary?: string;
    skills?: Skill[];
    experiences?: Experience[];
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

  const handleContactCandidate = (candidate: JDMatchCandidate, jdId: string, jdTitle: string) => {
    setContactTarget({ candidate, jdId, jdTitle });
    setContactDraft("");
    setContactDialogOpen(true);
  };

  const handleRequestProfileView = async (candidate: JDMatchCandidate, jdId: string, jdTitle: string) => {
    const message = `Ti viene chiesto di condividere il tuo profilo per la posizione "${jdTitle}". Se accetti, autorizza la condivisione del tuo profilo dalla tua inbox.`;

    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (jwtToken) {
        headers["Authorization"] = `Bearer ${jwtToken}`;
      }

      const res = await fetch("/api/contact/candidate", {
        method: "POST",
        headers,
        body: JSON.stringify({
          jd_id: jdId,
          candidate_id: candidate.user_id,
          message,
          origin: "profile_request",
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Errore dal server");
      }

      toast({
        title: "Richiesta inviata",
        description: "Il candidato riceverà una richiesta di condivisione del profilo nella sua inbox.",
      });
    } catch (err) {
      console.error("Errore invio richiesta profilo", err);
      toast({
        title: "Errore richiesta profilo",
        description: "Non è stato possibile inviare la richiesta di visualizzazione del profilo.",
        variant: "destructive",
      });
    }
  };

  const handleLoadXaiForCandidate = async (jdId: string, candidate: JDMatchCandidate) => {
    const key = `${jdId}:${candidate.user_id}`;
    setXaiLoadingKey(key);
    setXaiErrorByCandidate((prev) => ({ ...prev, [key]: "" }));

    try {
      const response = await fetch("/api/match_cv_jd", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cv_path: candidate.user_id, jd_path: jdId }),
      });

      if (!response.ok) {
        const text = await response.text();
        console.error("Errore risposta matcher (GestisciCandidature XAI)", text);
        throw new Error(text || "Errore dal servizio di matching");
      }

      const result = (await response.json()) as Record<string, unknown>;

      let candidateXai: XAIData | null = null;
      if (result.candidate && typeof result.candidate === "object") {
        const candidateObj = result.candidate as Record<string, unknown>;
        if (candidateObj.xai && typeof candidateObj.xai === "object") {
          candidateXai = candidateObj.xai as XAIData;
        }
      }

      if (!candidateXai && result.xai && typeof result.xai === "object") {
        candidateXai = result.xai as XAIData;
      }

      setXaiByCandidate((prev) => ({ ...prev, [key]: candidateXai }));
    } catch (err) {
      console.error("Errore caricamento XAI per candidato", err);
      setXaiByCandidate((prev) => ({ ...prev, [key]: null }));
      setXaiErrorByCandidate((prev) => ({ ...prev, [key]: "Spiegazione non disponibile al momento." }));
    } finally {
      setXaiLoadingKey(null);
    }
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
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (jwtToken) {
        headers["Authorization"] = `Bearer ${jwtToken}`;
      }
      const res = await fetch("/api/contact/candidate", {
        method: "POST",
        headers,
        body: JSON.stringify({
          jd_id: contactTarget.jdId,
          candidate_id: contactTarget.candidate.user_id,
          message,
          origin: "top20",
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
    } catch (err) {
      console.error("Errore invio messaggio al candidato", err);
      toast({
        title: "Errore invio messaggio",
        description: "Non è stato possibile inviare il messaggio al candidato.",
        variant: "destructive",
      });
      return;
    } finally {
      setContactDialogOpen(false);
      setContactTarget(null);
      setContactDraft("");
    }
  };

  return (
    <>
      <Card className="p-4 space-y-4">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h3 className="text-lg font-semibold">Gestisci le candidature</h3>
            {companyName && (
              <p className="text-xs text-muted-foreground mt-0.5">
                Azienda: <span className="font-medium">{companyName}</span>
              </p>
            )}
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setIsFormOpen((open) => !open)}
          >
            {isFormOpen ? "Chiudi form" : "Nuova Job Description"}
          </Button>
        </div>

        {isFormOpen && (
          <div className="mt-2 space-y-4 border rounded-md p-3 bg-muted/40">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="title">Titolo Posizione *</Label>
                <Input
                  id="title"
                  value={jdForm.title}
                  onChange={(e) => setJdForm({ ...jdForm, title: e.target.value })}
                  placeholder="es. Senior Frontend Developer"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="company">Azienda *</Label>
                <Input
                  id="company"
                  value={jdForm.company}
                  onChange={(e) => setJdForm({ ...jdForm, company: e.target.value })}
                  placeholder="es. TechCorp Italia"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="department">Dipartimento</Label>
                <Input
                  id="department"
                  value={jdForm.department}
                  onChange={(e) => setJdForm({ ...jdForm, department: e.target.value })}
                  placeholder="es. R&D"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="min_experience_years">Esperienza minima (anni)</Label>
                <Input
                  id="min_experience_years"
                  type="number"
                  min={0}
                  value={jdForm.min_experience_years}
                  onChange={(e) => setJdForm({ ...jdForm, min_experience_years: e.target.value })}
                  placeholder="es. 3"
                />
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="description">Descrizione *</Label>
                <Textarea
                  id="description"
                  value={jdForm.description}
                  onChange={(e) => setJdForm({ ...jdForm, description: e.target.value })}
                  placeholder="Descrivi la posizione, il team e le responsabilità..."
                  rows={3}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="location_city">Città</Label>
                <Input
                  id="location_city"
                  value={jdForm.location_city}
                  onChange={(e) => setJdForm({ ...jdForm, location_city: e.target.value })}
                  placeholder="es. Milano"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="location_country">Paese *</Label>
                <Input
                  id="location_country"
                  value={jdForm.location_country}
                  onChange={(e) => setJdForm({ ...jdForm, location_country: e.target.value })}
                  placeholder="es. IT"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="location_remote">Remote</Label>
                <input
                  id="location_remote"
                  type="checkbox"
                  checked={jdForm.location_remote}
                  onChange={(e) =>
                    setJdForm({ ...jdForm, location_remote: e.target.checked })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="constraints_visa">Visto richiesto</Label>
                <input
                  id="constraints_visa"
                  type="checkbox"
                  checked={jdForm.constraints_visa}
                  onChange={(e) =>
                    setJdForm({ ...jdForm, constraints_visa: e.target.checked })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="constraints_relocation">Disponibilità trasferimento</Label>
                <input
                  id="constraints_relocation"
                  type="checkbox"
                  checked={jdForm.constraints_relocation}
                  onChange={(e) =>
                    setJdForm({ ...jdForm, constraints_relocation: e.target.checked })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="constraints_seniority">Seniority *</Label>
                <Select
                  value={jdForm.constraints_seniority}
                  onValueChange={(v) => setJdForm({ ...jdForm, constraints_seniority: v })}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="junior">Junior</SelectItem>
                    <SelectItem value="mid">Mid</SelectItem>
                    <SelectItem value="senior">Senior</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label>Lingue minime richieste</Label>
                <Input
                  id="languages_min"
                  value={jdForm.languages_min}
                  onChange={(e) => setJdForm({ ...jdForm, languages_min: e.target.value })}
                  placeholder="es. english:B2, italian:C1"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="dei_gender">Target genere (0-1)</Label>
                <Input
                  id="dei_gender"
                  type="number"
                  min={0}
                  max={1}
                  step={0.01}
                  value={jdForm.dei_gender}
                  onChange={(e) => setJdForm({ ...jdForm, dei_gender: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="dei_underrepresented">Target underrepresented (0-1)</Label>
                <Input
                  id="dei_underrepresented"
                  type="number"
                  min={0}
                  max={1}
                  step={0.01}
                  value={jdForm.dei_underrepresented}
                  onChange={(e) =>
                    setJdForm({ ...jdForm, dei_underrepresented: e.target.value })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="salary_min">RAL Minima</Label>
                <Input
                  id="salary_min"
                  type="number"
                  min={0}
                  value={jdForm.salary_min}
                  onChange={(e) => setJdForm({ ...jdForm, salary_min: e.target.value })}
                  placeholder="es. 35000"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="salary_max">RAL Massima</Label>
                <Input
                  id="salary_max"
                  type="number"
                  min={0}
                  value={jdForm.salary_max}
                  onChange={(e) => setJdForm({ ...jdForm, salary_max: e.target.value })}
                  placeholder="es. 55000"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="salary_currency">Valuta</Label>
                <Input
                  id="salary_currency"
                  value={jdForm.salary_currency}
                  onChange={(e) => setJdForm({ ...jdForm, salary_currency: e.target.value })}
                  placeholder="es. EUR"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="contract">Tipo contratto</Label>
                <Select
                  value={jdForm.contract}
                  onValueChange={(v) => setJdForm({ ...jdForm, contract: v })}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="full_time">Full Time</SelectItem>
                    <SelectItem value="part_time">Part Time</SelectItem>
                    <SelectItem value="internship">Internship</SelectItem>
                    <SelectItem value="consultant">Consultant</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="mt-4">
              <Label>Requisiti *</Label>
              <div className="flex flex-wrap gap-2 mt-2">
                <Input
                  className="flex-1 min-w-[200px]"
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
                <Button type="button" onClick={handleAddRequirement}>
                  Aggiungi
                </Button>
              </div>
              <div className="flex flex-wrap gap-2 mt-3">
                {requirements.map((req, i) => (
                  <div key={i} className="flex items-center gap-2 px-2 py-1 border rounded-full">
                    <span className="text-xs">
                      {req.text} {req.type === "must" ? "(must)" : "(nice)"}
                    </span>
                    <button
                      type="button"
                      className="text-[10px] text-destructive"
                      onClick={() => handleRemoveRequirement(i)}
                    >
                      rimuovi
                    </button>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-2">
              <Button type="button" onClick={handleCreateJd} className="w-full">
                Crea Job Description
              </Button>
            </div>
          </div>
        )}

        <div className="mt-4 border-t pt-4">
          <h4 className="text-md font-semibold mb-3">Le tue Job Description</h4>
          {myJobDescriptions.length === 0 ? (
            <p className="text-sm text-muted-foreground">Nessuna JD pubblicata al momento.</p>
          ) : (
            <div className="space-y-3 max-h-80 overflow-y-auto">
              {myJobDescriptions.map((jd) => (
                <div
                  key={jd.jd_id}
                  className="p-3 border rounded-lg bg-muted/50 flex flex-col gap-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="space-y-0.5">
                      <span className="font-medium text-sm">{jd.title}</span>
                      {jd.company && (
                        <p className="text-xs text-muted-foreground">Azienda: {jd.company}</p>
                      )}
                      {jd.location?.city || jd.location?.country ? (
                        <p className="text-xs text-muted-foreground">
                          {[jd.location?.city, jd.location?.country]
                            .filter(Boolean)
                            .join(", ")}
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
                        <p className="text-muted-foreground">
                          Nessun risultato di matching disponibile.
                        </p>
                      ) : (
                        <div className="space-y-1 max-h-56 overflow-y-auto pr-1">
                          {matchCandidates.map((c) => {
                            const key = `${jd.jd_id}:${c.user_id}`;
                            const xai = xaiByCandidate[key];
                            const xaiError = xaiErrorByCandidate[key];
                            const profileKey = `${jd.jd_id}:${c.user_id}`;
                            const sharedProfile = profileSharesMap?.[profileKey];
                            const isProfileAccepted = !!sharedProfile;
                            const qualityLabel = xai?.quality_label;
                            const qualityLabelText = qualityLabel === "EXCELLENT"
                              ? "Eccellente"
                              : qualityLabel === "GOOD"
                                ? "Buono"
                                : qualityLabel === "WEAK"
                                  ? "Da approfondire"
                                  : null;
                            const reasons = xai?.top_reasons ?? [];
                            const risks = xai?.main_risks ?? [];
                            const summarizedReasons = reasons
                              .slice(0, 2)
                              .map((r) => r.text)
                              .filter(Boolean)
                              .join("; ");
                            const summarizedRisks = risks
                              .slice(0, 2)
                              .map((r) => r.text)
                              .filter(Boolean)
                              .join("; ");
                            return (
                              <div
                                key={`${c.user_id}-${c.rank}`}
                                className="flex items-start justify-between gap-2 rounded border bg-background px-2 py-1.5"
                              >
                                <div className="space-y-0.5 flex-1">
                                  <p className="font-medium text-[11px]">
                                    Candidato #{c.rank}
                                  </p>
                                  <p className="text-[11px] text-muted-foreground">
                                    Match {Math.round(c.score * 100)}%
                                  </p>
                                  {c.preview && (
                                    <p className="text-[11px] text-muted-foreground line-clamp-2">
                                      {c.preview}
                                    </p>
                                  )}
                                  <div className="mt-1">
                                    {xaiLoadingKey === key ? (
                                      <p className="text-[10px] text-muted-foreground">
                                        Caricamento spiegazione...
                                      </p>
                                    ) : xai ? (
                                      <div className="space-y-0.5 text-[10px]">
                                        {qualityLabelText && (
                                          <p className="text-green-700">
                                            Valutazione complessiva: {qualityLabelText}
                                          </p>
                                        )}
                                        {summarizedReasons && (
                                          <p className="text-green-700">
                                            Motivi principali: {summarizedReasons}
                                          </p>
                                        )}
                                        {summarizedRisks && (
                                          <p className="text-amber-700">
                                            Attenzioni da considerare: {summarizedRisks}
                                          </p>
                                        )}
                                        {!qualityLabelText && !summarizedReasons && !summarizedRisks && (
                                          <p className="text-muted-foreground">
                                            Spiegazione disponibile ma senza dettagli strutturati.
                                          </p>
                                        )}
                                      </div>
                                    ) : xaiError ? (
                                      <p className="text-[10px] text-muted-foreground">
                                        {xaiError}
                                      </p>
                                    ) : (
                                      <button
                                        type="button"
                                        className="text-[10px] text-primary underline"
                                        onClick={() => handleLoadXaiForCandidate(jd.jd_id, c)}
                                      >
                                        Vedi spiegazione del match
                                      </button>
                                    )}
                                  </div>
                                </div>
                                <div className="flex flex-col items-end gap-1">
                                  {isProfileAccepted && (
                                    <span className="mb-0.5 inline-flex items-center rounded-full bg-emerald-100 text-emerald-800 px-2 py-0.5 text-[10px] font-semibold">
                                      Richiesta profilo accettata
                                    </span>
                                  )}
                                  <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    className="h-6 px-2 text-[10px]"
                                    onClick={() => handleContactCandidate(c, jd.jd_id, jd.title)}
                                  >
                                    Contatta
                                  </Button>
                                  {isProfileAccepted ? (
                                    <Button
                                      type="button"
                                      variant="outline"
                                      size="sm"
                                      className="h-6 px-2 text-[10px]"
                                      onClick={() => {
                                        if (!sharedProfile) return;
                                        setProfileDialogData({
                                          jdTitle: jd.title,
                                          candidateLabel: `Candidato #${c.rank}`,
                                          summary: sharedProfile.summary,
                                          skills: sharedProfile.skills,
                                          experiences: sharedProfile.experiences,
                                        });
                                        setProfileDialogOpen(true);
                                      }}
                                    >
                                      Visualizza profilo
                                    </Button>
                                  ) : (
                                    <Button
                                      type="button"
                                      variant="outline"
                                      size="sm"
                                      className="h-6 px-2 text-[10px]"
                                      onClick={() => handleRequestProfileView(c, jd.jd_id, jd.title)}
                                    >
                                      Richiedi profilo
                                    </Button>
                                  )}
                                </div>
                              </div>
                            );
                          })}
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

      <Dialog
        open={contactDialogOpen}
        onOpenChange={(open) => {
          setContactDialogOpen(open);
          if (!open) {
            setContactTarget(null);
            setContactDraft("");
          }
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Invia un messaggio al candidato</DialogTitle>
            <DialogDescription>
              Scrivi un messaggio personalizzato. Sarà visibile al candidato nella sezione
              "Feedback ricevuti".
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

      <Dialog
        open={profileDialogOpen}
        onOpenChange={(open) => {
          setProfileDialogOpen(open);
          if (!open) {
            setProfileDialogData(null);
          }
        }}
      >
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Profilo candidato</DialogTitle>
            {profileDialogData?.jdTitle && (
              <DialogDescription>
                Posizione: <span className="font-semibold">{profileDialogData.jdTitle}</span>
              </DialogDescription>
            )}
          </DialogHeader>
          <div className="space-y-3 py-2 text-sm">
            {profileDialogData?.summary && (
              <div>
                <p className="font-semibold text-xs text-muted-foreground mb-1">Descrizione</p>
                <p className="text-xs whitespace-pre-wrap">{profileDialogData.summary}</p>
              </div>
            )}
            {profileDialogData?.skills && profileDialogData.skills.length > 0 && (
              <div>
                <p className="font-semibold text-xs text-muted-foreground mb-1">Competenze</p>
                <ul className="list-disc ml-4 space-y-0.5">
                  {profileDialogData.skills.map((s, idx) => (
                    <li key={idx} className="text-xs">
                      {s.name}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {profileDialogData?.experiences && profileDialogData.experiences.length > 0 && (
              <div>
                <p className="font-semibold text-xs text-muted-foreground mb-1">Esperienze</p>
                <div className="space-y-1.5">
                  {profileDialogData.experiences.map((e, idx) => (
                    <div key={idx} className="border rounded px-2 py-1 bg-muted/40">
                      <p className="text-xs font-semibold">
                        {e.title || "Ruolo"}
                        {e.company ? ` · ${e.company}` : ""}
                      </p>
                      {e.period && (
                        <p className="text-[11px] text-muted-foreground">{e.period}</p>
                      )}
                      {e.description && (
                        <p className="text-[11px] whitespace-pre-wrap mt-0.5">
                          {e.description}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button type="button" onClick={() => setProfileDialogOpen(false)}>
              Chiudi
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default GestisciCandidature;
