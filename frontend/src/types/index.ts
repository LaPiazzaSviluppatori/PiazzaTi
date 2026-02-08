export interface Skill {
  name: string;
  level?: "beginner" | "intermediate" | "advanced" | "expert";
}

export interface Experience {
  title: string;
  company: string;
  period: string;
  description: string;
  // Opzionali: informazioni aggiuntive dal parser
  location?: string;
  responsibilities?: string[];
}

export interface Project {
  title: string;
  description: string;
  technologies: string[];
  link?: string;
}

export interface Post {
  id: string;
  content: string;
  date: string;
  likes: number;
}

export interface OptInTag {
  label: string;
  category: "diversity" | "background" | "other";
}

export interface Candidate {
  id: string;
  name: string;
  email?: string;
  phone?: string;
  location: string;
  summary: string;
  skills: Skill[];
  experiences: Experience[];
  projects: Project[];
  posts: Post[];
  optInTags: OptInTag[];
  avatarUrl?: string;
  connections: number;
}

export interface JobRequirement {
  text: string;
  type: "must" | "nice";
}

export interface JobDescription {
  jd_id: string;
  title: string;
  department?: string;
  description: string;
  min_experience_years: number;
  requirements: string[];
  nice_to_have?: string[];
  company?: string; // Nome azienda
  location: {
    city?: string;
    country: string;
    remote?: boolean;
  };
  constraints: {
    visa?: boolean;
    relocation?: boolean;
    seniority: "junior" | "mid" | "senior";
    languages_min?: { lang: string; level: "A1"|"A2"|"B1"|"B2"|"C1"|"C2" }[];
  };
  dei_requirements?: {
    target_balance?: {
      gender?: number;
      underrepresented?: number;
    };
  };
  metadata?: {
    salary_range?: {
      min?: number;
      max?: number;
      currency?: string;
    };
    contract?: string;
  };
}

export interface CandidateMatch {
  candidateId: string;
  score: number;
  mustHaveMatch: number;
  niceToHaveMatch: number;
  explanation: string;
}

export interface ShortlistCandidate extends Candidate {
  match: CandidateMatch;
}

export interface Feedback {
  id: string;
  from: string;
  message: string;
  date: string;
  type: "positive" | "constructive" | "neutral";
  jdTitle?: string;
  company?: string;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  action: "shortlist_closed" | "override_triggered" | "jd_created" | "candidate_added";
  user: string;
  details: string;
  deiCompliant?: boolean;
  overrideReason?: string;
}

export interface Opportunity {
  id: string;
  title: string;
  type: "grant" | "hackathon" | "course" | "fellowship" | "other";
  organization: string;
  description: string;
  deadline?: string;
  link?: string;
}

export interface InclusivityIssue {
  term: string;
  severity: "high" | "medium" | "low";
  suggestion: string;
  position: number;
}
