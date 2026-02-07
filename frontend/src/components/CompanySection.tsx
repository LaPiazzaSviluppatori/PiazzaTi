import { useEffect, useRef, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { JobDescription, ShortlistCandidate, AuditLogEntry } from "@/types";
import { FileText } from "lucide-react";
import CompanyProfileHeader from "./CompanyProfileHeader";
import { toast } from "@/hooks/use-toast";

interface CompanySectionProps {
  jobDescriptions: JobDescription[];
  onCreateJd: (jd: Omit<JobDescription, "id" | "createdAt">) => void;
  shortlist: ShortlistCandidate[];
  deiMode: boolean;
  auditLog: AuditLogEntry[];
  onCloseShortlist: (jdId: string, override?: { reason: string }) => void;
  companyName?: string | null;
}

export const CompanySection = ({
  jobDescriptions,
  onCreateJd,
  shortlist,
  deiMode,
  auditLog,
  onCloseShortlist,
  companyName,
}: CompanySectionProps) => {
  const storageKey = companyName
    ? `piazzati:companyPosts:${companyName}`
    : "piazzati:companyPosts";

  const [posts, setPosts] = useState<Array<{ id: string; text: string; image?: string; createdAt: string }>>([]);
  const [postText, setPostText] = useState("");
  const [postImageFile, setPostImageFile] = useState<File | null>(null);
  const [postImagePreview, setPostImagePreview] = useState<string | null>(null);

  const postImageInputRef = useRef<HTMLInputElement | null>(null);

  // Carica i post aziendali da localStorage all'avvio / cambio azienda
  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      if (raw) {
        const parsed = JSON.parse(raw) as Array<{ id: string; text: string; image?: string; createdAt: string }>;
        setPosts(parsed);
      } else {
        setPosts([]);
      }
    } catch {
      setPosts([]);
    }
  }, [storageKey]);

  // Salva i post aziendali in localStorage quando cambiano
  useEffect(() => {
    try {
      if (posts.length > 0) {
        localStorage.setItem(storageKey, JSON.stringify(posts));
      } else {
        localStorage.removeItem(storageKey);
      }
    } catch {
      // ignore storage errors
    }
  }, [posts, storageKey]);

  const handlePostImageChange = (f?: File | null) => {
    if (!f) {
      setPostImageFile(null);
      setPostImagePreview(null);
      return;
    }
    setPostImageFile(f);
    try {
      setPostImagePreview(URL.createObjectURL(f));
    } catch {
      setPostImagePreview(null);
    }
  };

  const handleCreatePost = () => {
    if (!postText.trim() && !postImageFile) {
      toast({ title: "Contenuto richiesto", description: "Inserisci testo o carica un'immagine.", variant: "destructive" });
      return;
    }
    const newPost = { id: String(Date.now()), text: postText.trim(), image: postImagePreview || undefined, createdAt: new Date().toISOString() };
    setPosts(prev => [newPost, ...prev]);
    setPostText("");
    handlePostImageChange(null);
    toast({ title: "Post pubblicato", description: "Il tuo post è visibile nella timeline aziendale." });
  };
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

    // Serializza i dati del form in uno schema JD coerente
    // Cast seniority in modo typesafe
    const allowedSeniorities = ["junior", "mid", "senior"] as const;
    const seniority = allowedSeniorities.includes(jdForm.constraints_seniority as typeof allowedSeniorities[number])
      ? jdForm.constraints_seniority as "junior" | "mid" | "senior"
      : "junior";

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
      jd_id: "", // placeholder, sarà gestito dal backend
      title: jdForm.title,
      company: jdForm.company,
      department: jdForm.department,
      description: jdForm.description,
      min_experience_years: Number(jdForm.min_experience_years) || 0,
      requirements: requirements.filter(r => r.type === "must").map(r => r.text),
      nice_to_have: requirements.filter(r => r.type === "nice").map(r => r.text),
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
          underrepresented: jdForm.dei_underrepresented ? Number(jdForm.dei_underrepresented) : undefined,
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

    onCreateJd(jdData);

    // Reset form
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

  return (
    <div className="space-y-6">
      {/* Company header */}
      <CompanyProfileHeader isCompany={true} companyName={companyName || ""} />

      {/* Posts */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-3">Post Aziendali</h3>
        <Textarea value={postText} onChange={e => setPostText(e.target.value)} placeholder="Condividi aggiornamenti o opportunità..." rows={2} />
        <div className="flex items-center gap-3 mt-3">
          <input
            ref={postImageInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={e => handlePostImageChange(e.target.files?.[0] || null)}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => postImageInputRef.current?.click()}
          >
            Carica immagine
          </Button>
          {postImagePreview && <div className="w-20 h-20 overflow-hidden rounded"><img src={postImagePreview} alt="preview" className="w-full h-full object-cover" /></div>}
          <div className="ml-auto">
            <Button onClick={handleCreatePost}>Pubblica</Button>
          </div>
        </div>

        <div className="mt-6 space-y-4">
          {posts.length === 0 ? (
            <div className="text-sm text-muted-foreground">Nessun post al momento.</div>
          ) : (
            posts.map(p => (
              <div key={p.id} className="p-3 border rounded-lg">
                <div className="text-sm text-muted-foreground mb-1">{new Date(p.createdAt).toLocaleString()}</div>
                <div className="mb-2">{p.text}</div>
                {p.image && <img src={p.image} alt="post" className="max-h-48 w-full object-cover rounded" />}
              </div>
            ))
          )}
        </div>
      </Card>
      {/* JD Creator moved to PipelineSection (GestisciCandidature) */}
    </div>
  );
};
