import { useState, useEffect, useMemo } from "react";
import RegisterForm from "@/components/RegisterForm";
// import LandingPage from "./LandingPage";
import Header from "@/components/Header";
import { CandidateSection } from "@/components/CandidateSection";
import { CompanySection } from "@/components/CompanySection";
import { PipelineSection } from "@/components/PipelineSection";
import { DiscoverSection } from "@/components/DiscoverSection";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  mockOpportunities,
  mockFeedback,
  mockAuditLog,
} from "@/data/mockData";
import {
  Candidate,
  JobDescription,
  Opportunity,
  Feedback,
  AuditLogEntry,
  ShortlistCandidate,
  Skill,
  Post,
  OptInTag,
  Project,
} from "@/types";
import { toast } from "@/hooks/use-toast";

import CryptoJS from "crypto-js";
import { jwtDecode } from "jwt-decode";
import { User, Building2, GitBranch, Compass } from "lucide-react";


function getUserId(email: string): string {
  return CryptoJS.SHA256(email).toString(CryptoJS.enc.Hex);
}

interface JwtPayload {
  user_id?: string;
  sub?: string;
}

function decodeJwtUserId(token: string | null): string | undefined {
  if (!token) return undefined;
  try {
    const payload = jwtDecode<JwtPayload>(token);
    // Cerca user_id, altrimenti sub (come da backend)
    return payload.user_id || payload.sub;
  } catch (e) {
    // errore decodifica
    return undefined;
  }
}

// Barra di caricamento globale e overlay
import { Progress } from "@/components/ui/progress";
import "../components/custom-skeleton.css";

import type { Experience } from "@/types";

