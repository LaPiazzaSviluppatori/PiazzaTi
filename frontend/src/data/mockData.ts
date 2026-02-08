import { Candidate, JobDescription, Opportunity, Feedback, AuditLogEntry } from "@/types";

export const mockCandidates: Candidate[] = [
  {
    id: "1",
    name: "Sofia Rossi",
    location: "Milano, Italia",
    summary: "Full-stack developer con 5 anni di esperienza in React e Node.js. Appassionata di UI/UX e accessibilità web.",
    skills: [
      { name: "React", level: "expert" },
      { name: "TypeScript", level: "advanced" },
      { name: "Node.js", level: "advanced" },
      { name: "PostgreSQL", level: "intermediate" },
      { name: "UI/UX Design", level: "intermediate" },
      { name: "Accessibility", level: "advanced" },
    ],
    experiences: [
      {
        title: "Senior Frontend Developer",
        company: "TechCorp Italia",
        period: "2021 - Presente",
        description: "Lead development di applicazioni React, mentoring junior developers, implementazione design system accessibile.",
      },
      {
        title: "Full Stack Developer",
        company: "Startup Innovativa",
        period: "2019 - 2021",
        description: "Sviluppo full-stack di piattaforma e-commerce, integrazione API, ottimizzazione performance.",
      },
    ],
    projects: [
      {
        title: "Dashboard Analytics Accessibile",
        description: "Dashboard con focus su accessibilità WCAG 2.1 AA per visualizzazione dati real-time.",
        technologies: ["React", "D3.js", "ARIA", "TypeScript"],
        link: "https://github.com/example",
      },
      {
        title: "Design System Open Source",
        description: "Sistema di componenti riutilizzabili con documentazione Storybook.",
        technologies: ["React", "Tailwind", "Storybook"],
      },
    ],
    posts: [
      {
        id: "p1",
        content: "Oggi ho parlato all'evento Women in Tech Milano sull'importanza dell'accessibilità nel web design. Ricordiamoci che un web accessibile è un web per tutti! 💙",
        date: "2025-01-10",
        likes: 47,
      },
      {
        id: "p2",
        content: "Felice di condividere che il nostro team ha raggiunto il 100% di coverage nei test! Qualità del codice è fondamentale.",
        date: "2025-01-05",
        likes: 23,
      },
    ],
    optInTags: [
      { label: "Women in Tech", category: "diversity" },
      { label: "First-generation graduate", category: "background" },
    ],
    connections: 142,
  },
  {
    id: "2",
    name: "Marco Bianchi",
    location: "Roma, Italia",
    summary: "Backend engineer specializzato in microservizi e cloud architecture. Contributor open source.",
    skills: [
      { name: "Python", level: "expert" },
      { name: "Django", level: "advanced" },
      { name: "AWS", level: "advanced" },
      { name: "Docker", level: "expert" },
      { name: "Kubernetes", level: "intermediate" },
    ],
    experiences: [
      {
        title: "Backend Engineer",
        company: "FinTech Solutions",
        period: "2020 - Presente",
        description: "Progettazione e implementazione microservizi scalabili, deployment su AWS.",
      },
    ],
    projects: [
      {
        title: "API Gateway Open Source",
        description: "Gateway per gestione traffico microservizi con rate limiting e autenticazione.",
        technologies: ["Python", "FastAPI", "Redis"],
      },
    ],
    posts: [],
    optInTags: [],
    connections: 87,
  },
  {
    id: "3",
    name: "Lucia Verdi",
    location: "Torino, Italia",
    summary: "UX/UI Designer con background in psicologia. Focus su design inclusivo e user research.",
    skills: [
      { name: "Figma", level: "expert" },
      { name: "User Research", level: "advanced" },
      { name: "Prototyping", level: "expert" },
      { name: "Accessibility Design", level: "advanced" },
      { name: "HTML/CSS", level: "intermediate" },
    ],
    experiences: [
      {
        title: "Senior UX Designer",
        company: "Design Studio",
        period: "2019 - Presente",
        description: "Conduzione user research, progettazione interfacce, design system.",
      },
    ],
    projects: [
      {
        title: "Healthcare App Redesign",
        description: "Riprogettazione completa app sanitaria con focus su accessibilità per utenti anziani.",
        technologies: ["Figma", "User Testing", "WCAG"],
      },
    ],
    posts: [
      {
        id: "p3",
        content: "Il design inclusivo non è un optional, è una responsabilità. Ogni persona merita un'esperienza digitale accessibile.",
        date: "2025-01-08",
        likes: 89,
      },
    ],
    optInTags: [
      { label: "Women in Tech", category: "diversity" },
      { label: "Career changer", category: "background" },
    ],
    connections: 203,
  },
  {
    id: "4",
    name: "Ahmed Hassan",
    location: "Bologna, Italia",
    summary: "Data Scientist con esperienza in ML e AI. PhD in Computer Science.",
    skills: [
      { name: "Machine Learning", level: "expert" },
      { name: "Python", level: "expert" },
      { name: "TensorFlow", level: "advanced" },
      { name: "SQL", level: "advanced" },
      { name: "Statistics", level: "expert" },
    ],
    experiences: [
      {
        title: "Data Scientist",
        company: "AI Lab",
        period: "2021 - Presente",
        description: "Sviluppo modelli ML, analisi dati, ricerca applicata.",
      },
    ],
    projects: [
      {
        title: "Predictive Maintenance System",
        description: "Sistema di manutenzione predittiva per industria 4.0.",
        technologies: ["Python", "TensorFlow", "Kafka"],
      },
    ],
    posts: [],
    optInTags: [
      { label: "International background", category: "diversity" },
    ],
    connections: 95,
  },
  {
    id: "5",
    name: "Giulia Neri",
    location: "Firenze, Italia",
    summary: "DevOps Engineer con focus su automazione e CI/CD. Speaker a conferenze tech.",
    skills: [
      { name: "Terraform", level: "expert" },
      { name: "Jenkins", level: "advanced" },
      { name: "AWS", level: "advanced" },
      { name: "Linux", level: "expert" },
      { name: "Monitoring", level: "advanced" },
    ],
    experiences: [
      {
        title: "DevOps Engineer",
        company: "Cloud Services Inc",
        period: "2020 - Presente",
        description: "Infrastruttura as code, CI/CD pipeline, monitoring e alerting.",
      },
    ],
    projects: [
      {
        title: "Infrastructure Automation",
        description: "Framework per deployment automatizzato multi-cloud.",
        technologies: ["Terraform", "Ansible", "GitLab CI"],
      },
    ],
    posts: [
      {
        id: "p4",
        content: "Automation is not about replacing humans, it's about freeing them to do more creative work! 🚀",
        date: "2025-01-12",
        likes: 56,
      },
    ],
    optInTags: [
      { label: "Women in Tech", category: "diversity" },
    ],
    connections: 178,
  },
];

