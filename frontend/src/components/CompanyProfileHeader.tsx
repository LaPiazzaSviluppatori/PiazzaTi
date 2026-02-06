import React, { useState } from "react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Users } from "lucide-react";
import { toast } from "@/hooks/use-toast";

export const CompanyProfileHeader: React.FC = () => {
  const [companyName, setCompanyName] = useState<string>("");
  const [legalName, setLegalName] = useState<string>("");
  const [profileImagePreview, setProfileImagePreview] = useState<string | null>(null);

  const handleProfileImageChange = (file?: File | null) => {
    if (!file) return setProfileImagePreview(null);
    try {
      setProfileImagePreview(URL.createObjectURL(file));
    } catch {
      setProfileImagePreview(null);
    }
  };

  const handleSave = () => {
    toast({ title: "Profilo azienda salvato", description: "Informazioni aggiornate localmente." });
  };

  return (
    <Card className="p-4">
      <div className="flex items-center gap-6">
        <div className="w-28 h-28 rounded-full overflow-hidden border bg-muted/20 flex items-center justify-center">
          {profileImagePreview ? (
            <img src={profileImagePreview} alt="company" className="w-full h-full object-cover" />
          ) : (
            <Users className="h-8 w-8 text-muted-foreground" />
          )}
        </div>

        <div className="flex-1">
          <div className="flex gap-3">
            <Input placeholder="Nome azienda" value={companyName} onChange={e => setCompanyName(e.target.value)} />
            <Input placeholder="Ragione sociale" value={legalName} onChange={e => setLegalName(e.target.value)} />
          </div>
          <div className="flex items-center gap-3 mt-3">
            <label className="inline-flex items-center gap-2 cursor-pointer">
              <input type="file" accept="image/*" className="hidden" onChange={e => handleProfileImageChange(e.target.files?.[0] || null)} />
              <Button variant="outline" size="sm">Carica immagine</Button>
            </label>
            <Button onClick={handleSave} size="sm">Salva</Button>
          </div>
        </div>
      </div>
    </Card>
  );
};

export default CompanyProfileHeader;
