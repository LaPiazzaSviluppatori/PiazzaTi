
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Tuple, Union
from datetime import datetime
from enum import Enum
import re
import json
import uuid
import hashlib
import signal
from pathlib import Path
from langchain_ollama import OllamaLLM

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Union
from datetime import datetime
from enum import Enum


class DocumentType(str, Enum):
    cv = "cv"
    jd = "jd"


class SkillSource(str, Enum):
    extracted = "extracted"
    inferred = "inferred"
    heuristic = "heuristic"


class PersonalInfo(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    website: Optional[str] = None
    street: Optional[str] = None


class Span(BaseModel):
    start: int
    end: int
    text: str
    field: str
    confidence: float = 0.95


class Experience(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    description: Optional[str] = None
    responsibilities: List[str] = Field(default_factory=list)
    spans: List[Span] = Field(default_factory=list)

    @field_validator('is_current', mode='before')
    @classmethod
    def normalize_is_current(cls, v):
        """Convert string/any to boolean"""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            v_lower = v.lower().strip()
            if v_lower in ['true', 'yes', '1', 'current', 'presente', 'ongoing']:
                return True
            if v_lower in ['false', 'no', '0', '', 'none']:
                return False
        # Default to False for any other value
        return False


class Education(BaseModel):
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    institution: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    graduation_year: Optional[int] = None
    gpa: Optional[str] = None
    spans: List[Span] = Field(default_factory=list)


class Skill(BaseModel):
    name: str
    category: Optional[str] = None
    proficiency: Optional[str] = None
    source: SkillSource = SkillSource.extracted
    confidence: float = 1.0


class Language(BaseModel):
    name: str
    proficiency: Optional[str] = None
    level: Optional[str] = None
    certificate: Optional[str] = None
    certificate_year: Optional[int] = None


class Certification(BaseModel):
    name: str
    issuer: Optional[str] = None
    date_obtained: Optional[str] = None


class Project(BaseModel):
    name: str
    description: Optional[str] = None
    role: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)
    url: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class JobPreferences(BaseModel):
    desired_roles: Optional[List[str]] = None
    preferred_locations: Optional[List[str]] = None
    remote_preference: Optional[str] = None
    salary_expectation: Optional[str] = None
    availability: Optional[str] = None

    @field_validator('desired_roles', 'preferred_locations', mode='before')
    @classmethod
    def normalize_list_fields(cls, v):
        """Convert string to list or handle None"""
        if v is None:
            return None
        if isinstance(v, str):
            # Single string -> wrap in list
            return [v.strip()] if v.strip() else None
        if isinstance(v, list):
            # Filter out empty strings
            cleaned = [item.strip() for item in v if isinstance(item, str) and item.strip()]
            return cleaned if cleaned else None
        return None


class ParsedDocument(BaseModel):
    document_id: Optional[str] = None
    document_type: DocumentType
    file_sha256: Optional[str] = None

    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)

    summary: Optional[str] = None
    summary_span: Optional[Span] = None

    experience: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    skills: List[Skill] = Field(default_factory=list)
    languages: List[Language] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)

    preferences: Optional[JobPreferences] = None
    gdpr_consent: bool = False

    file_name: Optional[str] = None
    full_text: Optional[str] = None
    parsing_method: Optional[str] = None
    confidence_score: float = 0.0
    section_confidence: dict = Field(default_factory=dict)

    parsed_at: Optional[datetime] = None

    warnings: List[str] = Field(default_factory=list)
    all_spans: List[Span] = Field(default_factory=list)

    def add_warning(self, warning: str):
        if warning not in self.warnings:
            self.warnings.append(warning)

    def collect_all_spans(self):
        for exp in self.experience:
            self.all_spans.extend(exp.spans)
        for edu in self.education:
            self.all_spans.extend(edu.spans)
        if self.summary_span:
            self.all_spans.append(self.summary_span)

    def detect_missing_sections(self):
        if not self.summary:
            self.add_warning("LOW: Missing professional summary")
        if len(self.experience) == 0:
            self.add_warning("HIGH: No work experience found")
        if len(self.education) == 0:
            self.add_warning("MEDIUM: No education found")
        if len(self.skills) == 0:
            self.add_warning("MEDIUM: No skills found")
        if len(self.languages) == 0:
            self.add_warning("LOW: No languages found")
        if not self.preferences:
            self.add_warning("LOW: No job preferences found")
        if len(self.all_spans) == 0:
            self.add_warning("INFO: No XAI spans extracted")

    def compute_section_confidence(self):
        personal_fields = [
            self.personal_info.full_name,
            self.personal_info.email,
            self.personal_info.phone,
            self.personal_info.city
        ]
        self.section_confidence['personal_info'] = sum(1 for f in personal_fields if f) / len(personal_fields)
        self.section_confidence['summary'] = 1.0 if self.summary else 0.0

        if len(self.experience) > 0:
            exp_scores = []
            for exp in self.experience:
                score = sum([
                    1 if exp.title else 0,
                    1 if exp.company else 0,
                    1 if exp.start_date else 0,
                    0.5 if exp.description else 0
                ]) / 3.5
                exp_scores.append(score)
            self.section_confidence['experience'] = sum(exp_scores) / len(exp_scores)
        else:
            self.section_confidence['experience'] = 0.0

        if len(self.education) > 0:
            edu_scores = []
            for edu in self.education:
                score = sum([
                    1 if edu.degree else 0,
                    1 if edu.institution else 0,
                    0.5 if edu.graduation_year else 0
                ]) / 2.5
                edu_scores.append(score)
            self.section_confidence['education'] = sum(edu_scores) / len(edu_scores)
        else:
            self.section_confidence['education'] = 0.0

        self.section_confidence['skills'] = 1.0 if len(self.skills) >= 3 else len(self.skills) / 3
        self.section_confidence['languages'] = 1.0 if len(self.languages) >= 2 else len(self.languages) / 2
        self.section_confidence['certifications'] = 1.0 if len(self.certifications) >= 1 else 0.0
        self.section_confidence['preferences'] = 1.0 if self.preferences else 0.0

        weights = {
            'personal_info': 0.25,
            'experience': 0.25,
            'education': 0.20,
            'skills': 0.15,
            'languages': 0.10,
            'certifications': 0.05
        }

        self.confidence_score = sum(
            self.section_confidence.get(section, 0) * weight
            for section, weight in weights.items()
        )

    def detect_low_confidence_sections_v2(self):
        for section_key in ['personal_info', 'experience', 'education', 'skills', 'languages', 'certifications']:
            confidence = self.section_confidence.get(section_key, 0.0)
            if confidence == 0.0:
                self.add_warning(f"HIGH: Very low confidence for '{section_key}' ({confidence:.2f})")
            elif confidence < 0.5:
                self.add_warning(f"HIGH: Low confidence for '{section_key}' ({confidence:.2f})")
            elif confidence < 0.7:
                self.add_warning(f"MEDIUM: Moderate confidence for '{section_key}' ({confidence:.2f})")

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("LLM call timeout")


