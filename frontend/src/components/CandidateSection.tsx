import { useState, useEffect, useCallback } from "react";
import { CustomSkeleton } from "./CustomSkeleton";
import "./custom-skeleton.css";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Candidate, JobDescription, Feedback, Project, OptInTag } from "@/types";
type ParsedSkill = string | { name?: string };
type ParsedExperience = {
  title: string;
  company: string;
  start_date?: string;
  startDate?: string;
  end_date?: string;
  endDate?: string;
  description?: string;
  city?: string;
};
import { Plus, Briefcase, Award, FileText, MessageSquare, Heart, Users, TrendingUp, Send, Upload, UserPlus, Tag } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { Progress } from "@/components/ui/progress";

interface CandidateSectionProps {
  candidate: Candidate;
  jobDescriptions: JobDescription[];
  selectedJdId: string | null;
  onSelectJd: (id: string) => void;
  feedback: Feedback[];
  onAddSkill: (skill: string) => void;
  onAddProject: (project: Project) => void;
  onAddPost: (content: string) => void;
  onAddTag: (tag: OptInTag) => void;
  onRemoveSkill: (skill: string) => void;
  onRemoveTag: (label: string, category: string) => void;
  suggestedProfiles: Candidate[];
  deiMode: boolean;
  onConnect: (candidateId: string) => void;
  onOpenProfile: (candidateId: string) => void;
  onCandidateParsed?: (updated: Partial<Candidate>) => void;
  user_id?: string; // backend user_id (UUID) passato dal parent
  isParsing: boolean;
  progressPct: number;
  progressLabel?: string;
  onUploadCV?: (cvFile: File | null, user_id?: string) => Promise<void>;
  jwtToken?: string | null;
  onClearFeedback?: () => void;
}

