import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Candidate, Opportunity, JobDescription } from "@/types";

type UserRole = "candidate" | "company";
import { Users, Lightbulb, Briefcase, Plus, ExternalLink, TrendingUp, Calendar } from "lucide-react";
import { toast } from "@/hooks/use-toast";

// AGGIUNTA: props per candidato attivo
interface DiscoverSectionProps {
  suggestedProfiles: Candidate[];
  opportunities: Opportunity[];
  jobDescriptions: JobDescription[];
  activeCandidate?: Candidate;
  onConnect: (candidateId: string) => void;
  onAddOpportunity: () => void;
  onEvaluateMatch: (jdId: string) => void;
  role: UserRole;
}

export const DiscoverSection = ({
  suggestedProfiles,
  opportunities,
  jobDescriptions,
  activeCandidate,
  onConnect,
  onAddOpportunity,
  onEvaluateMatch,
  role,
}: DiscoverSectionProps) => {
  const getOpportunityIcon = (type: string) => {
    switch (type) {
      case "grant":
        return "💰";
      case "hackathon":
        return "🏆";
      case "course":
        return "📚";
      case "fellowship":
        return "🎓";
      default:
        return "✨";
    }
  };

  // Calcola i match solo se c'è un candidato attivo
    let matchedJd: Array<{ jd: JobDescription; score: number; mustRequirements: string[]; niceRequirements: string[] }> = [];
  if (activeCandidate) {
    matchedJd = jobDescriptions
      .map((jd) => {
        const mustRequirements = Array.isArray(jd.requirements) ? jd.requirements : [];
        const niceRequirements = Array.isArray(jd.nice_to_have) ? jd.nice_to_have : [];
        const candidateSkillNames = activeCandidate.skills.map((s) => s.name.toLowerCase());
        const mustMatch = mustRequirements.filter((req) =>
          candidateSkillNames.some((skill) => skill.includes(req.toLowerCase()))
        ).length;
        const niceMatch = niceRequirements.filter((req) =>
          candidateSkillNames.some((skill) => skill.includes(req.toLowerCase()))
        ).length;
        const mustPercentage = mustRequirements.length > 0 ? (mustMatch / mustRequirements.length) * 100 : 0;
        const nicePercentage = niceRequirements.length > 0 ? (niceMatch / niceRequirements.length) * 100 : 0;
        const score = Math.round(mustPercentage * 0.7 + nicePercentage * 0.3);
        return { jd, score, mustRequirements, niceRequirements };
      })
      .sort((a, b) => b.score - a.score)
      .slice(0, 20);
  }

  return (
    <div className="space-y-6">
      {/* Se azienda: mostra profili candidati */}
      {role === "company" && (
        <Card className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Users className="h-5 w-5 text-primary" />
              Profili Consigliati
            </h3>
            <Badge variant="outline">{suggestedProfiles.length} profili</Badge>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {suggestedProfiles.map((profile) => (
              <Card key={profile.id} className="p-4 hover:shadow-lg transition-shadow">
                <div className="flex items-start gap-3 mb-3">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground flex-shrink-0">
                    {profile.name.split(" ").map((n) => n[0]).join("")}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold truncate">{profile.name}</p>
                    <p className="text-xs text-muted-foreground truncate">{profile.location}</p>
                  </div>
                </div>
                <p className="text-sm text-muted-foreground mb-3 line-clamp-2">{profile.summary}</p>
                <div className="flex flex-wrap gap-1 mb-3">
                  {profile.skills.slice(0, 4).map((skill, i) => (
                    <Badge key={i} variant="secondary" className="text-xs">
                      {skill.name}
                    </Badge>
                  ))}
                  {profile.skills.length > 4 && (
                    <Badge variant="outline" className="text-xs">
                      +{profile.skills.length - 4}
                    </Badge>
                  )}
                </div>
                <Button size="sm" className="w-full" onClick={() => onConnect(profile.id)}>
                  Connetti
                </Button>
              </Card>
            ))}
          </div>
        </Card>
      )}

      {/* Opportunità: visibili a tutti */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Lightbulb className="h-5 w-5 text-primary" />
            Opportunità
          </h3>
          <Button variant="outline" size="sm" onClick={onAddOpportunity}>
            <Plus className="h-4 w-4 mr-1" /> Nuova
          </Button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {opportunities.map((opp) => (
            <Card key={opp.id} className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xl">{getOpportunityIcon(opp.type)}</span>
                <span className="font-semibold">{opp.title}</span>
              </div>
              <p className="text-xs text-muted-foreground mb-2">{opp.organization}</p>
              <p className="text-sm mb-2">{opp.description}</p>
              {opp.deadline && (
                <p className="text-xs text-muted-foreground mb-2">
                  <Calendar className="inline h-3 w-3 mr-1" />
                  Scadenza: {opp.deadline}
                </p>
              )}
              {opp.link && (
                <a href={opp.link} target="_blank" rel="noopener noreferrer" className="text-xs text-primary underline flex items-center gap-1">
                  <ExternalLink className="h-3 w-3" /> Vai al sito
                </a>
              )}
            </Card>
          ))}
        </div>
      </Card>

      {/* JD Top 20 - Lavori a cui posso candidarmi: solo per candidati */}
      {role === "candidate" && activeCandidate && matchedJd.length > 0 && (
        <Card className="p-6 mt-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Briefcase className="h-5 w-5 text-primary" />
              Lavori consigliati per te (Top 20)
            </h3>
            <Badge variant="outline">{matchedJd.length} lavori</Badge>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-4">
            {matchedJd.map(({ jd, score, mustRequirements, niceRequirements }) => (
              <Card key={jd.jd_id} className="p-4 border-2 border-muted shadow-sm">
                <div className="flex items-center gap-2 mb-1">
                  <span className="inline-flex items-center px-2 py-0.5 rounded bg-muted text-xs font-medium text-muted-foreground mr-2">
                    <Briefcase className="h-4 w-4 mr-1 inline" /> job
                  </span>
                  <span className="ml-auto text-xs font-semibold text-primary">Score match: {score}%</span>
                </div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-semibold text-base">{jd.title}</span>
                  {score >= 80 && <span className="ml-2 text-yellow-500 font-bold">★</span>}
                </div>
                <div className="text-xs text-muted-foreground mb-1">
                  {(jd.company || "Azienda")} &middot; {jd.location?.city || ""} {jd.location?.country ? "/ " + jd.location.country : ""} {jd.location?.remote ? ' / Remote' : ''}
                </div>
                <div className="w-full bg-muted-foreground/10 rounded h-2 mb-2">
                  <div className="bg-primary h-2 rounded" style={{ width: `${score}%` }} />
                </div>
                <div className="mb-2 text-xs text-muted-foreground line-clamp-2">{jd.description}</div>
                <div className="mb-2">
                  <span className="font-semibold text-xs">Requisiti:</span>
                  <ul className="list-disc ml-4 mt-1">
                    {mustRequirements.slice(0, 3).map((req, i) => (
                      <li key={i} className="text-xs text-emerald-700">{req}</li>
                    ))}
                    {niceRequirements.slice(0, 2).map((req, i) => (
                      <li key={i} className="text-xs text-blue-700">{req}</li>
                    ))}
                  </ul>
                </div>
                <div className="flex gap-2 mt-2">
                  <Button size="sm" className="flex-1" variant="default">Candidati ora</Button>
                  <Button size="sm" className="flex-1" variant="outline">Aggiungi ai preferiti</Button>
                </div>
              </Card>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};