const Index = () => {
  const [showLanding, setShowLanding] = useState(true);
  const [deiMode, setDeiMode] = useState(true);
  const [activeTab, setActiveTab] = useState("candidate");
  const [authRole, setAuthRole] = useState<"candidate" | "company" | null>(null);
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [selectedRole, setSelectedRole] = useState<"candidate" | "company">("candidate");
  const [jwtToken, setJwtToken] = useState<string | null>(() => localStorage.getItem("piazzati:jwtToken"));
  const [showRegister, setShowRegister] = useState(false);
  const [registerRole, setRegisterRole] = useState<"candidate" | "company">("candidate");

  // Funzione di registrazione collegata al RegisterForm
  type CandidateRegisterData = {
    email: string;
    password: string;
    name: string;
    surname: string;
    city: string;
    region: string;
    country: string;
  };
  type CompanyRegisterData = {
    email: string;
    password: string;
    name: string;
    surname: string;
    companyName: string;
    city: string;
    region: string;
    country: string;
  };
  type RegisterData = CandidateRegisterData | CompanyRegisterData;

  const handleRegister = async (data: RegisterData) => {
    try {
      const res = await fetch("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...data, role: registerRole }),
      });
      if (res.ok) {
        toast({ title: "Registrazione completata", description: "Ora puoi accedere!" });
        setShowRegister(false);
        setSelectedRole(registerRole);
      } else {
        const err = await res.json();
        toast({ title: "Errore registrazione", description: err.detail || "Registrazione fallita", variant: "destructive" });
      }
    } catch (err) {
      toast({ title: "Errore di rete", description: String(err), variant: "destructive" });
    }
  };

  // Parsing state centralizzato
  const [isParsing, setIsParsing] = useState(false);
  const [progressPct, setProgressPct] = useState(0);
  const [progressLabel, setProgressLabel] = useState("");
  const [parsingTaskId, setParsingTaskId] = useState<string | null>(null);
  const [parsingTimer, setParsingTimer] = useState<ReturnType<typeof setTimeout> | null>(null);

  // Stato candidati persistente
  const [candidates, setCandidates] = useState<Candidate[]>(() => {
    const saved = localStorage.getItem("piazzati:candidates");
    if (saved) {
      try { return JSON.parse(saved) as Candidate[]; }
      catch (e) { console.warn("Persisted candidates parse error", e); }
    }
    return [];
  });
  const [jobDescriptions, setJobDescriptions] = useState<JobDescription[]>([]);
    // Carica le JD reali dal backend all'avvio
    useEffect(() => {
      fetch("/api/jd/list")
        .then(res => res.json())
        .then(data => {
          if (Array.isArray(data)) setJobDescriptions(data);
        })
        .catch(() => {});
    }, []);
  const [opportunities, setOpportunities] = useState<Opportunity[]>(mockOpportunities);
  const [feedback, setFeedback] = useState<Feedback[]>(mockFeedback);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>(mockAuditLog);

  const [selectedJdId, setSelectedJdId] = useState<string | null>(jobDescriptions[0]?.jd_id || null);
  const [activeCandidateId, setActiveCandidateId] = useState<string | null>(() => {
    const saved = localStorage.getItem("piazzati:activeCandidateId");
    return saved || null;
  });

  // Current candidate sempre sincronizzato
  const currentCandidate = candidates.find(c => c.id === activeCandidateId) || candidates[0];

  // Persistenza locale
  useEffect(() => {
    localStorage.setItem("piazzati:candidates", JSON.stringify(candidates));
    if (activeCandidateId) localStorage.setItem("piazzati:activeCandidateId", activeCandidateId);
  }, [candidates, activeCandidateId]);

  // Shortlist logic
  const shortlist: ShortlistCandidate[] = useMemo(() => {
    if (!selectedJdId) return [];
    const jd = jobDescriptions.find((j) => j.jd_id === selectedJdId);
    if (!jd) return [];
    // requirements e nice_to_have sono array di stringhe
    const mustRequirements = Array.isArray(jd.requirements) ? jd.requirements : [];
    const niceRequirements = Array.isArray(jd.nice_to_have) ? jd.nice_to_have : [];
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
        return {
          ...candidate,
          match: {
            candidateId: candidate.id,
            score,
            mustHaveMatch: Math.round(mustPercentage),
            niceToHaveMatch: Math.round(nicePercentage),
            explanation: `Match ${score}%: ${mustMatch}/${mustRequirements.length} must-have, ${niceMatch}/${niceRequirements.length} nice-to-have`,
          },
        };
      })
      .sort((a, b) => b.match.score - a.match.score);
  }, [candidates, jobDescriptions, selectedJdId]);

  // Suggested profiles (candidates with similar skills)
  const suggestedProfiles = useMemo(() => {
    return candidates.filter((c) => c.id !== currentCandidate?.id);
  }, [candidates, currentCandidate]);

  // Mostra direttamente login/dashboard, niente landing page

  // Skill add logic (deduplica e sovrascrive)
  const handleAddSkill = (skillName: string) => {
    if (!currentCandidate) return;
    setCandidates((prev) =>
      prev.map((c) => {
        if (c.id !== currentCandidate.id) return c;
        const allowedLevels = ["beginner", "intermediate", "advanced", "expert"] as const;
        const defaultLevel: typeof allowedLevels[number] = "intermediate";
        const skillMap = new Map<string, Skill>();
        c.skills.forEach(s => {
          if (s.name) skillMap.set(s.name.toLowerCase(), s);
        });
        skillMap.set(skillName.toLowerCase(), { name: skillName, level: defaultLevel });
        return { ...c, skills: Array.from(skillMap.values()) };
      })
    );
  };

  // Skill remove logic (persistente)
  const handleRemoveSkill = (skillName: string) => {
    if (!currentCandidate) return;
    setCandidates(prev => prev.map(c =>
      c.id === currentCandidate.id
        ? { ...c, skills: c.skills.filter(s => s.name.toLowerCase() !== skillName.toLowerCase()) }
        : c
    ));
  };

  // Tag add logic (deduplica)
  const handleAddTag = (tag: OptInTag) => {
    if (!currentCandidate) return;
    setCandidates(prev =>
      prev.map(c => {
        if (c.id !== currentCandidate.id) return c;
        const tags = [...c.optInTags, tag];
        const uniqueTags = tags.filter((t, idx, arr) =>
          arr.findIndex(tt => tt.label === t.label && tt.category === t.category) === idx
        );
        return { ...c, optInTags: uniqueTags };
      })
    );
  };

  // Tag remove logic (persistente)
  const handleRemoveTag = (label: string, category: string) => {
    if (!currentCandidate) return;
    setCandidates(prev => prev.map(c =>
      c.id === currentCandidate.id
        ? { ...c, optInTags: c.optInTags.filter(t => !(t.label === label && t.category === category)) }
        : c
    ));
  };

  // Project add logic
  const handleAddProject = (project: Project) => {
    if (!currentCandidate) return;
    setCandidates((prev) =>
      prev.map((c) => (c.id === currentCandidate.id ? { ...c, projects: [...c.projects, project] } : c))
    );
  };

  // Post add logic
  const handleAddPost = (content: string) => {
    if (!currentCandidate) return;
    const newPost: Post = {
      id: `p${Date.now()}`,
      content,
      date: new Date().toISOString().split("T")[0],
      likes: 0,
    };
    setCandidates((prev) =>
      prev.map((c) => (c.id === currentCandidate.id ? { ...c, posts: [newPost, ...c.posts] } : c))
    );
  };

  // Parsing logic: aggiorna skills deduplicate e tutto il profilo
  // Tipo per il parsed document dal backend
