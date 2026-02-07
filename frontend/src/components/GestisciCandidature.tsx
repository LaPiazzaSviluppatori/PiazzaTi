import React, { useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { FileText } from "lucide-react";
import { toast } from "@/hooks/use-toast";

import type { JobDescription } from "@/types";

interface GestisciCandidatureProps {
  onCreateJd?: (jd: Omit<JobDescription, "id" | "createdAt">) => void;
}

const GestisciCandidature: React.FC<GestisciCandidatureProps> = ({ onCreateJd }) => {
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
      min_experience_years: Number(jdForm.min_experience_years) || 0,
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

  return (
    <Card className="p-6">
      <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
        <FileText className="h-5 w-5 text-primary" />
        Crea Job Description
      </h3>

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
    </Card>
  );
};

export default GestisciCandidature;


//aggiunta delle candidature 