class OllamaCVParser:
    def __init__(self, model: str = "llama3.2:3b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.llm = OllamaLLM(
            model=model,
            base_url=base_url,
            temperature=0.0,
            num_predict=6000,
            num_ctx=4096,
            top_k=5,
            top_p=0.9,
            repeat_penalty=1.2,
        )
        self._init_language_database()
        self._init_certification_database()
        self._init_skill_keywords()

    def parse(self, file_path: str, max_pages: int = 10) -> ParsedDocument:
        """
        Esegue il parsing di un CV PDF e restituisce un ParsedDocument.
        """
        # Calcola hash file
        file_sha256 = self._compute_file_hash(file_path)
        # Estrai testo dal PDF
        text = self._extract_text_from_pdf(file_path, max_pages=max_pages)
        if text.startswith("[OCR ERROR"):
            doc = self._create_empty_document()
            doc.file_name = file_path
            doc.file_sha256 = file_sha256
            doc.full_text = text
            doc.add_warning(text)
            return doc

        doc = ParsedDocument(
            document_id=str(uuid.uuid4()),
            document_type=DocumentType.cv,
            file_sha256=file_sha256,
            file_name=file_path,
            full_text=text,
            parsed_at=datetime.now(),
        )
        # Esempio: estrazione info personali
        info = self._extract_personal_info_regex(text)
        for k, v in info.items():
            setattr(doc.personal_info, k, v)
        # Fallback sezioni strutturate
        self._extract_education_fallback(doc)
        self._extract_languages_fallback(doc)
        # Estrazione skill con LLM (Ollama) + heuristics
        self._extract_skills_llm(doc)
        self._filter_and_enrich_skills(doc)
        # Summary euristico dal testo
        self._extract_summary_fallback(doc)
        self._enrich_country_info(doc)
        self._clean_date_fields(doc)
        doc.collect_all_spans()
        doc.detect_missing_sections()
        doc.compute_section_confidence()
        doc.detect_low_confidence_sections_v2()
        return doc

    def _extract_skills_llm(self, data: ParsedDocument, max_skills: int = 20) -> None:
        """Usa l'LLM Ollama per estrarre una lista di skill dal testo del CV.

        Il modello deve restituire **solo** un array JSON di oggetti
        con almeno il campo "name" e opzionalmente "category".
        In caso di errore o risposta inattesa, la funzione fa solo log
        e lascia che le euristiche facciano il loro lavoro.
        """
        if not getattr(self, "llm", None):
            return
        if not data.full_text:
            return

        prompt = (
            "Sei un assistente che estrae competenze da CV. "
            "Dato il testo seguente, individua le 10-20 skill PIÙ RILEVANTI "
            "(hard skill tecniche e competenze professionali, non soft skills generiche) "
            "e restituisci **SOLO** un array JSON, senza testo aggiuntivo, nel formato:\n"
            "[ {\"name\": \"Python\", \"category\": \"programming\" }, ... ]\n\n"
            "Testo CV:\n" + data.full_text[:8000]
        )

        try:
            # Supporta sia l'interfaccia moderna .invoke che la chiamata diretta
            if hasattr(self.llm, "invoke"):
                raw = self.llm.invoke(prompt)
            else:  # type: ignore[call-arg]
                raw = self.llm(prompt)
        except Exception as e:  # pragma: no cover - dipende dall'ambiente Ollama
            logger.warning("LLM skill extraction failed: %s", e)
            return

        # Normalizza la risposta a stringa
        if isinstance(raw, str):
            text = raw
        else:
            # Alcune versioni di LangChain usano .content
            text = getattr(raw, "content", str(raw))

        # Prova a isolare un array JSON nella risposta
        try:
            start = text.index("[")
            end = text.rindex("]") + 1
            json_str = text[start:end]
            items = json.loads(json_str)
        except Exception as e:
            logger.warning("Failed to parse LLM skill JSON: %s", e)
            return

        if not isinstance(items, list):
            return

        added = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            name = (item.get("name") or "").strip()
            if not name:
                continue
            category = item.get("category")
            if not category:
                category = self._categorize_skill(name)
            try:
                data.skills.append(
                    Skill(
                        name=name,
                        category=category,
                        source=SkillSource.inferred,
                        confidence=0.85,
                    )
                )
                added += 1
                if added >= max_skills:
                    break
            except Exception:
                # Non bloccare il parsing se un singolo item è malformato
                continue

    def _init_language_database(self):
        self.language_database = {
            'italiano': ('Italiano', 'it'), 'italian': ('Italian', 'it'),
            'inglese': ('Inglese', 'en'), 'english': ('English', 'en'),
            'francese': ('Francese', 'fr'), 'french': ('French', 'fr'),
            'spagnolo': ('Spagnolo', 'es'), 'spanish': ('Spanish', 'es'),
            'tedesco': ('Tedesco', 'de'), 'german': ('German', 'de'),
            'portoghese': ('Portoghese', 'pt'), 'portuguese': ('Portuguese', 'pt'),
            'cinese': ('Cinese', 'zh'), 'chinese': ('Chinese', 'zh'),
            'giapponese': ('Giapponese', 'ja'), 'japanese': ('Japanese', 'ja'),
            'russo': ('Russo', 'ru'), 'russian': ('Russian', 'ru'),
            'arabo': ('Arabo', 'ar'), 'arabic': ('Arabic', 'ar'),
        }

    def _init_skill_keywords(self):
        self.skill_keywords = {
            'pals', 'bls', 'blsd', 'bls-d', 'acls', 'nrp', 'ecmo',
            'python', 'java', 'javascript', 'typescript', 'c++', 'c#',
            'ruby', 'go', 'rust', 'swift', 'kotlin', 'php', 'scala',
            'react', 'vue', 'vue.js', 'angular', 'svelte',
            'node.js', 'nodejs', 'express', 'django', 'flask', 'fastapi',
            'sql', 'mysql', 'postgresql', 'postgres', 'mongodb', 'redis',
            'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'k8s', 'jenkins',
            'machine learning', 'ml', 'deep learning', 'nlp',
            'tensorflow', 'pytorch', 'keras', 'scikit-learn',
            'pandas', 'numpy', 'matplotlib',
            'autocad', 'revit', 'photoshop', 'illustrator', 'figma',
            'seo', 'sem', 'google ads', 'google analytics',
            'excel', 'word', 'powerpoint',
            'git', 'api', 'rest', 'graphql', 'agile', 'scrum',
        }

        self.soft_skills_exclude = {
            'gestione stress', 'decision-making', 'empatia',
            'comunicazione', 'leadership', 'lavoro di squadra',
            'team work', 'problem solving', 'attenzione ai dettagli',
        }

        self.skill_categories = {
            'programming': ['python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'ruby', 'go', 'rust'],
            'framework': ['react', 'vue', 'angular', 'django', 'flask', 'spring', 'express'],
            'database': ['sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch'],
            'cloud/devops': ['aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins'],
            'data/ai': ['machine learning', 'deep learning', 'nlp', 'tensorflow', 'pytorch', 'pandas'],
            'design': ['photoshop', 'illustrator', 'figma', 'autocad', 'revit'],
        }


    def _init_certification_database(self):
        self.certification_db = {
            'pals': {'full_name': 'PALS (Pediatric Advanced Life Support)', 'issuer': 'AHA'},
            'bls': {'full_name': 'BLS (Basic Life Support)', 'issuer': 'AHA'},
            'blsd': {'full_name': 'BLS-D (Basic Life Support & Defibrillation)', 'issuer': 'AHA'},
            'acls': {'full_name': 'ACLS (Advanced Cardiovascular Life Support)', 'issuer': 'AHA'},
        }

    def _detect_is_current_jobs(self, data: 'ParsedDocument'):
        """
        Detect current jobs based on end_date:
        - If end_date is None/empty → is_current = True
        - If end_date contains keywords (present, current, etc) → is_current = True, end_date = None
        - If end_date contains a real date → is_current = False
        """
        for exp in data.experience:
            is_current = False

            if not exp.end_date:
                # No end date → current job
                is_current = True
            elif isinstance(exp.end_date, str):
                end_lower = exp.end_date.lower().strip()

                # Check for "present/current" keywords
                if any(kw in end_lower for kw in ['present', 'presente', 'current', 'corrente', 'ongoing', 'in corso', 'now', 'oggi', 'attualmente']):
                    is_current = True
                    exp.end_date = None  # Remove the keyword, set to None
                else:
                    # Has a real date (month/year) → NOT current
                    is_current = False

            exp.is_current = is_current

    def _extract_spans(self, data: ParsedDocument):
        if not data.full_text:
            return

        text = data.full_text
        text_lower = text.lower()
        pi = data.personal_info

        if pi.email and len(pi.email) > 5:
            idx = text_lower.find(pi.email.lower())
            if idx != -1:
                data.all_spans.append(Span(start=idx, end=idx + len(pi.email), text=text[idx:idx + len(pi.email)], field="personal_info.email", confidence=0.99))

        if pi.phone and len(pi.phone) > 5:
            idx = text_lower.find(pi.phone.lower())
            if idx != -1:
                data.all_spans.append(Span(start=idx, end=idx + len(pi.phone), text=text[idx:idx + len(pi.phone)], field="personal_info.phone", confidence=0.95))

        if pi.full_name and len(pi.full_name) > 5:
            idx = text_lower.find(pi.full_name.lower())
            if idx != -1:
                data.all_spans.append(Span(start=idx, end=idx + len(pi.full_name), text=text[idx:idx + len(pi.full_name)], field="personal_info.full_name", confidence=0.95))

        for i, exp in enumerate(data.experience[:3]):
            if exp.title and len(exp.title) > 5:
                idx = text_lower.find(exp.title.lower())
                if idx != -1:
                    data.all_spans.append(Span(start=idx, end=idx + len(exp.title), text=text[idx:idx + len(exp.title)], field=f"experience[{i}].title", confidence=0.90))

        for i, skill in enumerate(data.skills[:10]):
            if skill.name and len(skill.name) > 2:
                idx = text_lower.find(skill.name.lower())
                if idx != -1:
                    data.all_spans.append(Span(start=idx, end=idx + len(skill.name), text=text[idx:idx + len(skill.name)], field=f"skills[{i}].name", confidence=0.80))

    def _filter_and_enrich_skills(self, data: ParsedDocument):
        filtered = []
        for skill in data.skills:
            if len(skill.name) > 50:
                continue
            if any(soft in skill.name.lower() for soft in self.soft_skills_exclude):
                continue
            if not skill.category:
                skill.category = self._categorize_skill(skill.name)
            filtered.append(skill)

        data.skills = filtered

        if len(data.skills) < 8:
            self._add_heuristic_skills(data)

        data.skills = data.skills[:15]

    def _add_heuristic_skills(self, data: ParsedDocument) -> int:
        if not data.full_text:
            return 0

        text_lower = data.full_text.lower()
        existing = {s.name.lower() for s in data.skills}
        added = 0

        for keyword in self.skill_keywords:
            if len(data.skills) >= 15:
                break
            if keyword in text_lower and keyword not in existing:
                skill_name = keyword.upper() if len(keyword) <= 5 else keyword.title()
                data.skills.append(Skill(name=skill_name, category=self._categorize_skill(skill_name), source=SkillSource.heuristic, confidence=0.65))
                existing.add(keyword)
                added += 1

        return added

    def _categorize_skill(self, skill_name: str) -> str:
        skill_lower = skill_name.lower()
        for category, keywords in self.skill_categories.items():
            if any(kw in skill_lower for kw in keywords):
                return category
        return 'other'

    def _extract_personal_info_regex(self, text: str) -> Dict:
        info = {}
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        if email_match:
            info['email'] = email_match.group(0)
        phone_match = re.search(r'[\+]?[0-9]{1,3}?[-.\s]?[(]?[0-9]{1,4}[)]?[-.\s]?[0-9]{1,4}[-.\s]?[0-9]{1,9}', text)
        if phone_match:
            info['phone'] = phone_match.group(0)
        lines = text.split('\n')
        for line in lines[:10]:
            line = line.strip()
            if any(x in line.lower() for x in ['email', 'phone', 'tel', '@', 'curriculum', 'cv']):
                continue
            if 10 < len(line) < 60 and ' ' in line:
                words = line.split()
                if len(words) >= 2 and all(w[0].isupper() for w in words[:2] if w):
                    info['full_name'] = line
                    break
        return info

    def _extract_experience_section_based(self, text: str) -> List[Experience]:
        experiences = []
        exp_section = self._find_section(text, ['esperienza lavorativa', 'work experience', 'experience'])
        if not exp_section:
            return experiences

        lines = exp_section.split('\n')
        current_exp = None

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            date_match = re.search(r'\b(20\d{2}|19\d{2})\b', line)
            if date_match and i + 1 < len(lines):
                if current_exp and current_exp.get('title'):
                    experiences.append(Experience(**current_exp))
                current_exp = {'start_date': date_match.group(0), 'title': 'Position', 'company': 'Company'}

        if current_exp and current_exp.get('title'):
            experiences.append(Experience(**current_exp))
        return experiences[:2]

    def _find_experience_section(self, text: str, max_chars: int = 4000) -> Optional[str]:
        text_lower = text.lower()
        indicators = ['esperienza lavorativa', 'work experience', 'experience', 'employment history']
        for indicator in indicators:
            idx = text_lower.find(indicator)
            if idx != -1:
                return text[idx:idx + max_chars]
        return None

    def _extract_education_fallback(self, data: ParsedDocument):
        edu_section = self._find_section(data.full_text, ['formazione', 'education', 'istruzione'])
        if not edu_section:
            return
        for line in edu_section.split('\n'):
            line = line.strip()
            if '|' in line and len(line) > 20:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 2:
                    year = None
                    for part in parts:
                        year_match = re.search(r'\b(19|20)\d{2}\b', part)
                        if year_match:
                            year = int(year_match.group(0))
                            break
                    data.education.append(Education(degree=parts[0], institution=parts[1], graduation_year=year))

    def _extract_languages_fallback(self, data: ParsedDocument):
        lang_section = self._find_section(data.full_text, ['lingue', 'languages'])
        if not lang_section or '|' not in lang_section:
            return
        for segment in lang_section.split('|'):
            match = re.match(r'([A-Za-zàèéìòù\s]+):\s*([^\n\|]{3,100})', segment.strip())
            if match:
                lang_name = match.group(1).strip()
                prof = match.group(2).strip()
                if lang_name.lower() in self.language_database:
                    canonical, _ = self.language_database[lang_name.lower()]
                    data.languages.append(Language(name=canonical, proficiency=prof))

    def _validate_and_enrich_language_levels(self, data: ParsedDocument):
        valid_cefr = {'C2', 'C1', 'B2', 'B1', 'A2', 'A1'}
        level_map = {
            'madrelingua': 'C2', 'native': 'C2', 'fluente': 'C1', 'fluent': 'C1',
            'avanzato': 'C1', 'advanced': 'C1', 'buono': 'B2', 'good': 'B2',
            'intermedio': 'B2', 'intermediate': 'B2', 'base': 'A2', 'basic': 'A2',
        }
        for lang in data.languages:
            if not lang.proficiency or lang.level:
                continue
            prof_lower = lang.proficiency.lower()
            for cefr in valid_cefr:
                if re.search(rf'\b{cefr.lower()}\b', prof_lower):
                    lang.level = cefr
                    break
            if not lang.level:
                for kw, lv in level_map.items():
                    if kw in prof_lower:
                        lang.level = lv
                        break

    def _deduplicate_certifications(self, data: ParsedDocument):
        groups = {}
        for cert in data.certifications:
            acronym_match = re.match(r'^([A-Z\-]+)', cert.name)
            key = acronym_match.group(1).lower().replace('-', '') if acronym_match else cert.name.lower()
            if key not in groups:
                groups[key] = []
            groups[key].append(cert)
        unique = []
        for certs in groups.values():
            certs.sort(key=lambda c: len(c.name), reverse=True)
            unique.append(certs[0])
        data.certifications = unique

    def _extract_summary_fallback(self, data: ParsedDocument):
        summary_section = self._find_section(data.full_text, ['profilo professionale', 'professional profile', 'summary', 'about me'])
        if not summary_section:
            return
        lines = [l.strip() for l in summary_section.split('\n') if l.strip()]
        content_lines = [l for l in lines if not any(h in l.lower() for h in ['profilo', 'professional', 'summary'])]
        if content_lines:
            summary = ' '.join(content_lines[:3])
            if len(summary) > 300:
                summary = summary[:297] + "..."
            if len(summary) >= 50:
                data.summary = summary

    def _enrich_country_info(self, data):
        if not data.personal_info.country and data.personal_info.city:
            italian_cities = {'milano', 'roma', 'padova', 'napoli', 'torino', 'bologna', 'firenze', 'venezia'}
            if data.personal_info.city.lower() in italian_cities:
                data.personal_info.country = 'Italy'

    def _clean_date_fields(self, data: ParsedDocument):
        for exp in data.experience:
            if exp.start_date:
                exp.start_date = re.sub(r'\s*\([^)]*\)', '', exp.start_date).strip().rstrip(',-;')
            if exp.end_date:
                exp.end_date = re.sub(r'\s*\([^)]*\)', '', exp.end_date).strip().rstrip(',-;')

    def _find_section(self, text, indicators):
        if not text:
            return None
        text_lower = text.lower()
        for ind in indicators:
            idx = text_lower.find(ind)
            if idx != -1:
                return text[idx:min(idx + 2000, len(text))]
        return None

    def _create_empty_document(self):
        return ParsedDocument(document_type=DocumentType.cv, parsed_at=datetime.now())

    def _compute_file_hash(self, path):
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
        return h.hexdigest()

    def _extract_text_from_pdf(self, path, max_pages=10):
        try:
            from pdf2image import convert_from_path
            import pytesseract
            images = convert_from_path(path, dpi=200)[:max_pages]
            text = ""
            for img in images:
                text += pytesseract.image_to_string(img, lang='eng+ita') + "\n\n"
            return text.strip()
        except Exception as e:
            return f"[OCR ERROR: {e}]"

    def _clean_ocr_text(self, text: str) -> str:
        replacements = {
            'â€"': '-', 'â€˜': "'", 'â€™': "'", 'â€œ': '"', 'â€': '"',
            'Ã©': 'é', 'Ã¨': 'è', 'Ã ': 'à', 'Ã²': 'ò', 'Ã¹': 'ù', 'Ã¬': 'ì',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text

    def _detect_europass_format(self, text: str) -> bool:
        text_lower = text.lower()
        indicators = ['formato europeo', 'curriculum vitae europeo', 'europass', 'informazioni personali']
        return sum(1 for ind in indicators if ind in text_lower) >= 1

    def _parse_europass_cv(self, text: str) -> ParsedDocument:
        return ParsedDocument(document_type=DocumentType.cv, parsed_at=datetime.now())



def display_parsing_results(result: ParsedDocument, verbose: bool = True):
    logger.info("PARSING RESULTS")
    logger.info(f"[Document Metadata] Document ID: {result.document_id}, Confidence: {result.confidence_score:.2%}, Method: {result.parsing_method}, Parsed At: {result.parsed_at.strftime('%Y-%m-%d %H:%M:%S') if result.parsed_at else 'N/A'}")
    logger.info(f"[Personal Info] Name: {result.personal_info.full_name}, Email: {result.personal_info.email}, Phone: {result.personal_info.phone}, Location: {result.personal_info.city}, {result.personal_info.country}")
    if result.summary:
        preview = result.summary[:150] + "..." if len(result.summary) > 150 else result.summary
        logger.info(f"[Summary] {preview}")
    logger.info(f"[Experience]: {len(result.experience)} entries")
    for i, exp in enumerate(result.experience, 1):
        current = " [CURRENT]" if exp.is_current else ""
        logger.info(f"  {i}. {exp.title or 'N/A'} @ {exp.company or 'N/A'}{current}")
        if verbose:
            logger.info(f"     Period: {exp.start_date or 'N/A'} - {exp.end_date or 'Present'}")
            if exp.description:
                desc = exp.description[:100] + "..." if len(exp.description) > 100 else exp.description
                logger.info(f"     Description: {desc}")
    logger.info(f"[Education]: {len(result.education)} entries")
    for i, edu in enumerate(result.education, 1):
        logger.info(f"  {i}. {edu.degree or 'N/A'}")
        if verbose:
            logger.info(f"     Institution: {edu.institution or 'N/A'}")
            logger.info(f"     Year: {edu.graduation_year or 'N/A'}")
    logger.info(f"[Skills]: {len(result.skills)} entries")
    if verbose:
        for i, skill in enumerate(result.skills, 1):
            logger.info(f"  {i}. {skill.name} [{skill.source}] (conf: {skill.confidence:.2f})")
    else:
        for i, skill in enumerate(result.skills[:5], 1):
            logger.info(f"  {i}. {skill.name}")
        if len(result.skills) > 5:
            logger.info(f"  ... and {len(result.skills) - 5} more")
    logger.info(f"[Languages]: {len(result.languages)} entries")
    for i, lang in enumerate(result.languages, 1):
        level = f" ({lang.level})" if lang.level else ""
        cert = f" - {lang.certificate}" if lang.certificate else ""
        logger.info(f"  {i}. {lang.name}{level}{cert}")
    logger.info(f"[Certifications]: {len(result.certifications)} entries")
    for i, cert in enumerate(result.certifications, 1):
        year = f" ({cert.date_obtained})" if cert.date_obtained else ""
        name = cert.name[:60] + "..." if len(cert.name) > 60 else cert.name
        logger.info(f"  {i}. {name}{year}")
    logger.info(f"[GDPR Consent]: {'Detected' if result.gdpr_consent else 'Not detected'}")
    logger.info(f"[XAI Spans]: {len(result.all_spans)} extracted")
    if verbose and result.all_spans:
        categories = {}
        for span in result.all_spans:
            cat = span.field.split('[')[0].split('.')[0]
            categories[cat] = categories.get(cat, 0) + 1
        for cat, count in categories.items():
            logger.info(f"  - {cat}: {count}")
    if result.warnings:
        logger.warning(f"[Warnings]: {len(result.warnings)}")
        for i, w in enumerate(result.warnings[:5], 1):
            logger.warning(f"  {i}. {w}")
        if len(result.warnings) > 5:
            logger.warning(f"  ... and {len(result.warnings) - 5} more")


def compute_extraction_stats(result: ParsedDocument) -> dict:
    stats = {
        'total_text_length': len(result.full_text),
        'counts': {
            'experience': len(result.experience),
            'education': len(result.education),
            'skills': len(result.skills),
            'languages': len(result.languages),
            'certifications': len(result.certifications),
            'projects': len(result.projects),
            'spans': len(result.all_spans)
        },
        'confidence_score': result.confidence_score,
        'section_confidence': result.section_confidence,
        'warnings_count': len(result.warnings),
        'has_gdpr': result.gdpr_consent or False,
        'has_preferences': result.preferences is not None,
        'current_jobs': sum(1 for exp in result.experience if exp.is_current)
    }

    total_sections = 8
    populated = 0
    if len(result.experience) > 0: populated += 1
    if len(result.education) > 0: populated += 1
    if len(result.skills) > 0: populated += 1
    if len(result.languages) > 0: populated += 1
    if len(result.certifications) > 0: populated += 1
    if result.summary: populated += 1
    if result.preferences: populated += 1
    if result.personal_info.full_name or result.personal_info.email: populated += 1

    stats['population_rate'] = populated / total_sections
    return stats


def validate_parsing_quality(result: ParsedDocument) -> dict:
    report = {
        'critical_issues': [],
        'warnings': [],
        'info': [],
        'passed_checks': []
    }

    if not result.personal_info.full_name:
        report['critical_issues'].append("Missing full_name")
    else:
        report['passed_checks'].append("Full name present")

    if not result.personal_info.email:
        report['critical_issues'].append("Missing email")
    else:
        report['passed_checks'].append("Email present")

    if len(result.experience) == 0:
        report['critical_issues'].append("No experience entries")
    else:
        report['passed_checks'].append(f"Experience: {len(result.experience)} entries")

    if len(result.education) == 0:
        report['critical_issues'].append("No education entries")
    else:
        report['passed_checks'].append(f"Education: {len(result.education)} entries")

    if len(result.skills) < 3:
        report['warnings'].append(f"Low skill count: {len(result.skills)}")
    else:
        report['passed_checks'].append(f"Skills: {len(result.skills)} entries")

    if len(result.languages) == 0:
        report['warnings'].append("No languages detected")
    else:
        report['passed_checks'].append(f"Languages: {len(result.languages)} entries")

    if result.confidence_score < 0.7:
        report['warnings'].append(f"Low confidence: {result.confidence_score:.2%}")
    else:
        report['passed_checks'].append(f"Confidence: {result.confidence_score:.2%}")

    if len(result.all_spans) < 10:
        report['info'].append(f"Limited spans: {len(result.all_spans)}")
    else:
        report['passed_checks'].append(f"Spans: {len(result.all_spans)} extracted")

    if not result.preferences:
        report['info'].append("No job preferences detected")
    else:
        report['passed_checks'].append("Job preferences extracted")

    if not result.gdpr_consent:
        report['info'].append("No GDPR consent detected")
    else:
        report['passed_checks'].append("GDPR consent detected")

    return report


def print_validation_report(report: dict):
    if report['critical_issues']:
        print("\n[CRITICAL]")
        for issue in report['critical_issues']:
            print(f"  X {issue}")

    if report['warnings']:
        print("\n[WARNINGS]")
        for w in report['warnings']:
            print(f"  ! {w}")

    if report['info']:
        print("\n[INFO]")
        for info in report['info']:
            print(f"  - {info}")

    if report['passed_checks']:
        print("\n[PASSED]")
        for check in report['passed_checks']:
            print(f"  + {check}")

    if not report['critical_issues']:
        print("\n[STATUS]: PASS")
    else:
        print("\n[STATUS]: FAIL")



import requests
import subprocess
import time
import logging
logger = logging.getLogger("ollama_cv_parser")
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO)
    logger.setLevel(logging.INFO)


"""Module-level utilities only; no side effects on import."""

import os
import time
import json
import subprocess
import requests
from pathlib import Path
from datetime import datetime

INPUT_FOLDER = Path("data/cvs")
OUTPUT_FOLDER = Path("parsed_cvs")  # Output outside data folder
MAX_CVS_TO_PROCESS = 25  # Process only first 25 CVs
VERBOSE_OUTPUT = False
RESTART_INTERVAL = 40  # Won't trigger with 25 CVs
ENABLE_AUTO_RESTART = True


def check_ollama_health():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        return r.status_code == 200
    except:
        return False


def check_gpu_available():
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return False
    except:
        return False


def restart_ollama_server():
    """Restart Ollama server with 3-stage warm-up"""
    print("\nRestarting Ollama server...")

    subprocess.run(["pkill", "-9", "ollama"], capture_output=True)
    time.sleep(2)

    gpu_name = check_gpu_available()
    has_gpu = bool(gpu_name)

    ollama_env = os.environ.copy()
    ollama_env['OLLAMA_NUM_GPU'] = '1' if has_gpu else '0'
    ollama_env['OLLAMA_MAX_LOADED_MODELS'] = '1'
    ollama_env['OLLAMA_NUM_PARALLEL'] = '4'
    ollama_env['OLLAMA_KEEP_ALIVE'] = '10m'

    process = subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=ollama_env
    )

    # Wait for server
    for i in range(30):
        if check_ollama_health():
            print(f"  Server ready ({i+1}s)")
            break
        time.sleep(1)
    else:
        print("  Server timeout")
        return False

    # 3-stage warm-up
    print("  Loading model (3-stage warm-up)...")
    warm_up_prompts = [
        "Test",
        "Extract name and email from: John Doe, john@email.com",
        "Analyze this CV profile: Software Engineer with 5 years experience in Python, Django, and Machine Learning"
    ]

    for idx, prompt in enumerate(warm_up_prompts, 1):
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": "llama3.2:3b", "prompt": prompt, "stream": False},
                timeout=20
            )
            if response.status_code == 200:
                print(f"    Stage {idx}/3: OK")
            else:
                print(f"    Stage {idx}/3: Failed (status {response.status_code})")
        except Exception as e:
            print(f"    Stage {idx}/3: Failed ({e})")

    # Stabilization
    print("  Stabilizing...")
    time.sleep(5)

    mode = f"GPU ({gpu_name})" if has_gpu else "CPU"
    print(f"  Server restarted ({mode} mode)")
    return True



