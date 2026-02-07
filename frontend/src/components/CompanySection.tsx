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
    : null;

  type CompanyPost = { id: string; text: string; images?: string[]; createdAt: string };

  const [posts, setPosts] = useState<CompanyPost[]>([]);
  const [postText, setPostText] = useState("");
  const [postImageFiles, setPostImageFiles] = useState<File[]>([]);
  const [postImagePreviews, setPostImagePreviews] = useState<string[]>([]);
  const [editingPostId, setEditingPostId] = useState<string | null>(null);

  const postTextAreaRef = useRef<HTMLTextAreaElement | null>(null);
  const postImageInputRef = useRef<HTMLInputElement | null>(null);

  const emojiOptions = ["😊", "🚀", "🎯", "💼", "📣", "🔥"];

  // Carica i post aziendali da localStorage all'avvio / cambio azienda
  useEffect(() => {
    try {
      if (!storageKey) {
        setPosts([]);
        return;
      }

      const raw = localStorage.getItem(storageKey);
      if (!raw) {
        setPosts([]);
        return;
      }

      const parsed = JSON.parse(raw) as Array<CompanyPost & { image?: string }>;
      const normalized: CompanyPost[] = parsed.map((p) => {
        if (p.images && p.images.length > 0) return { ...p, images: [...p.images] };
        if (p.image) {
          return { id: p.id, text: p.text, images: [p.image], createdAt: p.createdAt };
        }
        return { id: p.id, text: p.text, images: [], createdAt: p.createdAt };
      });

      setPosts(normalized);
    } catch {
      setPosts([]);
    }
  }, [storageKey]);

  // Salva i post aziendali in localStorage quando cambiano
  useEffect(() => {
    try {
      if (!storageKey) return;
      if (posts.length > 0) {
        localStorage.setItem(storageKey, JSON.stringify(posts));
      } else {
        localStorage.removeItem(storageKey);
      }
    } catch {
      // ignore storage errors
    }
  }, [posts, storageKey]);

  const handlePostImageChange = (files?: FileList | null) => {
    if (!files || files.length === 0) {
      setPostImageFiles([]);
      setPostImagePreviews([]);
      return;
    }

    const fileArray = Array.from(files);
    setPostImageFiles(fileArray);

    const readers = fileArray.map(
      (file) =>
        new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onloadend = () => {
            if (typeof reader.result === "string") {
              resolve(reader.result);
            } else {
              reject(new Error("Invalid file result"));
            }
          };
          reader.onerror = () => reject(new Error("Error reading file"));
          reader.readAsDataURL(file);
        })
    );

    Promise.all(readers)
      .then((urls) => {
        setPostImagePreviews(urls);
      })
      .catch(() => {
        setPostImagePreviews([]);
      });
  };

  const handleCreatePost = () => {
    if (!postText.trim() && postImagePreviews.length === 0) {
      toast({ title: "Contenuto richiesto", description: "Inserisci testo o carica un'immagine.", variant: "destructive" });
      return;
    }

    if (editingPostId) {
      setPosts(prev =>
        prev.map(p =>
          p.id === editingPostId
            ? {
                ...p,
                text: postText.trim(),
                images: postImagePreviews.length > 0 ? [...postImagePreviews] : [],
              }
            : p
        )
      );
      toast({ title: "Post aggiornato", description: "Le modifiche al post sono state salvate." });
    } else {
      const newPost: CompanyPost = {
        id: String(Date.now()),
        text: postText.trim(),
        images: postImagePreviews.length > 0 ? [...postImagePreviews] : [],
        createdAt: new Date().toISOString(),
      };
      setPosts(prev => [newPost, ...prev]);
      toast({ title: "Post pubblicato", description: "Il tuo post è visibile nella timeline aziendale." });
    }

    setPostText("");
    setPostImageFiles([]);
    setPostImagePreviews([]);
    setEditingPostId(null);
  };

  const handleDeletePost = (id: string) => {
    setPosts(prev => prev.filter(p => p.id !== id));
    toast({ title: "Post eliminato", description: "Il post è stato rimosso dalla timeline." });
  };

  const handleEditPost = (post: CompanyPost) => {
    setEditingPostId(post.id);
    setPostText(post.text);
    setPostImagePreviews(post.images ?? []);
    setPostImageFiles([]);
  };

  const handleBoldClick = () => {
    const textarea = postTextAreaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart ?? 0;
    const end = textarea.selectionEnd ?? 0;

    if (start === end) {
      const insertion = "****";
      const newText = postText.slice(0, start) + insertion + postText.slice(end);
      setPostText(newText);
      requestAnimationFrame(() => {
        textarea.focus();
        textarea.selectionStart = start + 2;
        textarea.selectionEnd = start + 2;
      });
      return;
    }

    const selected = postText.slice(start, end);
    const newText = postText.slice(0, start) + `**${selected}**` + postText.slice(end);
    setPostText(newText);
    requestAnimationFrame(() => {
      textarea.focus();
      textarea.selectionStart = start;
      textarea.selectionEnd = start + selected.length + 4;
    });
  };

  const handleItalicClick = () => {
    const textarea = postTextAreaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart ?? 0;
    const end = textarea.selectionEnd ?? 0;

    if (start === end) {
      const insertion = "__";
      const newText = postText.slice(0, start) + insertion + postText.slice(end);
      setPostText(newText);
      requestAnimationFrame(() => {
        textarea.focus();
        textarea.selectionStart = start + 1;
        textarea.selectionEnd = start + 1;
      });
      return;
    }

    const selected = postText.slice(start, end);
    const newText = postText.slice(0, start) + `_${selected}_` + postText.slice(end);
    setPostText(newText);
    requestAnimationFrame(() => {
      textarea.focus();
      textarea.selectionStart = start;
      textarea.selectionEnd = start + selected.length + 2;
    });
  };

  const handleBulletClick = () => {
    const textarea = postTextAreaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart ?? 0;
    const lineStart = postText.lastIndexOf("\n", start - 1) + 1;
    const newText =
      postText.slice(0, lineStart) +
      "- " +
      postText.slice(lineStart);
    setPostText(newText);
    requestAnimationFrame(() => {
      textarea.focus();
      const cursor = start + 2;
      textarea.selectionStart = cursor;
      textarea.selectionEnd = cursor;
    });
  };

  const handleNumberedClick = () => {
    const textarea = postTextAreaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart ?? 0;
    const lineStart = postText.lastIndexOf("\n", start - 1) + 1;
    const newText =
      postText.slice(0, lineStart) +
      "1. " +
      postText.slice(lineStart);
    setPostText(newText);
    requestAnimationFrame(() => {
      textarea.focus();
      const cursor = start + 3;
      textarea.selectionStart = cursor;
      textarea.selectionEnd = cursor;
    });
  };

  const handleInsertEmoji = (emoji: string) => {
    const textarea = postTextAreaRef.current;
    if (!textarea) {
      setPostText(prev => prev + emoji);
      return;
    }

    const start = textarea.selectionStart ?? postText.length;
    const end = textarea.selectionEnd ?? postText.length;
    const newText = postText.slice(0, start) + emoji + postText.slice(end);
    setPostText(newText);
    requestAnimationFrame(() => {
      textarea.focus();
      const cursor = start + emoji.length;
      textarea.selectionStart = cursor;
      textarea.selectionEnd = cursor;
    });
  };

  const renderPostText = (text: string) => {
    const renderInline = (value: string, keyPrefix: string) => {
      const tokens = value.split(/(\*\*[^*]+\*\*|_[^_]+_)/g).filter(Boolean);
      return tokens.map((token, idx) => {
        if (token.startsWith("**") && token.endsWith("**")) {
          return (
            <strong key={`${keyPrefix}-b-${idx}`}>
              {token.slice(2, -2)}
            </strong>
          );
        }
        if (token.startsWith("_") && token.endsWith("_")) {
          return (
            <em key={`${keyPrefix}-i-${idx}`}>
              {token.slice(1, -1)}
            </em>
          );
        }
        return <span key={`${keyPrefix}-t-${idx}`}>{token}</span>;
      });
    };

    const lines = text.split("\n");
    const blocks: { type: "p" | "ul" | "ol"; lines: string[] }[] = [];

    for (const line of lines) {
      const bulletMatch = line.startsWith("- ");
      const numberedMatch = /^\d+\.\s+/.test(line);

      if (bulletMatch) {
        const content = line.slice(2);
        const last = blocks[blocks.length - 1];
        if (last && last.type === "ul") {
          last.lines.push(content);
        } else {
          blocks.push({ type: "ul", lines: [content] });
        }
      } else if (numberedMatch) {
        const content = line.replace(/^\d+\.\s+/, "");
        const last = blocks[blocks.length - 1];
        if (last && last.type === "ol") {
          last.lines.push(content);
        } else {
          blocks.push({ type: "ol", lines: [content] });
        }
      } else {
        blocks.push({ type: "p", lines: [line] });
      }
    }

    return blocks.map((block, blockIndex) => {
      if (block.type === "ul") {
        return (
          <ul key={`b-${blockIndex}`} className="list-disc pl-5 space-y-1">
            {block.lines.map((l, idx) => (
              <li key={`b-${blockIndex}-l-${idx}`}>
                {renderInline(l, `b-${blockIndex}-l-${idx}`)}
              </li>
            ))}
          </ul>
        );
      }
      if (block.type === "ol") {
        return (
          <ol key={`b-${blockIndex}`} className="list-decimal pl-5 space-y-1">
            {block.lines.map((l, idx) => (
              <li key={`b-${blockIndex}-l-${idx}`}>
                {renderInline(l, `b-${blockIndex}-l-${idx}`)}
              </li>
            ))}
          </ol>
        );
      }
      // paragraph
      return (
        <p key={`b-${blockIndex}`} className="whitespace-pre-wrap">
          {renderInline(block.lines[0], `b-${blockIndex}-p`)}
        </p>
      );
    });
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
        <Textarea
          ref={postTextAreaRef}
          value={postText}
          onChange={e => setPostText(e.target.value)}
          placeholder="Condividi aggiornamenti o opportunità..."
          rows={2}
        />
        <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleBoldClick}
              className="px-2 py-0.5 border rounded font-bold hover:bg-muted/60"
            >
              B
            </button>
            <button
              type="button"
              onClick={handleItalicClick}
              className="px-2 py-0.5 border rounded italic hover:bg-muted/60"
            >
              i
            </button>
            <button
              type="button"
              onClick={handleBulletClick}
              className="px-2 py-0.5 border rounded hover:bg-muted/60"
            >
              •
            </button>
            <button
              type="button"
              onClick={handleNumberedClick}
              className="px-2 py-0.5 border rounded hover:bg-muted/60"
            >
              1.
            </button>
            <span>Formato</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="mr-1">Emoji:</span>
            {emojiOptions.map(emoji => (
              <button
                key={emoji}
                type="button"
                onClick={() => handleInsertEmoji(emoji)}
                className="px-1.5 py-0.5 rounded hover:bg-muted/60"
              >
                {emoji}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3 mt-3">
          <input
            ref={postImageInputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={e => handlePostImageChange(e.target.files)}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => postImageInputRef.current?.click()}
          >
            Carica immagine
          </Button>
          {postImagePreviews.length > 0 && (
            <div className="flex gap-2 max-w-xs overflow-x-auto">
              {postImagePreviews.map((src, idx) => (
                <div key={idx} className="w-20 h-20 flex items-center justify-center overflow-hidden rounded bg-muted/40">
                  <img src={src} alt={`preview-${idx}`} className="max-h-20 w-auto object-contain" />
                </div>
              ))}
            </div>
          )}
          <div className="ml-auto">
            <Button onClick={handleCreatePost}>{editingPostId ? "Aggiorna" : "Pubblica"}</Button>
          </div>
        </div>

        <div className="mt-6 space-y-4">
          {posts.length === 0 ? (
            <div className="text-sm text-muted-foreground">Nessun post al momento.</div>
          ) : (
            posts.map(p => (
              <div key={p.id} className="p-3 border rounded-lg">
                <div className="flex items-start justify-between mb-1">
                  <div className="text-sm text-muted-foreground">
                    {new Date(p.createdAt).toLocaleString()}
                  </div>
                  <div className="flex gap-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-xs hover:bg-muted/60"
                      onClick={() => handleEditPost(p)}
                    >
                      Aggiorna
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 px-2 text-xs text-red-600 hover:text-red-700 hover:bg-red-50"
                      onClick={() => handleDeletePost(p.id)}
                    >
                      Elimina
                    </Button>
                  </div>
                </div>
                <div className="mb-2 text-sm">
                  {renderPostText(p.text)}
                </div>
                {p.images && p.images.length > 0 && (
                  <div className="w-full flex gap-3 overflow-x-auto mt-1 pb-1">
                    {p.images.map((src, idx) => (
                      <div
                        key={idx}
                        className="min-w-[160px] max-w-xs max-h-64 flex items-center justify-center overflow-hidden rounded bg-muted/40"
                      >
                        <img
                          src={src}
                          alt={`post-image-${idx}`}
                          className="max-h-64 w-auto object-contain"
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </Card>
      {/* JD Creator moved to PipelineSection (GestisciCandidature) */}
    </div>
  );
};