export const mockJobDescriptions: JobDescription[] = [
  {
    jd_id: "jd1",
    title: "Senior Frontend Developer",
    department: "Engineering",
    description: "Cerchiamo un Senior Frontend Developer per unirsi al nostro team di sviluppo. Lavorerai su progetti innovativi utilizzando le tecnologie più moderne.",
    min_experience_years: 5,
    requirements: ["React", "TypeScript", "UI/UX Design", "Accessibility", "Node.js"],
    nice_to_have: ["Storybook", "Jest", "GraphQL"],
    location: {
      city: "Milano",
      country: "IT",
      remote: true
    },
    constraints: {
      visa: false,
      relocation: false,
      seniority: "senior",
      languages_min: [
        { lang: "italian", level: "C1" },
        { lang: "english", level: "B2" }
      ]
    },
    dei_requirements: {
      target_balance: {
        gender: 0.5,
        underrepresented: 0.2
      }
    },
    metadata: {
      salary_range: {
        min: 45000,
        max: 65000,
        currency: "EUR"
      },
      contract: "full_time"
    }
  },
  {
    jd_id: "jd2",
    title: "Backend Engineer",
    department: "Engineering",
    description: "Backend Engineer per sviluppo microservizi scalabili in ambiente cloud.",
    min_experience_years: 3,
    requirements: ["Python", "Microservizi", "Cloud (AWS/Azure)", "Docker", "Kubernetes"],
    nice_to_have: ["CI/CD", "Terraform"],
    location: {
      city: "Roma",
      country: "IT",
      remote: true
    },
    constraints: {
      visa: true,
      relocation: true,
      seniority: "mid",
      languages_min: [
        { lang: "italian", level: "B2" },
        { lang: "english", level: "B2" }
      ]
    },
    dei_requirements: {
      target_balance: {
        gender: 0.4,
        underrepresented: 0.1
      }
    },
    metadata: {
      salary_range: {
        min: 50000,
        max: 70000,
        currency: "EUR"
      },
      contract: "full_time"
    }
  },
];