// ...existing imports...

  type ParsedCandidateBackend = Partial<Candidate> & {
    personal_info?: {
      full_name?: string;
      email?: string;
      phone?: string;
    };
    experience?: Experience[];
    experiences?: Experience[];
  };

  const handleCandidateParsed = (updated: ParsedCandidateBackend) => {
    setCandidates(prev => {
      // Estraggo i dati dal parsed document (compatibile con backend)
      const fullName = updated.personal_info?.full_name || updated.name || "";
      const email = updated.personal_info?.email || updated.email || "";
      const phone = updated.personal_info?.phone || updated.phone || "";
      const experiences = updated.experience || updated.experiences || [];
      if (prev.length === 0) {
        const newId = `c${Date.now()}`;
        const created: Candidate = {
          id: newId,
          name: fullName,
          email,
          phone,
          location: updated.location || "",
          connections: 0,
          optInTags: [],
          summary: updated.summary || "",
          skills: updated.skills || [],
          experiences,
          projects: updated.projects || [],
          posts: [],
        };
        setActiveCandidateId(newId);
        return [created];
      }
      if (!currentCandidate) return prev;
      const targetId = updated.id || currentCandidate.id;
      const parsedSkills = updated.skills || [];
      let newSkills: Skill[] = [];
      if (parsedSkills.length > 0) {
        const skillMap = new Map<string, Skill>();
        parsedSkills.forEach(s => {
          if (s.name) skillMap.set(s.name.toLowerCase(), s);
        });
        newSkills = Array.from(skillMap.values());
      } else {
        newSkills = prev.find(c => c.id === targetId)?.skills || [];
      }
      return prev.map(c =>
        c.id === targetId
          ? {
              ...c,
              ...updated,
              id: targetId,
              name: fullName,
              email,
              phone,
              experiences,
              skills: newSkills
            }
          : c
      );
    });
  };

  // Upload e parsing CV centralizzato e robusto
  const handleUploadCV = async (cvFile: File | null, userId?: string) => {
    if (!cvFile) {
      toast({ title: "Seleziona un file", description: "Carica un file CV", variant: "destructive" });
      return;
    }
    setIsParsing(true);
    setProgressPct(0);
    setProgressLabel("");
    setParsingTaskId(null);
    if (parsingTimer) clearTimeout(parsingTimer);
    const formData = new FormData();
    formData.append("file", cvFile);
    if (userId) {
      formData.append("user_id", userId);
    }
    try {
      const response = await fetch("/api/parse/upload", { method: "POST", body: formData });
      let parsed = null;
      if (response.status === 202) {
        const { task_id } = await response.json();
        if (!task_id) throw new Error("Task ID mancante");
        setParsingTaskId(task_id);
        const pollStart = Date.now();
        const maxMillis = 10 * 60 * 1000;
        const pollInterval = 2000;
        const poll = async () => {
          if (!task_id) return;
          const st = await fetch(`/api/parse/task/${task_id}`);
          if (!st.ok) throw new Error("Errore stato task");
          const task = await st.json();
          const elapsed = typeof task.elapsed_seconds === "number" ? task.elapsed_seconds : (Date.now() - pollStart) / 1000;
          const remaining = typeof task.estimated_remaining === "number" ? task.estimated_remaining : Math.max(0, (maxMillis - (Date.now() - pollStart)) / 1000);
          const total = elapsed + remaining;
          const pct = total > 0 ? Math.min(100, Math.max(0, Math.round((elapsed / total) * 100))) : Math.min(100, Math.round(((Date.now() - pollStart) / maxMillis) * 100));
          setProgressPct(pct);
          setProgressLabel(task.status === "completed" ? "Completato" : `Elaborazione… ${pct}%`);
          if (task.status === "completed") {
            parsed = task.result || task.parsed || task;
            setProgressPct(100);
            setProgressLabel("Completato");
            setIsParsing(false);
            setParsingTaskId(null);
            handleCandidateParsed(parsed);
            toast({ title: "CV caricato!", description: "Parsing completato e profilo aggiornato." });
            return;
          }
          if (task.status === "failed") {
            setIsParsing(false);
            setParsingTaskId(null);
            toast({ title: "Parsing fallito", description: task.error || "Errore durante il parsing", variant: "destructive" });
            return;
          }
          setParsingTimer(setTimeout(poll, pollInterval));
        };
        poll();
      } else {
        if (!response.ok) throw new Error("Errore upload");
        const data = await response.json();
        parsed = data.parsed || data;
        handleCandidateParsed(parsed);
        setProgressPct(100);
        setProgressLabel("Completato");
        setIsParsing(false);
        toast({ title: "CV caricato!", description: "Parsing completato e profilo aggiornato." });
      }
    } catch (err) {
      toast({ title: "Errore upload", description: String(err), variant: "destructive" });
      setIsParsing(false);
      setParsingTaskId(null);
    }
  };

  // Job description creation
  const handleCreateJd = (jd: Omit<JobDescription, "jd_id">) => {
    const newJd: JobDescription = {
      ...jd,
      jd_id: `jd${Date.now()}`,
    };
    setJobDescriptions((prev) => [newJd, ...prev]);
    const logEntry: AuditLogEntry = {
      id: `a${Date.now()}`,
      timestamp: new Date().toISOString(),
      action: "jd_created",
      user: "current.user@company.it",
      details: `Creata JD: ${newJd.title}`,
      deiCompliant: true,
    };
    setAuditLog((prev) => [logEntry, ...prev]);
  };

  // Shortlist close
  const handleCloseShortlist = (jdId: string, override?: { reason: string }) => {
    const logEntry: AuditLogEntry = {
      id: `a${Date.now()}`,
      timestamp: new Date().toISOString(),
      action: "shortlist_closed",
      user: "current.user@company.it",
      details: `Shortlist chiusa per JD: ${jdId}` + (override?.reason ? ` (${override.reason})` : ""),
      deiCompliant: true,
    };
    setAuditLog((prev) => [logEntry, ...prev]);
  };

  // Opportunity add
  const handleAddOpportunity = (op: Opportunity) => {
    setOpportunities((prev) => [op, ...prev]);
  };

  // Evaluate match
  const handleEvaluateMatch = (candidateId: string, jdId: string, score: number) => {
    toast({ title: "Match valutato", description: `Candidato ${candidateId} - JD ${jdId}: ${score}%` });
  };

  // Connect
  const handleConnect = (candidateId: string) => {
    setCandidates(prev =>
      prev.map(c =>
        c.id === candidateId
          ? { ...c, connections: c.connections + 1 }
          : c
      )
    );
    toast({ title: "Connessione effettuata", description: `Ora sei connesso con ${candidates.find(c => c.id === candidateId)?.name}` });
  };

  // Open profile
  const handleOpenProfile = (candidateId: string) => {
    setActiveTab("candidate");
    toast({ title: "Profilo aperto", description: `Visualizzazione profilo di ${candidates.find(c => c.id === candidateId)?.name}` });
  };

  // Login handler
  const handleLogin = async () => {
    if (!loginEmail || !loginPassword) {
      toast({ title: "Credenziali mancanti", description: "Inserisci email e password" });
      return;
    }
    try {
      const res = await fetch("/auth/token", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          username: loginEmail,
          password: loginPassword,
          role: selectedRole,
        }),
      });
      if (!res.ok) {
        let errorMsg = "Credenziali errate o utente inesistente";
        try {
          const err = await res.json();
          errorMsg = err.detail || errorMsg;
        } catch {
          const text = await res.text();
          errorMsg = text || errorMsg;
        }
        toast({ title: "Login fallito", description: errorMsg, variant: "destructive" });
        return;
      }
      const data = await res.json();
      localStorage.setItem("piazzati:jwtToken", data.access_token);
      setJwtToken(data.access_token);
      setAuthRole(selectedRole);

      // Estrai user_id dal JWT e imposta come candidato attivo
      let userIdFromJwt: string | undefined = undefined;
      try {
        const payload = jwtDecode<JwtPayload>(data.access_token);
        userIdFromJwt = payload.user_id;
      } catch (e) {
        // errore decodifica
      }
      if (userIdFromJwt) {
        // Cerca il candidato con quell'id, se esiste
        const found = candidates.find(c => c.id === userIdFromJwt);
        if (found) {
          setActiveCandidateId(userIdFromJwt);
        }
      }

      toast({ title: "Login eseguito", description: `Accesso come ${selectedRole}` });
    } catch (err) {
      toast({ title: "Errore login", description: String(err), variant: "destructive" });
    }
  };

  // Render
  return (
    <div
      className="min-h-screen w-full bg-cover bg-center relative"
      style={{ background: "url('/pink_wallpaper.jpg') center center / cover no-repeat fixed" }}
    >
      {/* Overlay e blur ora sono gestiti dentro CandidateSection */}
      {/* Header solo se autenticato */}
      {authRole && (
        <Header
          onLogout={() => {
            setAuthRole(null);
            setLoginEmail("");
            setLoginPassword("");
            setJwtToken(null);
            localStorage.removeItem("piazzati:jwtToken");
            toast({ title: "Logout eseguito", description: "Sei tornato alla pagina di login" });
          }}
        />
      )}
      <main className="container mx-auto px-4 py-8">
        {!authRole ? (
          showRegister ? (
            <div className="min-h-[80vh] flex items-center justify-center">
              <div className="max-w-md w-full bg-white/80 rounded-lg shadow p-8 flex flex-col gap-6">
                <h2 className="text-2xl font-bold mb-2 uppercase tracking-wide text-center">REGISTRAZIONE</h2>
                <RegisterForm
                  role={registerRole}
                  onRegister={handleRegister}
                  onSwitchRole={setRegisterRole}
                />
                <div className="text-center mt-2">
                  <button className="text-primary underline" onClick={() => setShowRegister(false)}>Hai già un account? Accedi</button>
                </div>
              </div>
            </div>
          ) : (
            <div className="min-h-[80vh] flex items-center justify-center">
              <div className="max-w-md w-full bg-white/80 rounded-lg shadow p-8 flex flex-col gap-6">
                <h2 className="text-2xl font-bold mb-2 uppercase tracking-wide text-center">ACCEDI</h2>
                <div className="flex flex-row gap-3 mb-4 justify-center items-center">
                  <button
                    className={`w-32 px-4 py-2 rounded-full border text-base font-semibold uppercase tracking-wide transition-colors duration-150 ${selectedRole === "candidate" ? "bg-primary text-primary-foreground" : "bg-muted"}`}
                    style={{ borderRadius: "2rem" }}
                    onClick={() => setSelectedRole("candidate")}
                  >CANDIDATO</button>
                  <button
                    className={`w-32 px-4 py-2 rounded-full border text-base font-semibold uppercase tracking-wide transition-colors duration-150 ${selectedRole === "company" ? "bg-primary text-primary-foreground" : "bg-muted"}`}
                    style={{ borderRadius: "2rem" }}
                    onClick={() => setSelectedRole("company")}
                  >AZIENDA</button>
                </div>
                <input
                  type="email"
                  placeholder="Email"
                  value={loginEmail}
                  onChange={e => setLoginEmail(e.target.value)}
                  className="mb-2 px-3 py-2 border rounded w-full"
                />
                <input
                  type="password"
                  placeholder="Password"
                  value={loginPassword}
                  onChange={e => setLoginPassword(e.target.value)}
                  className="mb-4 px-3 py-2 border rounded w-full"
                />
                <button
                  className="w-full bg-primary text-primary-foreground py-3 rounded-full font-semibold text-lg transition-colors duration-150"
                  style={{ borderRadius: "2rem" }}
                  onClick={handleLogin}
                >Accedi come {selectedRole === "candidate" ? "Candidato" : "Azienda"}</button>
                <div className="text-center mt-2">
                  <span>Non hai un account? </span>
                  <button className="text-primary underline" onClick={() => { setShowRegister(true); setRegisterRole(selectedRole); }}>Registrati</button>
                </div>
              </div>
            </div>
          )
        ) : (
          <Tabs
            value={activeTab}
            onValueChange={(val) => setActiveTab(val)}
            className="w-full"
          >
            <TabsList className={authRole === "candidate" ? "grid w-full grid-cols-3 mb-8" : authRole === "company" ? "grid w-full grid-cols-3 mb-8" : "grid w-full grid-cols-4 mb-8"}>
              {authRole !== "company" && (
                <TabsTrigger
                  value="candidate"
                  className="role-trigger flex items-center gap-2 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:border-primary"
                  disabled={authRole !== "candidate"}
                >
                  <User className="h-4 w-4" />
                  Candidato
                </TabsTrigger>
              )}
              {authRole !== "candidate" && (
                <TabsTrigger
                  value="company"
                  className="role-trigger flex items-center gap-2 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:border-primary"
                  disabled={authRole !== "company"}
                >
                  <Building2 className="h-4 w-4" />
                  Azienda
                </TabsTrigger>
              )}
              <TabsTrigger value="pipeline" className="flex items-center gap-2">
                <GitBranch className="h-4 w-4" />
                Pipeline
              </TabsTrigger>
              <TabsTrigger value="discover" className="flex items-center gap-2">
                <Compass className="h-4 w-4" />
                Scopri
              </TabsTrigger>
            </TabsList>

            {authRole !== "company" && (
              <TabsContent value="candidate">
                <CandidateSection
                  candidate={currentCandidate || {
                    id: "temp",
                    name: "",
                    location: "",
                    connections: 0,
                    optInTags: [],
                    summary: "",
                    skills: [],
                    experiences: [],
                    projects: [],
                    posts: [],
                  }}
                  jobDescriptions={jobDescriptions}
                  selectedJdId={selectedJdId}
                  onSelectJd={setSelectedJdId}
                  feedback={feedback}
                  onAddSkill={handleAddSkill}
                  onAddProject={handleAddProject}
                  onAddPost={handleAddPost}
                  onAddTag={handleAddTag}
                  onRemoveSkill={handleRemoveSkill}
                  onRemoveTag={handleRemoveTag}
                  suggestedProfiles={suggestedProfiles}
                  deiMode={deiMode}
                  onConnect={handleConnect}
                  onOpenProfile={handleOpenProfile}
                  onCandidateParsed={handleCandidateParsed}
                  userId={decodeJwtUserId(jwtToken)}
                  isParsing={isParsing}
                  progressPct={progressPct}
                  progressLabel={progressLabel}
                  onUploadCV={handleUploadCV}
                />
              </TabsContent>
            )}

            {authRole !== "candidate" && (
              <TabsContent value="company">
                <CompanySection
                  jobDescriptions={jobDescriptions}
                  onCreateJd={handleCreateJd}
                  shortlist={shortlist}
                  deiMode={deiMode}
                  auditLog={auditLog}
                  onCloseShortlist={handleCloseShortlist}
                />
              </TabsContent>
            )}

            <TabsContent value="pipeline">
              <PipelineSection
                candidates={candidates}
                jobDescriptions={jobDescriptions}
                auditLog={auditLog}
                deiMode={deiMode}
                isParsing={isParsing}
                mode={authRole === "company" ? "company" : "candidate"}
              />
            </TabsContent>

            <TabsContent value="discover">
              <DiscoverSection
                suggestedProfiles={suggestedProfiles}
                opportunities={opportunities}
                jobDescriptions={jobDescriptions}
                activeCandidate={currentCandidate}
                onConnect={handleConnect}
                onAddOpportunity={() => handleAddOpportunity(opportunities[0])}
                onEvaluateMatch={(jdId: string) => {
                  if (currentCandidate) {
                    const jd = jobDescriptions.find(j => j.jd_id === jdId);
                    if (jd) {
                      const mustRequirements = Array.isArray(jd.requirements) ? jd.requirements : [];
                      const niceRequirements = Array.isArray(jd.nice_to_have) ? jd.nice_to_have : [];
                      const candidateSkillNames = currentCandidate.skills.map((s) => s.name.toLowerCase());
                      const mustMatch = mustRequirements.filter((req) =>
                        candidateSkillNames.some((skill) => skill.includes(req.toLowerCase()))
                      ).length;
                      const niceMatch = niceRequirements.filter((req) =>
                        candidateSkillNames.some((skill) => skill.includes(req.toLowerCase()))
                      ).length;
                      const mustPercentage = mustRequirements.length > 0 ? (mustMatch / mustRequirements.length) * 100 : 0;
                      const nicePercentage = niceRequirements.length > 0 ? (niceMatch / niceRequirements.length) * 100 : 0;
                      const score = Math.round(mustPercentage * 0.7 + nicePercentage * 0.3);
                      handleEvaluateMatch(currentCandidate.id, jdId, score);
                    }
                  }
                }}
                role={authRole ?? "candidate"}
              />
            </TabsContent>
          </Tabs>
        )}
      </main>
    </div>
  );
};

export default Index;