export const CandidateSection = ({
  candidate,
  jobDescriptions,
  selectedJdId,
  onSelectJd,
  feedback,
  onAddSkill,
  onAddProject,
  onAddPost,
  onAddTag,
  onRemoveSkill,
  onRemoveTag,
  suggestedProfiles,
  deiMode,
  onConnect,
  onOpenProfile,
  onCandidateParsed,
  user_id,
  isParsing,
  progressPct,
  progressLabel = "",
  onUploadCV,
  jwtToken,
  onClearFeedback,
}: CandidateSectionProps) => {
  // Wrapper per upload CV che lancia anche la pipeline batch
  const handleUploadCVWithBatch = async (cvFile: File | null, user_id?: string) => {
    if (!onUploadCV) return;
    await onUploadCV(cvFile, user_id);
    // Dopo upload/parse, triggera la pipeline batch
    try {
      const today = new Date().toISOString().slice(0, 10);
      const resp = await fetch("/api/parse/batch/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date: today })
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        toast({ title: "Errore pipeline batch", description: err.detail || resp.statusText, variant: "destructive" });
      } else {
        toast({ title: "Pipeline NLP avviata", description: "Elaborazione batch in corso..." });
      }
    } catch (e) {
      toast({ title: "Errore rete batch", description: String(e), variant: "destructive" });
    }
  };
  const [candidateData, setCandidateData] = useState<Candidate>(candidate);
  // Versioning modal state
  const [versioningModalOpen, setVersioningModalOpen] = useState(false);
  const [previousCvInfo, setPreviousCvInfo] = useState<{ previous_filename?: string } | null>(null);
  const [newCvInfo, setNewCvInfo] = useState<{ filename?: string } | null>(null);
  // Sincronizza lo stato locale quando cambia il candidato attivo dal genitore
  useEffect(() => {
    setCandidateData(candidate);
  }, [candidate]);

  // Sincronizza skills e tags dopo rimozione dal parent
  useEffect(() => {
    setCandidateData(prev => ({
      ...prev,
      skills: candidate.skills,
      optInTags: candidate.optInTags,
    }));
  }, [candidate.skills, candidate.optInTags]);
  const [newSkill, setNewSkill] = useState("");
  // Rimozione skill: chiama il parent
  const handleRemoveSkill = (skillName: string) => {
    onRemoveSkill(skillName);
    setCandidateData(prev => ({
      ...prev,
      skills: prev.skills.filter(s => s.name.toLowerCase() !== skillName.toLowerCase()),
    }));
  };
  const [newPost, setNewPost] = useState("");
  const [lastParsedUpdates, setLastParsedUpdates] = useState<Partial<Candidate> | null>(null);
  
  // Project modal
  const [projectModalOpen, setProjectModalOpen] = useState(false);
  const [projectForm, setProjectForm] = useState({ title: "", description: "", technologies: "", link: "" });
  
  // Tag modal
  const [tagModalOpen, setTagModalOpen] = useState(false);
  const [newTagLabel, setNewTagLabel] = useState("");
  const [newTagCategory, setNewTagCategory] = useState<"diversity" | "background" | "other">("diversity");

  // Remove tag: chiama il parent
  const handleRemoveTag = (label: string, category: string) => {
    onRemoveTag(label, category);
    setCandidateData(prev => ({
      ...prev,
      optInTags: prev.optInTags.filter(t => !(t.label === label && t.category === category)),
    }));
  };

  // CV file upload
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  // Stato parsing e progress ora vengono dal parent tramite prop
  const isSpinning = isParsing && progressPct >= 100;
  // Helper: build location by fully replacing any existing email/phone anywhere
  const buildLocationWithContact = (currentLocation: string | undefined, contactSuffix: string): string => {
    const existing = (currentLocation || "").trim();
    const emailPhoneRegex = /([\w.+-]+@[\w.-]+\.[A-Za-z]{2,})|((?:\+\d{1,3}\s?)?(?:\d[\d\s-]?){6,})/g;
    // Remove all email/phone occurrences
    const cleaned = existing.replace(emailPhoneRegex, "").replace(/\s*•\s*/g, " ").replace(/\s*\|\s*/g, " | ").trim();
    // Take first non-empty token before pipe as base location, strip trailing separators
    const baseToken = cleaned.split("|")[0].trim().replace(/\s+$/g, "");
    const baseIsEmpty = baseToken.length === 0;
    return baseIsEmpty ? contactSuffix : `${baseToken} | ${contactSuffix}`;
  };

  // Candidate Login Modal state

  const handleAddSkill = async () => {
    const skillName = newSkill.trim();
    if (!skillName) return;
    // Check if skill already exists (case-insensitive)
    const exists = candidateData.skills.some(s => s.name.toLowerCase() === skillName.toLowerCase());
    if (exists) {
      toast({ title: "Skill già presente", description: `La skill "${skillName}" è già nel profilo.`, variant: "destructive" });
      return;
    }
    // Add and deduplicate
    setCandidateData(prev => {
      const skills = [...(prev.skills || []), { name: skillName }];
      const uniqueSkills = skills.filter((skill, idx, arr) =>
        arr.findIndex(s => s.name.toLowerCase() === skill.name.toLowerCase()) === idx
      );
      return { ...prev, skills: uniqueSkills };
    });
    onAddSkill(skillName);
    setNewSkill("");
    toast({ title: "Skill aggiunta", description: `"${skillName}" aggiunta al profilo` });

    // Se abbiamo uno user_id backend, aggiorna anche il JSON del CV e gli embeddings
    if (user_id) {
      try {
        const resp = await fetch(`/api/parse/user/${user_id}/skills/append`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ skills: [skillName] }),
        });
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          console.error("Errore aggiornamento skills/embeddings", err);
          toast({
            title: "Errore aggiornamento profilo",
            description: err.detail || resp.statusText,
            variant: "destructive",
          });
        }
      } catch (e) {
        console.error("Errore rete aggiornamento skills/embeddings", e);
        toast({
          title: "Errore di rete",
          description: String(e),
          variant: "destructive",
        });
      }
    }
  };

  const handleAddPost = () => {
    if (newPost.trim()) {
      onAddPost(newPost.trim());
      setNewPost("");
      toast({ title: "Post pubblicato", description: "Il tuo post è ora visibile sul tuo wall" });
    }
  };

  const handleAddProject = () => {
    if (!projectForm.title.trim() || !projectForm.description.trim()) {
      toast({ title: "Campi obbligatori", description: "Titolo e descrizione sono richiesti", variant: "destructive" });
      return;
    }

    const newProject: Project = {
      title: projectForm.title,
      description: projectForm.description,
      technologies: projectForm.technologies.split(",").map(t => t.trim()).filter(t => t),
      link: projectForm.link || undefined,
    };

    onAddProject(newProject);
    setProjectForm({ title: "", description: "", technologies: "", link: "" });
    setProjectModalOpen(false);
    toast({ title: "Progetto aggiunto", description: `"${newProject.title}" aggiunto al portfolio` });
  };

  const handleAddTag = () => {
    if (!newTagLabel.trim()) {
      toast({ title: "Etichetta richiesta", description: "Inserisci un'etichetta per il tag", variant: "destructive" });
      return;
    }

    const newTag = {
      label: newTagLabel.trim(),
      category: newTagCategory,
    };

    // Check if tag already exists
    const exists = candidateData.optInTags.some(t => t.label === newTag.label && t.category === newTag.category);
    if (exists) {
      toast({ title: "Tag già presente", description: `Il tag "${newTag.label}" è già presente.`, variant: "destructive" });
      return;
    }
    // Add and deduplicate
    setCandidateData(prev => {
      const tags = [...(prev.optInTags || []), newTag];
      // Deduplicate by label+category
      const uniqueTags = tags.filter((tag, idx, arr) =>
        arr.findIndex(t => t.label === tag.label && t.category === tag.category) === idx
      );
      return { ...prev, optInTags: uniqueTags };
    });
    onAddTag(newTag);
    setNewTagLabel("");
    setTagModalOpen(false);
    toast({ title: "Tag aggiunto", description: `Tag "${newTag.label}" aggiunto al profilo` });
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* CV Versioning Modal */}
      <Dialog open={versioningModalOpen} onOpenChange={setVersioningModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Versione CV trovata</DialogTitle>
            <DialogDescription>
              Esiste una versione precedente del tuo CV.<br />
              Vuoi mantenere la nuova versione o ripristinare la precedente?
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <strong>Nuovo CV:</strong> {newCvInfo?.filename}
            </div>
            <div>
              <strong>Precedente:</strong> {previousCvInfo?.previous_filename}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setVersioningModalOpen(false)}>Mantieni Nuovo</Button>
            <Button
              onClick={async () => {
                // Call backend to delete new CV and restore previous
                if (newCvInfo?.filename) {
                  await fetch(`/api/cv/delete`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ filename: newCvInfo.filename })
                  });
                  toast({ title: "Ripristinato CV precedente", description: "La versione precedente è stata ripristinata." });
                  setVersioningModalOpen(false);
                }
              }}
            >Ripristina Precedente</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {/* Main Profile Column */}
      <div className="lg:col-span-2 space-y-6">
        {/* Profile Header */}
        <Card className={`p-6 ${isParsing && progressPct < 100 ? 'yt-shimmer' : ''}`}>
          <div className="flex items-start gap-4">
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-primary text-2xl font-bold text-primary-foreground">
              {candidateData.name.split(" ").map((n) => n[0]).join("")}
            </div>
            <div className="flex-1">
              <div className="flex items-start justify-between">
                <div>
                  {deiMode && candidateData.optInTags.length > 0 && (
                    <div className="mt-2">
                      <Badge variant="outline" className="border-success text-success">
                        {candidateData.optInTags.length} tag opt-in
                      </Badge>
                    </div>
                  )}
                </div>
              </div>
              <div className="mt-1 text-2xl font-extrabold leading-tight tracking-wide" style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>{candidateData.name}</div>
              {candidateData.email && (
                <div className="text-sm text-muted-foreground mt-1"> {candidateData.email}</div>
              )}
              {candidateData.phone && (
                <div className="text-sm text-muted-foreground mt-1"> {candidateData.phone}</div>
              )}
              {isSpinning ? (
                <div className="mt-2 space-y-2">
                  <CustomSkeleton height={18} style={{marginBottom: 4}} />
                  <CustomSkeleton height={18} style={{marginBottom: 4}} />
                  <CustomSkeleton height={18} />
                </div>
              ) : (
                <p className="mt-2">{candidateData.summary}</p>
              )}
              {candidateData.optInTags.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {candidateData.optInTags.map((tag, i) => (
                    <Badge key={i} variant="outline" className="border-success text-success flex items-center gap-1">
                      <span>{tag.label}</span>
                      <button
                        type="button"
                        aria-label={`Rimuovi ${tag.label}`}
                        className="ml-1 text-xs text-destructive hover:text-destructive-foreground px-1 rounded focus:outline-none"
                        onClick={() => handleRemoveTag(tag.label, tag.category)}
                      >×</button>
                    </Badge>
                  ))}
                  {deiMode && (
                    <Button variant="ghost" size="sm" onClick={() => setTagModalOpen(true)}>
                      <Plus className="h-3 w-3 mr-1" />
                      Tag
                    </Button>
                  )}
                </div>
              )}
              {deiMode && candidateData.optInTags.length === 0 && (
                <div className="mt-3">
                  <Button variant="outline" size="sm" onClick={() => setTagModalOpen(true)}>
                    <Tag className="h-3 w-3 mr-1" />
                    Aggiungi tag opt-in
                  </Button>
                </div>
              )}
            </div>
          </div>
        </Card>

        {/* Overlay e barra di caricamento SOLO sulla sezione centrale, non sull'header */}
        <div style={{position:'relative'}}>
            {/* Nessun overlay/spinner sopra le componenti centrali */}
          {/* Tutto il contenuto centrale rimane sempre visibile sotto l'overlay */}
        </div>

        {/* Skills */}
        <Card className={`p-6 ${isParsing && progressPct < 100 ? 'yt-shimmer' : ''}`}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Award className="h-5 w-5 text-primary" />
              Competenze
            </h3>
          </div>
          <div className="flex flex-wrap gap-2 mb-4">
            {isSpinning ? (
              Array.from({ length: 6 }).map((_, i) => (
                <CustomSkeleton key={i} width={90} height={24} />
              ))
            ) : (
              candidateData.skills.map((skill, i) => (
                <Badge key={i} variant="secondary" className="flex items-center gap-1">
                  <span>{skill.name}</span>
                  {skill.level && <span className="ml-1 text-xs opacity-70">({skill.level})</span>}
                  <button
                    type="button"
                    aria-label={`Rimuovi ${skill.name}`}
                    className="ml-1 text-xs text-destructive hover:text-destructive-foreground px-1 rounded focus:outline-none"
                    onClick={() => handleRemoveSkill(skill.name)}
                  >
                    ×
                  </button>
                </Badge>
              ))
            )}
          </div>
          <div className="flex gap-2">
            <Input
              placeholder="Nuova skill..."
              value={newSkill}
              onChange={(e) => setNewSkill(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddSkill()}
            />
            <Button onClick={handleAddSkill}>
              <Plus className="h-4 w-4" />
            </Button>
          </div>
        </Card>

        {/* Experience */}
        <Card className={`p-6 ${isParsing && progressPct < 100 ? 'yt-shimmer' : ''}`}>
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
            <Briefcase className="h-5 w-5 text-primary" />
            Esperienze
          </h3>
          <div className="space-y-4">
            {isSpinning ? (
              Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="pl-4">
                  <CustomSkeleton width={240} height={20} />
                  <div className="mt-1"><CustomSkeleton width={280} height={16} /></div>
                  <div className="mt-2">
                    <CustomSkeleton height={16} style={{marginBottom: 4}} />
                    <CustomSkeleton height={16} />
                  </div>
                </div>
              ))
            ) : (
              candidateData.experiences.map((exp, i) => (
                <div key={i} className="border-l-2 border-primary pl-4">
                  <h4 className="font-semibold">{exp.title}</h4>
                  <p className="text-sm text-muted-foreground">
                    {exp.company} • {exp.period}
                  </p>
                  <p className="text-sm mt-1" style={{overflowWrap: 'break-word', wordBreak: 'break-word', whiteSpace: 'pre-line'}}>{exp.description}</p>
                </div>
              ))
            )}
          </div>
        </Card>

        {/* Projects */}
        <Card className={`p-6 ${isParsing && progressPct < 100 ? 'yt-shimmer' : ''}`}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <FileText className="h-5 w-5 text-primary" />
              Progetti
            </h3>
            <Button variant="outline" size="sm" onClick={() => setProjectModalOpen(true)}>
              <Plus className="h-4 w-4 mr-1" />
              Progetto
            </Button>
          </div>
          <div className="space-y-4">
            {isSpinning ? (
              Array.from({ length: 2 }).map((_, i) => (
                <div key={i} className="rounded-lg border p-4">
                  <CustomSkeleton width={220} height={20} />
                  <div className="mt-2">
                    <CustomSkeleton height={16} style={{marginBottom: 4}} />
                    <CustomSkeleton height={16} />
                  </div>
                  <div className="flex gap-2 mt-2">
                    {Array.from({ length: 4 }).map((_, j) => (
                      <CustomSkeleton key={j} width={70} height={20} />
                    ))}
                  </div>
                </div>
              ))
            ) : (
              candidateData.projects.map((project, i) => (
                <div key={i} className="rounded-lg border p-4">
                  <h4 className="font-semibold">{project.title}</h4>
                  <p className="text-sm text-muted-foreground mt-1">{project.description}</p>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {project.technologies.map((tech, j) => (
                      <Badge key={j} variant="outline" className="text-xs">
                        {tech}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>

        {/* Wall / Posts */}
        <Card className={`p-6 ${isParsing && progressPct < 100 ? 'yt-shimmer' : ''}`}>
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
            <MessageSquare className="h-5 w-5 text-primary" />
            Wall
          </h3>
          <div className="space-y-4 mb-4">
            {isSpinning ? (
              Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="rounded-lg border p-4">
                  <CustomSkeleton height={16} style={{marginBottom: 4}} />
                  <CustomSkeleton height={16} />
                  <div className="mt-2"><CustomSkeleton width={140} height={14} /></div>
                </div>
              ))
            ) : (
              candidateData.posts.map((post) => (
                <div key={post.id} className="rounded-lg border p-4">
                  <p className="text-sm">{post.content}</p>
                  <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                    <span>{post.date}</span>
                    <button className="flex items-center gap-1 hover:text-foreground transition-colors">
                      <Heart className="h-3 w-3" />
                      {post.likes}
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
          <div className="space-y-2">
            <Textarea
              placeholder="Condividi un pensiero, un link o un aggiornamento..."
              value={newPost}
              onChange={(e) => setNewPost(e.target.value)}
            />
            <Button onClick={handleAddPost} className="w-full">
              <Plus className="h-4 w-4 mr-1" />
              Pubblica Post
            </Button>
          </div>
        </Card>
      </div>

      {/* Sidebar Column */}
      <div className="space-y-6">
        {/* Upload CV da file */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
            <Upload className="h-5 w-5 text-primary" />
            Carica CV (file)
          </h3>
          <Input
            type="file"
            accept=".pdf,.doc,.docx,.txt"
            onChange={e => setCvFile(e.target.files?.[0] || null)}
          />
          <Button
            variant="outline"
            className="w-full mt-2"
            onClick={() => handleUploadCVWithBatch(cvFile, user_id)}
            disabled={uploading || !cvFile || !onUploadCV}
          >
            <Upload className="h-4 w-4 mr-2" />
            {uploading ? "Caricamento..." : "Carica CV"}
          </Button>
          
          {isParsing && (
            <div className="mt-4">
              {progressPct < 100 ? (
                <>
                  <Progress value={progressPct} />
                  <div className="mt-2 text-xs text-muted-foreground">
                    {progressLabel || `Elaborazione… ${progressPct}%`}
                  </div>
                </>
              ) : (
                <div style={{ display: 'flex', justifyContent: 'center', marginTop: 8 }}>
                  <div style={{
                    width: '40px',
                    height: '40px',
                    border: '6px solid hsl(var(--secondary))',
                    borderTop: '6px solid hsl(var(--primary))',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite'
                  }} />
                  <style>{`
                    @keyframes spin {
                      0% { transform: rotate(0deg); }
                      100% { transform: rotate(360deg); }
                    }
                  `}</style>
                </div>
              )}
            </div>
          )}
        </Card>

        {/* Feedback dalle aziende */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold">Feedback dalle aziende</h3>
            {user_id && feedback.length > 0 && (
              <button
                type="button"
                className="text-[11px] text-muted-foreground hover:underline"
                onClick={onClearFeedback}
              >
                Cancella tutti
              </button>
            )}
          </div>
          {!user_id && (
            <p className="text-xs text-muted-foreground">
              Accedi e carica il tuo CV per ricevere feedback dalle aziende sulle posizioni a cui ti candidi o in cui compari nella Top 20.
            </p>
          )}
          {user_id && feedback.length === 0 && (
            <p className="text-xs text-muted-foreground">
              Al momento non hai ancora ricevuto feedback dalle aziende.
            </p>
          )}
          {user_id && feedback.length > 0 && (
            <div className="space-y-3">
              {feedback.map((item) => {
                const label =
                  item.type === "positive"
                    ? "Accettato"
                    : item.type === "constructive"
                    ? "Gentile rifiuto"
                    : "Neutro";
                const badgeClass =
                  item.type === "positive"
                    ? "bg-success text-success-foreground"
                    : item.type === "constructive"
                    ? "border-warning text-warning"
                    : "";
                return (
                  <div key={item.id} className="rounded-lg border p-3 text-sm">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex flex-col">
                        <span className="font-semibold">{item.from}</span>
                        {(item.jdTitle || item.company) && (
                          <span className="text-[11px] text-muted-foreground">
                            {item.jdTitle}
                            {item.jdTitle && item.company ? " • " : ""}
                            {item.company && !item.jdTitle ? item.company : item.company && item.jdTitle ? item.company : null}
                          </span>
                        )}
                      </div>
                      <Badge
                        variant={item.type === "positive" ? "default" : "outline"}
                        className={badgeClass}
                      >
                        {label}
                      </Badge>
                    </div>
                    {item.date && (
                      <p className="text-[11px] text-muted-foreground mb-1">
                        {new Date(item.date).toLocaleDateString()}
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground">{item.message}</p>
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        {/* Profili Consigliati */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
            <Users className="h-5 w-5 text-primary" />
            Profili Consigliati
          </h3>
          <div className="space-y-3">
            {suggestedProfiles.slice(0, 3).map((profile) => (
              <div key={profile.id} className="rounded-lg border p-3">
                <div className="flex items-center gap-2 mb-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                    {profile.name.split(" ").map((n) => n[0]).join("")}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-sm truncate">{profile.name}</p>
                    <p className="text-xs text-muted-foreground truncate">{profile.location}</p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1 mb-2">
                  {profile.skills.slice(0, 3).map((skill, i) => (
                    <Badge key={i} variant="outline" className="text-xs">
                      {skill.name}
                    </Badge>
                  ))}
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" className="flex-1" onClick={() => onConnect(profile.id)}>
                    <UserPlus className="h-3 w-3 mr-1" />
                    Connetti
                  </Button>
                  {/* <Button variant="ghost" size="sm" onClick={() => openLoginForCandidate(profile.id)}>
                    <TrendingUp className="h-4 w-4" />
                  </Button> */}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Project Modal */}
      <Dialog open={projectModalOpen} onOpenChange={setProjectModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Aggiungi Progetto</DialogTitle>
            <DialogDescription>Inserisci i dettagli del progetto da aggiungere al tuo portfolio.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="project-title">Titolo *</Label>
              <Input
                id="project-title"
                value={projectForm.title}
                onChange={(e) => setProjectForm({ ...projectForm, title: e.target.value })}
                placeholder="es. Dashboard Analytics"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="project-desc">Descrizione *</Label>
              <Textarea
                id="project-desc"
                value={projectForm.description}
                onChange={(e) => setProjectForm({ ...projectForm, description: e.target.value })}
                placeholder="Descrivi il progetto..."
                rows={3}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="project-tech">Tecnologie (separate da virgola)</Label>
              <Input
                id="project-tech"
                value={projectForm.technologies}
                onChange={(e) => setProjectForm({ ...projectForm, technologies: e.target.value })}
                placeholder="es. React, TypeScript, Tailwind"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="project-link">Link (opzionale)</Label>
              <Input
                id="project-link"
                value={projectForm.link}
                onChange={(e) => setProjectForm({ ...projectForm, link: e.target.value })}
                placeholder="https://github.com/..."
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setProjectModalOpen(false)}>Annulla</Button>
            <Button onClick={handleAddProject}>Aggiungi Progetto</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Tag Modal */}
      <Dialog open={tagModalOpen} onOpenChange={setTagModalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Aggiungi Tag Opt-in</DialogTitle>
            <DialogDescription>
              I tag opt-in sono volontari e usati solo per reportistica/guardrail, non per il punteggio.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="tag-label">Etichetta *</Label>
              <Input
                id="tag-label"
                value={newTagLabel}
                onChange={(e) => setNewTagLabel(e.target.value)}
                placeholder="es. Women in Tech, First-gen graduate..."
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="tag-category">Categoria</Label>
              <Select value={newTagCategory} onValueChange={(v) => setNewTagCategory(v as typeof newTagCategory)}>
                <SelectTrigger id="tag-category">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="diversity">Diversity</SelectItem>
                  <SelectItem value="background">Background</SelectItem>
                  <SelectItem value="other">Other</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTagModalOpen(false)}>Annulla</Button>
            <Button onClick={handleAddTag}>Aggiungi Tag</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
