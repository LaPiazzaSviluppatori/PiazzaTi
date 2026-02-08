import { useState, useEffect, useMemo, useCallback, type CSSProperties } from "react";
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

import { jwtDecode } from "jwt-decode";
import { User, Building2, GitBranch, Compass } from "lucide-react";

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
  const [currentUserProfile, setCurrentUserProfile] = useState<{ id: string; email: string; name?: string; role: string; company?: string | null } | null>(null);

  // Tema colori: rosa per candidato, blu per azienda
  // Anche nella schermata di login usiamo selectedRole per decidere il colore
  const isCompanyTheme = authRole === "company" || (!authRole && selectedRole === "company");

  const rootStyle = {
    background:
      authRole === "company"
        ? "url('/company_wallpaper.jpg') center center / cover no-repeat fixed"
        : authRole === "candidate"
        ? "url('/candidate_wallpaper.jpg') center center / cover no-repeat fixed"
        : "url('/grey_wallpaper.jpg') center center / cover no-repeat fixed",
    "--primary": isCompanyTheme ? "220 83% 56%" : "330 100% 35%",
    "--primary-foreground": "0 0% 100%",
  } as CSSProperties;

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
  const [feedback, setFeedback] = useState<Feedback[]>([]);
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>(mockAuditLog);

  const [selectedJdId, setSelectedJdId] = useState<string | null>(jobDescriptions[0]?.jd_id || null);
  const [activeCandidateId, setActiveCandidateId] = useState<string | null>(() => {
    const saved = localStorage.getItem("piazzati:activeCandidateId");
    return saved || null;
  });

  // Se l'utente è un candidato loggato ma non abbiamo ancora nessun candidato in memoria
  // (es. nuovo device o localStorage pulito), proviamo a ricostruire il profilo
  // chiedendo al backend l'ultimo CV parsato per lo user_id nel JWT.
  useEffect(() => {
    if (authRole !== "candidate" || !jwtToken) return;
    const userId = decodeJwtUserId(jwtToken);
    if (!userId) return;
    const already = candidates.find((c) => c.id === userId);
    if (already) return;

    (async () => {
      try {
        const res = await fetch(`/api/parse/user/${encodeURIComponent(userId)}/cv/latest`);
        if (!res.ok) return; // Nessun CV salvato per questo utente
        const data = await res.json();
        if (!data || !data.parsed_json) return;
        // Riusa la stessa logica usata dopo il parsing CV per
        // trasformare parsed_json in Candidate (handleCandidateParsed)
        handleCandidateParsed(data.parsed_json);
      } catch {
        // silenzioso: su device nuovo è opzionale
      }
    })();
  }, [authRole, jwtToken, candidates]);

  // Inbox messaggi per candidato (campanella)
  type InboxMessage = {
    id: string;
    timestamp: string;
    jd_id: string;
    message: string;
    from_company?: string | null;
    from_name?: string | null;
    origin?: string | null;
  };

  const [inboxMessages, setInboxMessages] = useState<InboxMessage[]>([]);
  const [inboxOpen, setInboxOpen] = useState(false);
  const [hasUnreadInbox, setHasUnreadInbox] = useState(false);

  const buildInboxKey = useCallback((msg: InboxMessage): string => {
    // Usa l'id stabile generato dal backend per identificare in modo univoco il messaggio
    return msg.id;
  }, []);

  const [seenInboxKeys, setSeenInboxKeys] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem("piazzati:seenInboxMessages");
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  });

  type CompanyReply = {
    id: string;
    timestamp: string;
    jd_id: string;
    candidate_id: string;
    candidate_name?: string | null;
    message: string;
  };

  const [companyReplies, setCompanyReplies] = useState<CompanyReply[]>([]);

  const buildCompanyReplyKey = useCallback((reply: CompanyReply): string => {
    return [
      reply.timestamp,
      reply.jd_id,
      reply.candidate_id,
      reply.candidate_name || "",
      reply.message,
    ].join("|");
  }, []);

  const [seenCompanyReplyKeys, setSeenCompanyReplyKeys] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem("piazzati:seenCompanyReplies");
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  });

  const markCompanyReplyAsSeen = (reply: CompanyReply) => {
    const key = buildCompanyReplyKey(reply);
    setSeenCompanyReplyKeys((prev) => {
      if (prev.includes(key)) return prev;
      const next = [...prev, key];
      try {
        localStorage.setItem("piazzati:seenCompanyReplies", JSON.stringify(next));
      } catch {
        // ignore storage errors
      }
      return next;
    });
  };

  const markInboxAsSeen = (msg: InboxMessage) => {
    const key = buildInboxKey(msg);
    setSeenInboxKeys((prev) => {
      if (prev.includes(key)) return prev;
      const next = [...prev, key];
      try {
        localStorage.setItem("piazzati:seenInboxMessages", JSON.stringify(next));
      } catch {
        // ignore storage errors
      }
      return next;
    });
  };

  type ConversationMessage = {
    id: string;
    timestamp: string;
    jd_id: string;
    candidate_id: string;
    message: string;
    from_role?: string | null;
    from_company?: string | null;
    from_name?: string | null;
  };

  const [openConversationJdId, setOpenConversationJdId] = useState<string | null>(null);
  const [conversationMessages, setConversationMessages] = useState<ConversationMessage[]>([]);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [conversationDraft, setConversationDraft] = useState("");
  const [lastConversationJdId, setLastConversationJdId] = useState<string | null>(null);

  const [openCompanyConversation, setOpenCompanyConversation] = useState<{ jdId: string; candidateId: string } | null>(null);
  const [companyConversationMessages, setCompanyConversationMessages] = useState<ConversationMessage[]>([]);
  const [loadingCompanyConversation, setLoadingCompanyConversation] = useState(false);
  const [companyConversationDraft, setCompanyConversationDraft] = useState("");
  const [lastCompanyConversation, setLastCompanyConversation] = useState<{ jdId: string; candidateId: string } | null>(null);
  const [companyFeedbackSending, setCompanyFeedbackSending] = useState<"positive" | "constructive" | "neutral" | null>(null);

  // Candidature ricevute lato azienda
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

  const [companyApplications, setCompanyApplications] = useState<CompanyApplication[]>([]);

  const buildCompanyAppKey = useCallback((app: CompanyApplication): string => {
    return [app.timestamp, app.jd_id, app.candidate_user_id, app.candidate_name || "", app.message]
      .join("|");
  }, []);

  const [seenCompanyAppKeys, setSeenCompanyAppKeys] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem("piazzati:seenCompanyApplications");
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  });

  const markCompanyAppAsSeen = (app: CompanyApplication) => {
    const key = buildCompanyAppKey(app);
    setSeenCompanyAppKeys((prev) => {
      if (prev.includes(key)) return prev;
      const next = [...prev, key];
      try {
        localStorage.setItem("piazzati:seenCompanyApplications", JSON.stringify(next));
      } catch {
        // ignore storage errors
      }
      return next;
    });
  };

  const fetchInbox = async () => {
    if (!jwtToken || authRole !== "candidate") return;
    try {
      const res = await fetch("/api/contact/inbox", {
        headers: {
          Authorization: `Bearer ${jwtToken}`,
        },
      });
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data)) {
        setInboxMessages(data as InboxMessage[]);
      }
    } catch {
      // silenzioso: la inbox non è critica
    }
  };
  type ApiFeedback = {
    id: string;
    timestamp?: string;
    jd_id: string;
    jd_title?: string | null;
    company?: string | null;
    type?: string;
    message?: string | null;
  };

  const fetchFeedback = async () => {
    if (!jwtToken || authRole !== "candidate") return;
    try {
      const res = await fetch("/api/contact/feedback/my", {
        headers: {
          Authorization: `Bearer ${jwtToken}`,
        },
      });
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data)) {
        const mapped: Feedback[] = (data as ApiFeedback[]).map((fb) => ({
          id: String(fb.id),
          from: fb.company || "",
          message: String(fb.message ?? ""),
          date: String(fb.timestamp ?? new Date().toISOString()),
          type:
            fb.type === "positive" || fb.type === "constructive" || fb.type === "neutral"
              ? (fb.type as Feedback["type"])
              : "neutral",
          jdTitle: fb.jd_title ?? undefined,
          company: fb.company ?? undefined,
        }));
        setFeedback(mapped);
      }
    } catch {
      // per ora silenzioso, i feedback non sono critici
    }
  };

  const clearMyFeedback = async () => {
    if (!jwtToken || authRole !== "candidate") return;
    try {
      const res = await fetch("/api/contact/feedback/my", {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${jwtToken}`,
        },
      });
      if (!res.ok) {
        const txt = await res.text();
        toast({
          title: "Errore cancellazione feedback",
          description: txt || "Non è stato possibile cancellare i feedback.",
          variant: "destructive",
        });
        return;
      }
      setFeedback([]);
      toast({
        title: "Feedback cancellati",
        description: "Tutti i feedback dalle aziende sono stati rimossi.",
      });
    } catch (err) {
      console.error("Errore cancellazione feedback", err);
      toast({
        title: "Errore cancellazione feedback",
        description: "Non è stato possibile cancellare i feedback.",
        variant: "destructive",
      });
    }
  };

  const fetchConversation = useCallback(
    async (jdId: string) => {
      if (!jwtToken || authRole !== "candidate") return;
      try {
        setLoadingConversation(true);
        const res = await fetch(`/api/contact/conversation?jd_id=${encodeURIComponent(jdId)}`, {
          headers: { Authorization: `Bearer ${jwtToken}` },
        });
        if (!res.ok) return;
        const data = await res.json();
        if (Array.isArray(data)) {
          setConversationMessages(data as ConversationMessage[]);
        }
      } catch {
        // silenzioso per ora
      } finally {
        setLoadingConversation(false);
      }
    },
    [jwtToken, authRole]
  );

  const fetchCompanyConversation = useCallback(
    async (jdId: string, candidateId: string) => {
      if (!jwtToken || authRole !== "company") return;
      try {
        setLoadingCompanyConversation(true);
        const res = await fetch(
          `/api/contact/conversation/company?jd_id=${encodeURIComponent(jdId)}&candidate_id=${encodeURIComponent(candidateId)}`,
          {
            headers: { Authorization: `Bearer ${jwtToken}` },
          }
        );
        if (!res.ok) return;
        const data = await res.json();
        if (Array.isArray(data)) {
          setCompanyConversationMessages(data as ConversationMessage[]);
        }
      } catch {
        // silenzioso per ora
      } finally {
        setLoadingCompanyConversation(false);
      }
    },
    [jwtToken, authRole]
  );

  // Aggiornamento periodico chat candidato mentre il modal è aperto
  useEffect(() => {
    if (authRole !== "candidate" || !jwtToken || !openConversationJdId) return;
    const interval = setInterval(() => {
      fetchConversation(openConversationJdId);
    }, 2000);
    return () => clearInterval(interval);
  }, [authRole, jwtToken, openConversationJdId, fetchConversation]);

  // Aggiornamento periodico chat azienda mentre il modal è aperto
  useEffect(() => {
    if (authRole !== "company" || !jwtToken || !openCompanyConversation) return;
    const interval = setInterval(() => {
      fetchCompanyConversation(openCompanyConversation.jdId, openCompanyConversation.candidateId);
    }, 2000);
    return () => clearInterval(interval);
  }, [authRole, jwtToken, openCompanyConversation, fetchCompanyConversation]);

  const fetchCompanyApplications = async () => {
    if (!jwtToken || authRole !== "company") return;
    try {
      const res = await fetch("/api/contact/applications", {
        headers: {
          Authorization: `Bearer ${jwtToken}`,
        },
      });
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data)) {
        setCompanyApplications(data as CompanyApplication[]);
      }
    } catch {
      // silenzioso
    }
  };

  const fetchCompanyReplies = async () => {
    if (!jwtToken || authRole !== "company") return;
    try {
      const res = await fetch("/api/contact/inbox/company", {
        headers: {
          Authorization: `Bearer ${jwtToken}`,
        },
      });
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data)) {
        setCompanyReplies(data as CompanyReply[]);
      }
    } catch {
      // silenzioso
    }
  };

  useEffect(() => {
    if (authRole === "candidate" && jwtToken) {
      fetchInbox();
      fetchFeedback();
    } else {
      setInboxMessages([]);
      setInboxOpen(false);
      setHasUnreadInbox(false);
      setFeedback([]);
    }
    if (authRole === "company" && jwtToken) {
      fetchCompanyApplications();
      fetchCompanyReplies();
    } else {
      setCompanyApplications([]);
      setCompanyReplies([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authRole, jwtToken]);

  // Polling leggero per aggiornare la inbox (campanella) del candidato
  useEffect(() => {
    if (authRole !== "candidate" || !jwtToken) return;

    const intervalId = window.setInterval(() => {
      fetchInbox();
    }, 8000);

    return () => window.clearInterval(intervalId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authRole, jwtToken]);

  const unreadInboxMessages = useMemo(
    () =>
      inboxMessages.filter((msg) => !seenInboxKeys.includes(buildInboxKey(msg))),
    [inboxMessages, seenInboxKeys, buildInboxKey]
  );

  const unreadCompanyApplications = useMemo(
    () =>
      companyApplications.filter((app) => !seenCompanyAppKeys.includes(buildCompanyAppKey(app))),
    [companyApplications, seenCompanyAppKeys, buildCompanyAppKey]
  );

  const unreadCompanyReplies = useMemo(
    () =>
      companyReplies.filter((reply) => !seenCompanyReplyKeys.includes(buildCompanyReplyKey(reply))),
    [companyReplies, seenCompanyReplyKeys, buildCompanyReplyKey]
  );

  useEffect(() => {
    if (authRole === "candidate") {
      setHasUnreadInbox(unreadInboxMessages.length > 0);
    }
  }, [authRole, unreadInboxMessages]);

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

  type ParsedCandidateBackend = {
    // Struttura che arriva dal backend (ParsedDocument)
    user_id?: string;
    personal_info?: {
      full_name?: string;
      email?: string;
      phone?: string;
      city?: string;
      country?: string;
    };
    summary?: string;
    skills?: { name?: string; level?: Skill["level"]; }[];
    experience?: {
      title?: string;
      company?: string;
      city?: string;
      country?: string;
      start_date?: string;
      end_date?: string;
      description?: string;
    }[];
    experiences?: ParsedCandidateBackend["experience"];
    projects?: Project[];
    id?: string;
    email?: string;
    phone?: string;
    name?: string;
    location?: string;
  };

  const normalizeParsedSkills = (
    skills?: { name?: string; level?: Skill["level"]; }[]
  ): Skill[] => {
    if (!skills) return [];
    const result: Skill[] = [];
    for (const s of skills) {
      if (!s.name) continue;
      result.push({ name: s.name, level: s.level });
    }
    return result;
  };

  const handleCandidateParsed = (updated: ParsedCandidateBackend) => {
    setCandidates(prev => {
      // Estraggo i dati dal parsed document (compatibile con backend)
      const fullName = updated.personal_info?.full_name || updated.name || "";
      const email = updated.personal_info?.email || updated.email || "";
      const phone = updated.personal_info?.phone || updated.phone || "";
      const rawExperiences = updated.experience || updated.experiences || [];
      const experiences: Experience[] = rawExperiences.map((e) => ({
        title: e.title || "",
        company: e.company || "",
        period: [e.start_date, e.end_date].filter(Boolean).join(" - "),
        description: e.description || "",
      }));

      const locationParts: string[] = [];
      if (updated.personal_info?.city) locationParts.push(updated.personal_info.city);
      if (updated.personal_info?.country) locationParts.push(updated.personal_info.country);
      const location = updated.location || locationParts.join(", ");
      // Usa user_id come identificatore backend del candidato (non pi f8 l'alias id)
      const targetIdFromParsed = updated.user_id || currentCandidate?.id || `c${Date.now()}`;
      const normalizedSkills = normalizeParsedSkills(updated.skills);

      if (prev.length === 0 || !prev.some(c => c.id === targetIdFromParsed)) {
        const newId = targetIdFromParsed;
        const created: Candidate = {
          id: newId,
          name: fullName,
          email,
          phone,
          location,
          connections: 0,
          optInTags: [],
          summary: updated.summary || "",
          skills: normalizedSkills,
          experiences,
          projects: updated.projects || [],
          posts: [],
        };
        setActiveCandidateId(newId);
        return [created];
      }
      if (!currentCandidate) return prev;
      const targetId = targetIdFromParsed || currentCandidate.id;
      const parsedSkills = normalizeParsedSkills(updated.skills);
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
              location,
              experiences,
              skills: newSkills
            }
          : c
      );
    });
  };

  // Upload e parsing CV centralizzato e robusto
  const handleUploadCV = async (cvFile: File | null, user_id?: string) => {
    if (!cvFile) {
      toast({ title: "Seleziona un file", description: "Carica un file CV", variant: "destructive" });
      return;
    }
    // Usa prima l'user_id passato dal componente, altrimenti quello dal JWT corrente
    const effectiveUserId = user_id || decodeJwtUserId(jwtToken);
    setIsParsing(true);
    setProgressPct(0);
    setProgressLabel("");
    setParsingTaskId(null);
    if (parsingTimer) clearTimeout(parsingTimer);
    const formData = new FormData();
    formData.append("file", cvFile);
    if (effectiveUserId) {
      formData.append("user_id", effectiveUserId);
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

  // Carica il profilo candidato dal backend (ultimo CV parsato) dato uno user_id
  const loadCandidateProfileFromBackend = async (userId: string, token: string) => {
    try {
      const res = await fetch(`/api/parse/user/${userId}/cv/latest`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!res.ok) {
        // 404: nessun CV ancora caricato, silenzioso
        return;
      }
      const data = await res.json();
      const parsed = (data.parsed_json || {}) as ParsedCandidateBackend;
      if (!parsed.user_id) {
        parsed.user_id = userId;
      }
      handleCandidateParsed(parsed);
      setActiveCandidateId(userId);
    } catch (err) {
      console.warn("Impossibile caricare il profilo candidato dal backend", err);
    }
  };

  // Job description creation (persistente su backend)
  const handleCreateJd = async (jd: Omit<JobDescription, "jd_id">) => {
    try {
      const payload = {
        title: jd.title,
        description: jd.description,
        language: "it",
        requirements: jd.requirements ?? [],
        nice_to_have: jd.nice_to_have ?? [],
        department: jd.department,
        company: jd.company,
        location: jd.location,
        constraints: jd.constraints,
        dei_requirements: jd.dei_requirements,
        metadata: jd.metadata,
      };

      const response = await fetch("/api/jd/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error("Errore nel salvataggio della JD");
      }

      const data = await response.json();
      const backendId: string = data.id || `jd${Date.now()}`;

      const newJd: JobDescription = {
        ...jd,
        jd_id: backendId,
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

      toast({ title: "JD salvata", description: "La job description è stata salvata nel sistema." });
    } catch (err) {
      toast({ title: "Errore JD", description: String(err), variant: "destructive" });
    }
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
          const text = await res.text();
          if (text) {
            try {
              const err = JSON.parse(text);
              errorMsg = (err && err.detail) || errorMsg;
            } catch {
              errorMsg = text || errorMsg;
            }
          }
        } catch {
          // fallback al messaggio di default
        }
        toast({ title: "Login fallito", description: errorMsg, variant: "destructive" });
        return;
      }
      const data = await res.json();
      localStorage.setItem("piazzati:jwtToken", data.access_token);
      setJwtToken(data.access_token);
      setAuthRole(selectedRole);

      // Recupera profilo utente corrente (incluso company per aziende)
      try {
        const meRes = await fetch("/auth/me", {
          headers: { Authorization: `Bearer ${data.access_token}` },
        });
        if (meRes.ok) {
          const me = await meRes.json();
          setCurrentUserProfile(me);
        }
      } catch {
        // profilo non essenziale, ignora errori
      }

      // Estrai user_id dal JWT e imposta come candidato attivo
      let userIdFromJwt: string | undefined = undefined;
      try {
        const payload = jwtDecode<JwtPayload>(data.access_token);
        userIdFromJwt = payload.user_id;
      } catch (e) {
        // errore decodifica
      }
      if (userIdFromJwt) {
        // Cerca il candidato con quell'id, se esiste già in locale
        const found = candidates.find(c => c.id === userIdFromJwt);
        if (found) {
          setActiveCandidateId(userIdFromJwt);
        } else if (selectedRole === "candidate") {
          // Se login come candidato e non c'è ancora in locale, prova a ricostruirlo dal backend
          await loadCandidateProfileFromBackend(userIdFromJwt, data.access_token);
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
      style={rootStyle}
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
          showInbox={true}
          inboxCount={
            authRole === "candidate"
              ? unreadInboxMessages.length
              : unreadCompanyApplications.length + unreadCompanyReplies.length
          }
          hasUnreadInbox={
            authRole === "candidate"
              ? hasUnreadInbox
              : authRole === "company" &&
                unreadCompanyApplications.length + unreadCompanyReplies.length > 0
          }
          showChat={true}
          onToggleChat={async () => {
            if (!authRole) return;
            if (authRole === "candidate") {
              // Se la chat è aperta, chiudila
              if (openConversationJdId) {
                setOpenConversationJdId(null);
                setConversationMessages([]);
                setConversationDraft("");
                return;
              }
              // Altrimenti apri l'ultima conversazione o la prima disponibile
              let targetJdId = lastConversationJdId;
              if (!targetJdId && inboxMessages.length > 0) {
                targetJdId = inboxMessages[0].jd_id;
              }
              if (!targetJdId) {
                toast({
                  title: "Nessuna chat",
                  description: "Non hai ancora conversazioni attive con le aziende.",
                });
                return;
              }
              setOpenConversationJdId(targetJdId);
              setLastConversationJdId(targetJdId);
              await fetchConversation(targetJdId);
            } else if (authRole === "company") {
              // Se la chat è aperta, chiudila
              if (openCompanyConversation) {
                setOpenCompanyConversation(null);
                setCompanyConversationMessages([]);
                setCompanyConversationDraft("");
                return;
              }
              // Altrimenti apri l'ultima conversazione o la prima candidatura disponibile
              let target = lastCompanyConversation;
              if (!target && companyApplications.length > 0) {
                const first = companyApplications[0];
                target = { jdId: first.jd_id, candidateId: first.candidate_user_id };
              }
              if (!target) {
                toast({
                  title: "Nessuna chat",
                  description: "Non hai ancora conversazioni attive con i candidati.",
                });
                return;
              }
              setOpenCompanyConversation(target);
              setLastCompanyConversation(target);
              await fetchCompanyConversation(target.jdId, target.candidateId);
            }
          }}
          onToggleInbox={async () => {
            if (authRole === "candidate") {
              if (!inboxOpen) {
                // Apertura: carica messaggi
                await fetchInbox();
              } else {
                // Chiusura: segna tutti i messaggi attuali come letti
                unreadInboxMessages.forEach((msg) => markInboxAsSeen(msg));
              }
              setInboxOpen((prev) => !prev);
            } else if (authRole === "company") {
              if (!inboxOpen) {
                await Promise.all([fetchCompanyApplications(), fetchCompanyReplies()]);
              } else {
                // Segna come visti tutti gli elementi non letti (candidature + risposte chat)
                unreadCompanyApplications.forEach((app) => markCompanyAppAsSeen(app));
                unreadCompanyReplies.forEach((reply) => markCompanyReplyAsSeen(reply));
              }
              setInboxOpen((prev) => !prev);
            }
          }}
        />
      )}
      {/* Inbox candidato: pannello a discesa dalla campanella */}
      {authRole === "candidate" && inboxOpen && unreadInboxMessages.length > 0 && (
        <div className="fixed top-16 right-4 z-40 w-80 max-h-[60vh] overflow-y-auto bg-white/95 shadow-lg rounded-lg border p-3 space-y-3">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-sm font-semibold">Messaggi dalle aziende</h2>
            <button
              className="text-xs text-muted-foreground hover:underline"
              onClick={() => setInboxOpen(false)}
            >
              Chiudi
            </button>
          </div>
          {unreadInboxMessages.map((msg) => {
            const jdTitle = jobDescriptions.find((jd) => jd.jd_id === msg.jd_id)?.title;
            return (
              <div key={msg.id} className="border rounded-md px-2 py-2 text-xs bg-muted/60 space-y-1">
                <div className="flex flex-col mb-1">
                  <span className="font-semibold text-pink-900">
                    {msg.from_company || "Azienda"}
                  </span>
                  {msg.from_name && (
                    <span className="text-[11px] text-muted-foreground">Contatto: {msg.from_name}</span>
                  )}
                </div>
                {jdTitle && (
                  <div className="text-[11px] text-muted-foreground mb-1">
                    Posizione: {jdTitle}
                  </div>
                )}
                <p className="text-[11px] whitespace-pre-wrap">{msg.message}</p>
                <button
                  type="button"
                  className="mt-1 text-[11px] text-primary hover:underline"
                  onClick={async () => {
                    setLastConversationJdId(msg.jd_id);
                    markInboxAsSeen(msg);
                    setOpenConversationJdId(msg.jd_id);
                    await fetchConversation(msg.jd_id);
                    setInboxOpen(false);
                  }}
                >
                  Accetta e apri chat
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Inbox azienda: candidature spontanee + nuove risposte in chat */}
      {authRole === "company" &&
        inboxOpen &&
        (unreadCompanyApplications.length > 0 || unreadCompanyReplies.length > 0) && (
        <div className="fixed top-16 right-4 z-40 w-80 max-h-[60vh] overflow-y-auto bg-white/95 shadow-lg rounded-lg border p-3 space-y-3">
          {unreadCompanyApplications.length > 0 && (
            <div className="flex items-center justify-between mb-1">
              <h2 className="text-sm font-semibold">Candidature spontanee</h2>
            </div>
          )}
          {unreadCompanyApplications.map((app) => {
            const jd = jobDescriptions.find((j) => j.jd_id === app.jd_id);
            return (
              <div
                key={app.id}
                className="w-full border rounded-md px-2 py-2 text-xs bg-muted/60"
              >
                <div className="flex flex-col mb-1">
                  <span className="font-semibold text-pink-900">
                    {app.candidate_name || "Candidato"}
                  </span>
                </div>
                {jd ? (
                  <div className="text-[11px] text-muted-foreground mb-1">
                    Per la posizione: {jd.title}
                  </div>
                ) : (
                  <div className="text-[11px] text-muted-foreground mb-1">
                    Candidatura spontanea
                  </div>
                )}
                <p className="text-[11px] line-clamp-2 whitespace-pre-wrap mb-1">{app.message}</p>
                <div className="flex justify-between gap-2 mt-1">
                  <button
                    type="button"
                    className="text-[11px] text-primary hover:underline"
                    onClick={() => {
                      markCompanyAppAsSeen(app);
                      setInboxOpen(false);
                      const anchor = document.getElementById("company-spontaneous-section");
                      if (anchor) {
                        anchor.scrollIntoView({ behavior: "smooth", block: "start" });
                      }
                    }}
                  >
                    Vai alla sezione
                  </button>
                  <button
                    type="button"
                    className="text-[11px] text-primary hover:underline"
                    onClick={async () => {
                      markCompanyAppAsSeen(app);
                      setInboxOpen(false);
                      const conv = { jdId: app.jd_id, candidateId: app.candidate_user_id };
                      setOpenCompanyConversation(conv);
                      setLastCompanyConversation(conv);
                      await fetchCompanyConversation(conv.jdId, conv.candidateId);
                    }}
                  >
                    Apri chat
                  </button>
                </div>
              </div>
            );
          })}

          {unreadCompanyReplies.length > 0 && (
            <div className="flex items-center justify-between mt-3 mb-1 border-t pt-2">
              <h2 className="text-sm font-semibold">Nuove risposte in chat</h2>
            </div>
          )}
          {unreadCompanyReplies.map((reply) => {
            const jd = jobDescriptions.find((j) => j.jd_id === reply.jd_id);
            return (
              <div
                key={reply.id}
                className="w-full border rounded-md px-2 py-2 text-xs bg-muted/60"
              >
                <div className="flex flex-col mb-1">
                  <span className="font-semibold text-pink-900">
                    {reply.candidate_name || "Candidato"}
                  </span>
                </div>
                {jd ? (
                  <div className="text-[11px] text-muted-foreground mb-1">
                    Per la posizione: {jd.title}
                  </div>
                ) : null}
                <p className="text-[11px] line-clamp-2 whitespace-pre-wrap mb-1">
                  {reply.message}
                </p>
                <div className="flex justify-end gap-2 mt-1">
                  <button
                    type="button"
                    className="text-[11px] text-primary hover:underline"
                    onClick={async () => {
                      markCompanyReplyAsSeen(reply);
                      setInboxOpen(false);
                      const conv = { jdId: reply.jd_id, candidateId: reply.candidate_id };
                      setOpenCompanyConversation(conv);
                      setLastCompanyConversation(conv);
                      await fetchCompanyConversation(conv.jdId, conv.candidateId);
                    }}
                  >
                    Apri chat
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Chat candidato-azienda */}
      {authRole === "candidate" && openConversationJdId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md max-h-[80vh] bg-white rounded-lg shadow-lg border flex flex-col">
            <div className="px-4 py-2 border-b flex items-center justify-between">
              <div className="flex flex-col">
                {(() => {
                  const jd = jobDescriptions.find((j) => j.jd_id === openConversationJdId);
                  const firstCompanyMsg = conversationMessages.find(
                    (m) => m.from_role === "company" && m.from_company
                  );
                  const companyName = firstCompanyMsg?.from_company || jd?.company || "";
                  return (
                    <>
                      <span className="text-sm font-semibold">
                        {companyName ? `Chat con ${companyName}` : "Chat con l'azienda"}
                      </span>
                      {jd && (
                        <span className="text-[11px] text-muted-foreground">Posizione: {jd.title}</span>
                      )}
                    </>
                  );
                })()}
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  className="text-[11px] text-muted-foreground hover:underline"
                  onClick={async () => {
                    if (!jwtToken || !openConversationJdId) {
                      return;
                    }
                    try {
                      const res = await fetch(`/api/contact/conversation?jd_id=${encodeURIComponent(openConversationJdId)}`, {
                        method: "DELETE",
                        headers: {
                          Authorization: `Bearer ${jwtToken}`,
                        },
                      });
                      if (!res.ok) {
                        const txt = await res.text();
                        toast({
                          title: "Errore cancellazione chat",
                          description: txt || "Non è stato possibile cancellare la chat.",
                          variant: "destructive",
                        });
                      } else {
                        setConversationMessages([]);
                        toast({
                          title: "Chat cancellata",
                          description: "La conversazione è stata svuotata.",
                        });
                      }
                    } catch (err) {
                      console.error("Errore cancellazione conversazione", err);
                      toast({
                        title: "Errore cancellazione chat",
                        description: "Non è stato possibile cancellare la chat.",
                        variant: "destructive",
                      });
                    }
                  }}
                >
                  Cancella chat
                </button>
                <button
                  type="button"
                  className="text-xs text-muted-foreground hover:underline"
                  onClick={() => {
                    setOpenConversationJdId(null);
                    setConversationMessages([]);
                    setConversationDraft("");
                  }}
                >
                  Chiudi
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2 text-xs bg-muted/40">
              {loadingConversation && conversationMessages.length === 0 && (
                <div className="text-center text-[11px] text-muted-foreground">Caricamento conversazione...</div>
              )}
              {!loadingConversation && conversationMessages.length === 0 && (
                <div className="text-center text-[11px] text-muted-foreground">
                  Nessun messaggio nella conversazione.
                </div>
              )}
              {conversationMessages.map((m) => {
                const isCandidate = m.from_role === "candidate";
                return (
                  <div
                    key={m.id}
                    className={`flex ${isCandidate ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[75%] rounded-lg px-2 py-1 ${
                        isCandidate ? "bg-primary text-primary-foreground" : "bg-white border"
                      }`}
                    >
                      {!isCandidate && (
                        <div className="text-[10px] font-semibold mb-0.5">
                          {m.from_company || m.from_name || "Azienda"}
                        </div>
                      )}
                      <div className="whitespace-pre-wrap text-[11px]">{m.message}</div>
                    </div>
                  </div>
                );
              })}
            </div>
            <form
              className="border-t px-3 py-2 flex items-center gap-2"
              onSubmit={async (e) => {
                e.preventDefault();
                const text = conversationDraft.trim();
                if (!text || !jwtToken || !openConversationJdId) return;
                try {
                  const res = await fetch("/api/contact/reply", {
                    method: "POST",
                    headers: {
                      "Content-Type": "application/json",
                      Authorization: `Bearer ${jwtToken}`,
                    },
                    body: JSON.stringify({ jd_id: openConversationJdId, message: text }),
                  });
                  if (!res.ok) {
                    const txt = await res.text();
                    toast({
                      title: "Errore invio messaggio",
                      description: txt || "Non è stato possibile inviare il messaggio.",
                      variant: "destructive",
                    });
                    return;
                  }
                  setConversationDraft("");
                  await fetchConversation(openConversationJdId);
                } catch (err) {
                  console.error("Errore invio messaggio conversazione", err);
                  toast({
                    title: "Errore invio messaggio",
                    description: "Non è stato possibile inviare il messaggio.",
                    variant: "destructive",
                  });
                }
              }}
            >
              <input
                type="text"
                className="flex-1 border rounded px-2 py-1 text-xs"
                placeholder="Scrivi un messaggio per organizzare la call..."
                value={conversationDraft}
                onChange={(e) => setConversationDraft(e.target.value)}
              />
              <button
                type="submit"
                className="text-xs px-3 py-1 rounded bg-primary text-primary-foreground hover:bg-primary/90"
                disabled={!conversationDraft.trim()}
              >
                Invia
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Chat azienda-candidato (speculare) */}
      {authRole === "company" && openCompanyConversation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md max-h-[80vh] bg-white rounded-lg shadow-lg border flex flex-col">
            <div className="px-4 py-2 border-b flex items-center justify-between">
              <div className="flex flex-col">
                <span className="text-sm font-semibold">Chat con il candidato</span>
                {(() => {
                  const jd = jobDescriptions.find((j) => j.jd_id === openCompanyConversation.jdId);
                  return jd ? (
                    <span className="text-[11px] text-muted-foreground">Posizione: {jd.title}</span>
                  ) : null;
                })()}
              </div>
              <button
                type="button"
                className="text-xs text-muted-foreground hover:underline"
                onClick={() => {
                  setOpenCompanyConversation(null);
                  setCompanyConversationMessages([]);
                  setCompanyConversationDraft("");
                }}
              >
                Chiudi
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2 text-xs bg-muted/40">
              {loadingCompanyConversation && companyConversationMessages.length === 0 && (
                <div className="text-center text-[11px] text-muted-foreground">Caricamento conversazione...</div>
              )}
              {!loadingCompanyConversation && companyConversationMessages.length === 0 && (
                <div className="text-center text-[11px] text-muted-foreground">
                  Nessun messaggio nella conversazione.
                </div>
              )}
              {companyConversationMessages.map((m) => {
                const isCompany = m.from_role === "company";
                return (
                  <div
                    key={m.id}
                    className={`flex ${isCompany ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[75%] rounded-lg px-2 py-1 ${
                        isCompany ? "bg-primary text-primary-foreground" : "bg-white border"
                      }`}
                    >
                      {!isCompany && (
                        <div className="text-[10px] font-semibold mb-0.5">
                          Candidato
                        </div>
                      )}
                      <div className="whitespace-pre-wrap text-[11px]">{m.message}</div>
                    </div>
                  </div>
                );
              })}
            </div>
            <form
              className="border-t px-3 py-2 flex items-center gap-2"
              onSubmit={async (e) => {
                e.preventDefault();
                if (!openCompanyConversation) return;
                const text = companyConversationDraft.trim();
                if (!text || !jwtToken) return;
                try {
                  const res = await fetch("/api/contact/candidate", {
                    method: "POST",
                    headers: {
                      "Content-Type": "application/json",
                      Authorization: `Bearer ${jwtToken}`,
                    },
                    body: JSON.stringify({
                      jd_id: openCompanyConversation.jdId,
                      candidate_id: openCompanyConversation.candidateId,
                      message: text,
                      // Continuazione di una conversazione, non per forza Top20;
                      // la classificazione in CandidateSection usa anche le candidature spontanee.
                      origin: "spontaneous",
                    }),
                  });
                  if (!res.ok) {
                    const txt = await res.text();
                    toast({
                      title: "Errore invio messaggio",
                      description: txt || "Non è stato possibile inviare il messaggio.",
                      variant: "destructive",
                    });
                    return;
                  }
                  setCompanyConversationDraft("");
                  await fetchCompanyConversation(openCompanyConversation.jdId, openCompanyConversation.candidateId);
                } catch (err) {
                  console.error("Errore invio messaggio conversazione azienda", err);
                  toast({
                    title: "Errore invio messaggio",
                    description: "Non è stato possibile inviare il messaggio.",
                    variant: "destructive",
                  });
                }
              }}
            >
              <input
                type="text"
                className="flex-1 border rounded px-2 py-1 text-xs"
                placeholder="Scrivi un messaggio al candidato..."
                value={companyConversationDraft}
                onChange={(e) => setCompanyConversationDraft(e.target.value)}
              />
              <button
                type="submit"
                className="text-xs px-3 py-1 rounded bg-primary text-primary-foreground hover:bg-primary/90"
                disabled={!companyConversationDraft.trim()}
              >
                Invia
              </button>
            </form>
            {/* Azioni di feedback finale sull'application */}
            <div className="border-t px-3 py-2 flex flex-wrap gap-2 items-center bg-muted/30">
              <span className="text-[11px] text-muted-foreground mr-1">Invia feedback finale:</span>
              <button
                type="button"
                className="text-[11px] px-2 py-1 rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-60"
                disabled={companyFeedbackSending !== null || !openCompanyConversation || !jwtToken}
                onClick={async () => {
                  if (!openCompanyConversation || !jwtToken) return;
                  try {
                    setCompanyFeedbackSending("positive");
                    const res = await fetch("/api/contact/feedback", {
                      method: "POST",
                      headers: {
                        "Content-Type": "application/json",
                        Authorization: `Bearer ${jwtToken}`,
                      },
                      body: JSON.stringify({
                        jd_id: openCompanyConversation.jdId,
                        candidate_id: openCompanyConversation.candidateId,
                        type: "positive",
                        message: "Il candidato è stato accettato e procederemo con i prossimi step.",
                      }),
                    });
                    if (!res.ok) {
                      const txt = await res.text();
                      throw new Error(txt || "Errore dal server");
                    }
                    toast({
                      title: "Feedback inviato",
                      description: "Feedback positivo inviato al candidato.",
                    });
                  } catch (err) {
                    console.error("Errore invio feedback positivo", err);
                    toast({
                      title: "Errore invio feedback",
                      description: "Non è stato possibile inviare il feedback positivo.",
                      variant: "destructive",
                    });
                  } finally {
                    setCompanyFeedbackSending(null);
                  }
                }}
              >
                Accettato
              </button>
              <button
                type="button"
                className="text-[11px] px-2 py-1 rounded bg-amber-500 text-black hover:bg-amber-600 disabled:opacity-60"
                disabled={companyFeedbackSending !== null || !openCompanyConversation || !jwtToken}
                onClick={async () => {
                  if (!openCompanyConversation || !jwtToken) return;
                  try {
                    setCompanyFeedbackSending("constructive");
                    const res = await fetch("/api/contact/feedback", {
                      method: "POST",
                      headers: {
                        "Content-Type": "application/json",
                        Authorization: `Bearer ${jwtToken}`,
                      },
                      body: JSON.stringify({
                        jd_id: openCompanyConversation.jdId,
                        candidate_id: openCompanyConversation.candidateId,
                        type: "constructive",
                        message: "Grazie per la candidatura. Al momento proseguiamo con altri profili, ma il tuo resta interessante per future opportunità.",
                      }),
                    });
                    if (!res.ok) {
                      const txt = await res.text();
                      throw new Error(txt || "Errore dal server");
                    }
                    toast({
                      title: "Feedback inviato",
                      description: "Feedback di gentile rifiuto inviato al candidato.",
                    });
                  } catch (err) {
                    console.error("Errore invio feedback costruttivo", err);
                    toast({
                      title: "Errore invio feedback",
                      description: "Non è stato possibile inviare il feedback di rifiuto.",
                      variant: "destructive",
                    });
                  } finally {
                    setCompanyFeedbackSending(null);
                  }
                }}
              >
                Rifiuto gentile
              </button>
              <button
                type="button"
                className="text-[11px] px-2 py-1 rounded bg-slate-500 text-white hover:bg-slate-600 disabled:opacity-60"
                disabled={companyFeedbackSending !== null || !openCompanyConversation || !jwtToken}
                onClick={async () => {
                  if (!openCompanyConversation || !jwtToken) return;
                  try {
                    setCompanyFeedbackSending("neutral");
                    const res = await fetch("/api/contact/feedback", {
                      method: "POST",
                      headers: {
                        "Content-Type": "application/json",
                        Authorization: `Bearer ${jwtToken}`,
                      },
                      body: JSON.stringify({
                        jd_id: openCompanyConversation.jdId,
                        candidate_id: openCompanyConversation.candidateId,
                        type: "neutral",
                        message: "Abbiamo concluso lo screening per questa posizione. Ti aggiorneremo in caso di sviluppi futuri.",
                      }),
                    });
                    if (!res.ok) {
                      const txt = await res.text();
                      throw new Error(txt || "Errore dal server");
                    }
                    toast({
                      title: "Feedback inviato",
                      description: "Feedback neutro inviato al candidato.",
                    });
                  } catch (err) {
                    console.error("Errore invio feedback neutro", err);
                    toast({
                      title: "Errore invio feedback",
                      description: "Non è stato possibile inviare il feedback neutro.",
                      variant: "destructive",
                    });
                  } finally {
                    setCompanyFeedbackSending(null);
                  }
                }}
              >
                Neutro
              </button>
            </div>
          </div>
        </div>
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
                {authRole === "company" ? "Gestisci Job Description" : "Gestisci candidature"}
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
                  user_id={decodeJwtUserId(jwtToken)}
                  isParsing={isParsing}
                  progressPct={progressPct}
                  progressLabel={progressLabel}
                  onUploadCV={handleUploadCV}
                  jwtToken={jwtToken}
                  onClearFeedback={clearMyFeedback}
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
                  companyName={currentUserProfile?.company}
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
                onCreateJd={handleCreateJd}
                companyName={currentUserProfile?.company}
                companyApplications={companyApplications}
                jwtToken={jwtToken}
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
                jwtToken={jwtToken}
                companyName={currentUserProfile?.company}
              />
            </TabsContent>
          </Tabs>
        )}
      </main>
    </div>
  );
};

export default Index;