export const mockOpportunities: Opportunity[] = [
  {
    id: "o1",
    title: "Women in Tech Scholarship",
    type: "grant",
    organization: "Tech Foundation",
    description: "Borsa di studio per donne nel tech che vogliono specializzarsi in AI/ML.",
    deadline: "2025-03-31",
    link: "https://example.com",
  },
  {
    id: "o2",
    title: "Hackathon Sostenibilità 2025",
    type: "hackathon",
    organization: "Green Tech",
    description: "48 ore di coding per soluzioni tech a impatto ambientale positivo.",
    deadline: "2025-02-15",
  },
  {
    id: "o3",
    title: "Full Stack Developer Bootcamp",
    type: "course",
    organization: "Code Academy",
    description: "Corso intensivo 12 settimane per diventare full stack developer.",
  },
  {
    id: "o4",
    title: "Tech Leadership Fellowship",
    type: "fellowship",
    organization: "Leadership Institute",
    description: "Programma 6 mesi per sviluppare competenze di leadership nel tech.",
    deadline: "2025-04-30",
  },
];

export const mockFeedback: Feedback[] = [
  {
    id: "f1",
    from: "TechCorp Italia",
    message: "Il tuo profilo è molto interessante! Ci piacerebbe conoscerti per una video call conoscitiva.",
    date: "2025-01-12",
    type: "positive",
    jdTitle: "Senior Frontend Developer",
    company: "TechCorp Italia",
  },
  {
    id: "f2",
    from: "Startup Innovativa",
    message: "Grazie per la candidatura. Al momento stiamo valutando profili con più esperienza in DevOps.",
    date: "2025-01-08",
    type: "constructive",
    jdTitle: "DevOps Engineer",
    company: "Startup Innovativa",
  },
  {
    id: "f3",
    from: "Design Studio",
    message: "Abbiamo ricevuto la tua application. Ti contatteremo entro 2 settimane.",
    date: "2025-01-05",
    type: "neutral",
    jdTitle: "UX/UI Designer",
    company: "Design Studio",
  },
];

export const mockAuditLog: AuditLogEntry[] = [
  {
    id: "a1",
    timestamp: "2025-01-12T10:30:00Z",
    action: "jd_created",
    user: "hiring.manager@techcorp.it",
    details: "Creata JD: Senior Frontend Developer",
    deiCompliant: true,
  },
  {
    id: "a2",
    timestamp: "2025-01-12T11:45:00Z",
    action: "candidate_added",
    user: "system",
    details: "Candidato aggiunto a shortlist: Sofia Rossi (score: 85%)",
  },
  {
    id: "a3",
    timestamp: "2025-01-11T09:15:00Z",
    action: "override_triggered",
    user: "hiring.manager@fintech.it",
    details: "Override DEI guardrail per JD: Backend Engineer",
    deiCompliant: false,
    overrideReason: "Urgenza aziendale: posizione critica da coprire entro fine mese. Team commitment a rivedere pipeline di sourcing.",
  },
];
