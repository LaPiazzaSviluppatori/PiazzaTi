import React, { useRef, useState } from "react";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Users, Pencil } from "lucide-react";
import { toast } from "@/hooks/use-toast";

interface CompanyProfileHeaderProps {
  isCompany?: boolean;
}

export const CompanyProfileHeader: React.FC<CompanyProfileHeaderProps> = ({ isCompany = false }) => {
  const [companyName, setCompanyName] = useState<string>("");
  const [legalName, setLegalName] = useState<string>("");
  const [profileImagePreview, setProfileImagePreview] = useState<string | null>(null);
  const [isEditingNames, setIsEditingNames] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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
        <div className={`w-28 h-28 rounded-full overflow-hidden border flex items-center justify-center ${isCompany ? 'bg-blue-100 border-blue-200' : 'bg-muted/20'}`}>
          {profileImagePreview ? (
            <img src={profileImagePreview} alt="company" className="w-full h-full object-cover" />
          ) : (
            <Users className={`h-8 w-8 ${isCompany ? 'text-blue-600' : 'text-muted-foreground'}`} />
          )}
        </div>

        <div className="flex-1">
          <div className="flex items-center gap-3">
            {isEditingNames ? (
              <>
                <Input
                  placeholder="Nome azienda"
                  value={companyName}
                  onChange={e => setCompanyName(e.target.value)}
                />
                <Input
                  placeholder="Ragione sociale"
                  value={legalName}
                  onChange={e => setLegalName(e.target.value)}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="shrink-0"
                  onClick={() => setIsEditingNames(false)}
                >
                  ✓
                </Button>
              </>
            ) : (
              <>
                <div className="flex flex-col">
                  <span className="text-lg font-semibold">
                    {companyName || "Nome azienda"}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    {legalName || "Ragione sociale"}
                  </span>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="shrink-0"
                  onClick={() => setIsEditingNames(true)}
                >
                  <Pencil className="h-4 w-4" />
                </Button>
              </>
            )}
          </div>
          <div className="flex items-center gap-3 mt-3">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={e => handleProfileImageChange(e.target.files?.[0] || null)}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
            >
              Carica immagine
            </Button>
            <Button onClick={handleSave} size="sm">Salva</Button>
          </div>
        </div>
      </div>
    </Card>

    //i post pubblucati dall'azienda saranno visibili qui, con la possibilità di modificarli o eliminarli.
  );
};

export default CompanyProfileHeader;
