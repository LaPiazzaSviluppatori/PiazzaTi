"""
===============================================================================
CELLA 5: CV PARSER v1.7.4 FINAL - ENHANCED DESCRIPTION GENERATION
===============================================================================

"""


# =====================
# PATCH: COMPATIBILITÀ CODEBASE
# =====================

# Import modelli Pydantic
from ..schemas.parsed_document import (
    Certification,
    DocumentType,
    Education,
    Experience,
    Language,
    ParsedDocument,
    PersonalInfo,
    Skill,
    SkillSource,
    Span,
)

from langchain_ollama import OllamaLLM as Ollama

import os
import time
import re
import json
import uuid
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Set
from datetime import datetime

print("="*80)
print("STEP 5: Creating Parser v1.7.4 FINAL (Complete)")
print("="*80)

# ========================================================================
# IMPORTS
# ========================================================================
import time
import re
import json
import uuid
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Set
from datetime import datetime

# LangChain
from langchain_community.llms import Ollama

# ========================================================================
# PARSER CLASS
# ========================================================================


class OllamaCVParser:
    """Parser v1.7.4 with enhanced description generation."""

    def __init__(self, model: str = "llama3.2:3b", base_url: str = None):
        self.model = model
        self.base_url = (
            base_url or os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
        )
        print(f"Initializing parser v1.7.4 FINAL...")
        print(f"  Using Ollama base_url: {self.base_url}")
        try:
            self.llm = Ollama(
                model=model,
                base_url=self.base_url,
                temperature=0.0,
                num_predict=12000,
                top_k=10,
                top_p=0.9,
                repeat_penalty=1.1,
            )
            print(f"  ✅ LLM client initialized successfully (model: {model})")
        except Exception as e:
            print(f"  ❌ Failed to initialize Ollama client: {e}")
            self.llm = None

        self._init_language_database()
        self._init_certification_database()
        self._init_skill_keywords()
        print(f"SUCCESS: Parser v1.7.4 FINAL ready")


    def _init_language_database(self):
        """Language database."""
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
        """Skill keywords (only technical)."""
        self.skill_keywords = {
            # Healthcare
            'pals', 'bls', 'blsd', 'bls-d', 'acls', 'nrp', 'ecmo',
            'picc', 'cvc', 'ventilazione', 'intubazione',
            'monitoraggio emodinamico', 'rianimazione',
            'chemioterapia', 'ecg', 'cpap',
            # IT
            'python', 'java', 'javascript', 'react', 'vue', 'angular',
            'node.js', 'django', 'fastapi', 'flask',
            'docker', 'kubernetes', 'aws', 'azure', 'gcp',
            'sql', 'postgresql', 'mongodb', 'redis',
            'git', 'ci/cd', 'jenkins', 'github actions',
            'autocad', 'revit', 'archicad', 'sketchup', 'photoshop',
            'illustrator', 'indesign',
            # Marketing
            'seo', 'sem', 'google ads', 'facebook ads', 'meta ads',
            'google analytics', 'ga4', 'hubspot', 'mailchimp',
            'wordpress', 'shopify'
        }

        self.soft_skills_exclude = {
            'gestione stress', 'decision-making', 'empatia',
            'comunicazione', 'leadership', 'lavoro di squadra',
            'team work', 'problem solving', 'attenzione ai dettagli',
            'flessibilità', 'organizzazione'
        }


    def _init_certification_database(self):
        """Certification database."""
        self.certification_db = {
            'pals': {'full_name': 'PALS (Pediatric Advanced Life Support)', 'issuer': 'AHA'},
            'bls': {'full_name': 'BLS (Basic Life Support)', 'issuer': 'AHA'},
            'blsd': {'full_name': 'BLS-D (Basic Life Support & Defibrillation)', 'issuer': 'AHA'},
            'nrp': {'full_name': 'NRP (Neonatal Resuscitation Program)', 'issuer': 'AAP'},
            'acls': {'full_name': 'ACLS (Advanced Cardiovascular Life Support)', 'issuer': 'AHA'},
            'ecmo': {'full_name': 'ECMO Specialist', 'issuer': 'ELSO'},
        }



    def parse(self, file_path: str) -> ParsedDocument:
        """Parse CV with automatic format detection."""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        print(f"\n{'='*80}")
        print(f"PARSING: {file_path.name}")
        print(f"{'='*80}")

        # Steps 0-1: Hash, OCR
        print("\n[0/16] Hash...")
        file_hash = self._compute_file_hash(str(file_path))
        print(f"✓ {file_hash[:16]}")

        print("\n[1/16] OCR...")
        full_text = self._extract_text_from_pdf(str(file_path), max_pages=10)
        print(f"✓ {len(full_text)} chars")

        # Clean OCR text
        print("\n[1.5/16] Cleaning OCR...")
        full_text = self._clean_ocr_text(full_text)
        print(f"✓ Cleaned")

        # Detect format
        print("\n[2/16] Format detection...")
        is_europass = self._detect_europass_format(full_text)

        if is_europass:
            print("      ✓ EUROPASS format detected")
            extracted_data = self._parse_europass_cv(full_text)
        else:
            print("      ✓ Standard format detected")
            print("\n[2.5/16] LLM Extraction...")
            extracted_data = self._extract_with_robust_llm(full_text)

        # Step 3: Metadata
        extracted_data.document_id = str(uuid.uuid4())
        extracted_data.file_sha256 = file_hash
        extracted_data.file_name = file_path.name
        extracted_data.full_text = full_text
        extracted_data.parsing_method = f"{'europass' if is_europass else 'standard'}_v1.7.4_{self.model}"
        extracted_data.parsed_at = datetime.now()

        # POST-PROCESSING
        print("\n" + "="*80)
        print("POST-PROCESSING")
        print("="*80)

        self._run_postprocessing(extracted_data)

        print(f"\n{'='*80}")
        print(f" COMPLETE v1.7.4 ({'EUROPASS' if is_europass else 'STANDARD'})")
        print(f"{'='*80}")

        return extracted_data


    # ========================================================================
    # OCR TEXT CLEANING
    # ========================================================================

    def _clean_ocr_text(self, text: str) -> str:
        """Clean OCR text (fix encoding errors)."""
        replacements = {
            'â€"': '-', 'â€"': '-', 'â€˜': "'", 'â€™': "'",
            'â€œ': '"', 'â€': '"',
            'Ã©': 'é', 'Ã¨': 'è', 'Ã ': 'à', 'Ã²': 'ò', 'Ã¹': 'ù', 'Ã¬': 'ì',
            'Ã€': 'À', 'Ã‰': 'É', 'Ãˆ': 'È',
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        return text


    # ========================================================================
    # EUROPASS FORMAT DETECTION
    # ========================================================================

    def _detect_europass_format(self, text: str) -> bool:
        """Detect if CV is in Europass format."""
        text_lower = text.lower()

        strong_indicators = [
            'formato europeo',
            'curriculum vitae europeo',
            'europass',
            'informazioni personali'
        ]

        strong_count = sum(1 for ind in strong_indicators if ind in text_lower)

        field_labels = ['* date (da', '* nome e indirizzo', '* tipo di azienda', '* tipo di impiego']
        field_count = sum(1 for label in field_labels if label in text_lower)

        return strong_count >= 1 or field_count >= 2


    # ========================================================================
    # EUROPASS CV PARSER
    # ========================================================================

    def _parse_europass_cv(self, text: str) -> ParsedDocument:
        """Parse Europass CV with field-based extraction."""
        print("      Using Europass parser...")

        doc = ParsedDocument(document_type=DocumentType.cv, parsed_at=datetime.now())

        print("        Personal info...")
        doc.personal_info = self._extract_europass_personal_info(text)

        print("        Experience...")
        doc.experience = self._extract_europass_experience(text)
        print(f"          → {len(doc.experience)} entries")

        print("        Education...")
        doc.education = self._extract_europass_education(text)
        print(f"          → {len(doc.education)} entries")

        print("        Languages...")
        doc.languages = self._extract_europass_languages(text)
        print(f"          → {len(doc.languages)} languages")

        print("      ✓ Europass parsing complete")
        return doc


    def _extract_europass_personal_info(self, text: str) -> PersonalInfo:
        """Extract personal info from Europass."""
        info = PersonalInfo()

        section_match = re.search(
            r'INFORMAZIONI PERSONALI(.*?)(?:ESPERIENZA LAVORATIVA|ISTRUZIONE)',
            text,
            re.IGNORECASE | re.DOTALL
        )

        if not section_match:
            return info

        section = section_match.group(1)
        lines = section.split('\n')

        for i, line in enumerate(lines):
            line = line.strip()

            if line.lower() == 'nome' and i + 1 < len(lines):
                name = lines[i + 1].strip()
                if name and len(name) > 3:
                    info.full_name = name

            if line.lower() == 'e-mail' and i + 1 < len(lines):
                email = lines[i + 1].strip()
                if '@' in email:
                    info.email = email

            if line.lower() == 'telefono' and i + 1 < len(lines):
                phone = lines[i + 1].strip()
                if phone and len(phone) > 5:
                    info.phone = phone

            if line.lower() == 'indirizzo' and i + 1 < len(lines):
                address = lines[i + 1].strip()
                if address and len(address) > 10:
                    info.address = address
                    city_match = re.search(r'-\s*([A-Z][a-zA-Z\s]+)\s*\(', address)
                    if city_match:
                        info.city = city_match.group(1).strip()

        return info


    def _extract_europass_experience(self, text: str) -> List[Experience]:
        """Extract experience from Europass."""
        experiences = []

        section_match = re.search(
            r'ESPERIENZA LAVORATIVA(.*?)(?:ISTRUZIONE E FORMAZIONE|CAPACITA)',
            text,
            re.IGNORECASE | re.DOTALL
        )

        if not section_match:
            return experiences

        section = section_match.group(1)
        entries = re.split(r'\*\s*Date\s*\(da\s*[-–]\s*a\)', section)

        for entry in entries[1:]:
            exp = Experience()
            lines = [l.strip() for l in entry.split('\n') if l.strip()]

            if len(lines) == 0:
                continue

            # Dates
            if lines[0]:
                date_match = re.search(r'(\d{4})\s*[-–]\s*(\d{4}|in corso)', lines[0], re.IGNORECASE)
                if date_match:
                    exp.start_date = date_match.group(1)
                    end = date_match.group(2)
                    exp.end_date = None if 'corso' in end.lower() else end

            # Company
            for i, line in enumerate(lines):
                if any(key in line.lower() for key in ['nome e indirizzo', 'datore di lavoro']):
                    if i + 1 < len(lines):
                        company = lines[i + 1]
                        exp.company = company
                        city_match = re.search(r'-\s*([A-Z][a-zA-Z]+)\s*\(', company)
                        if city_match:
                            exp.city = city_match.group(1)
                    break

            # Job title
            for i, line in enumerate(lines):
                if 'tipo di impiego' in line.lower():
                    if i + 1 < len(lines):
                        exp.title = lines[i + 1]
                    break

            # Responsibilities
            for i, line in enumerate(lines):
                if 'mansioni e responsabilita' in line.lower():
                    if i + 1 < len(lines):
                        resp_text = ' '.join(lines[i + 1:i + 4])
                        if resp_text:
                            resp_list = re.split(r'[;,]\s*', resp_text)
                            exp.responsibilities = [r.strip() for r in resp_list if len(r.strip()) > 10][:5]
                    break

            if exp.title or exp.company:
                experiences.append(exp)

        return experiences


    def _extract_europass_education(self, text: str) -> List[Education]:
        """Extract education from Europass."""
        educations = []

        section_match = re.search(
            r'ISTRUZIONE E FORMAZIONE(.*?)(?:CAPACITA|ALTRE LINGUA|$)',
            text,
            re.IGNORECASE | re.DOTALL
        )

        if not section_match:
            return educations

        section = section_match.group(1)
        entries = re.split(r'\*\s*Date\s*\(da\s*[-–]\s*a\)', section)

        for entry in entries[1:]:
            edu = Education()
            lines = [l.strip() for l in entry.split('\n') if l.strip()]

            if len(lines) == 0:
                continue

            # Year
            if lines[0]:
                year_match = re.search(r'(\d{4})', lines[0])
                if year_match:
                    edu.graduation_year = int(year_match.group(1))

            # Institution
            for i, line in enumerate(lines):
                if 'nome e tipo di istituto' in line.lower():
                    if i + 1 < len(lines):
                        edu.institution = lines[i + 1]
                    break

            # Degree
            for i, line in enumerate(lines):
                if 'qualifica conseguita' in line.lower():
                    if i + 1 < len(lines):
                        edu.degree = lines[i + 1]
                    break

            # GPA
            gpa_match = re.search(r'(\d{2,3})/(\d{2,3})', entry)
            if gpa_match:
                edu.gpa = gpa_match.group(0)

            if edu.degree or edu.institution:
                educations.append(edu)

        return educations


    def _extract_europass_languages(self, text: str) -> List[Language]:
        """Extract languages from Europass."""
        languages = []

        section_match = re.search(
            r'ALTRE LINGUA(.*?)(?:CAPACITA|$)',
            text,
            re.IGNORECASE | re.DOTALL
        )

        if not section_match:
            return languages

        section = section_match.group(1)
        lines = [l.strip() for l in section.split('\n') if l.strip()]

        current_lang = None
        current_prof = []

        for line in lines:
            line_lower = line.lower()

            if line_lower in self.language_database:
                if current_lang:
                    languages.append(Language(
                        name=current_lang,
                        proficiency=' '.join(current_prof) if current_prof else None
                    ))

                current_lang = self.language_database[line_lower][0]
                current_prof = []

            elif current_lang:
                if any(word in line_lower for word in ['intermediate', 'advanced', 'toefl', 'ielts', 'capacita']):
                    current_prof.append(line)

        if current_lang:
            languages.append(Language(
                name=current_lang,
                proficiency=' '.join(current_prof) if current_prof else None
            ))

        return languages


    # ========================================================================
    # STANDARD LLM EXTRACTION
    # ========================================================================

    def _extract_with_robust_llm(self, text: str) -> ParsedDocument:
        """Extract with LLM (standard format)."""
        print("      Extracting with LLM...")
        prompt = self._get_robust_prompt(text[:8000])

        try:
            response = self.llm.invoke(prompt)
            data = self._parse_json_response(response)
            print("      ✓ Success")
            return data
        except Exception as e:
            print(f"      ✗ LLM failed: {str(e)[:50]}")
            return self._create_empty_document()


    def _get_robust_prompt(self, text: str) -> str:
        """Robust prompt for standard CVs."""
        return f"""Extract CV data into VALID JSON.

RULES:
1. Output ONLY valid JSON
2. Extract ALL fields
3. Languages: ONLY language names
4. Skills: Technical skills only
5. Certifications: Full names

SCHEMA:
{{
  "personal_info": {{"full_name": "Name", "email": "email", "phone": "phone", "address": "Via X", "city": "City", "country": "Country"}},
  "summary": "Professional summary",
  "experience": [{{"title": "Job", "company": "Company", "city": "City", "start_date": "YYYY", "end_date": "YYYY", "responsibilities": ["r1"]}}],
  "education": [{{"degree": "Degree", "institution": "Institution", "graduation_year": 2020, "gpa": "110/110"}}],
  "skills": [{{"name": "Python"}}],
  "languages": [{{"name": "Italiano", "proficiency": "Madrelingua"}}],
  "certifications": [{{"name": "Cert", "date_obtained": "2023"}}]
}}

CV:
{text}

JSON:"""


    def _parse_json_response(self, response: str) -> ParsedDocument:
        """Parse JSON response."""
        response = response.strip()

        try:
            data_dict = json.loads(response)
            return self._dict_to_document(data_dict)
        except:
            pass

        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                data_dict = json.loads(json_match.group(0))
                return self._dict_to_document(data_dict)
            except:
                pass

        return self._create_empty_document()


    def _dict_to_document(self, data_dict: dict) -> ParsedDocument:
        """Convert dict to document."""
        doc = ParsedDocument(document_type=DocumentType.cv, parsed_at=datetime.now())

        if 'personal_info' in data_dict:
            pi = data_dict['personal_info']
            doc.personal_info = PersonalInfo(**{k: v for k, v in pi.items() if v})

        if 'summary' in data_dict:
            doc.summary = data_dict['summary']

        if 'experience' in data_dict:
            for exp in data_dict['experience']:
                doc.experience.append(Experience(**{k: v for k, v in exp.items() if k != 'spans'}))

        if 'education' in data_dict:
            for edu in data_dict['education']:
                doc.education.append(Education(**{k: v for k, v in edu.items() if k != 'spans'}))

        if 'skills' in data_dict:
            for skill in data_dict['skills']:
                if isinstance(skill, dict) and 'name' in skill:
                    doc.skills.append(Skill(name=skill['name'], source=SkillSource.extracted))

        if 'languages' in data_dict:
            for lang in data_dict['languages']:
                if isinstance(lang, dict) and 'name' in lang:
                    doc.languages.append(Language(**{k: v for k, v in lang.items()}))

        if 'certifications' in data_dict:
            for cert in data_dict['certifications']:
                if isinstance(cert, dict) and 'name' in cert:
                    doc.certifications.append(Certification(**{k: v for k, v in cert.items()}))

        return doc


    # ========================================================================
    # POST-PROCESSING (consolidated)
    # ========================================================================

    def _run_postprocessing(self, data: ParsedDocument):
        """Run all post-processing modules."""

        # Education fallback
        print("\n[4/16] Education fallback...")
        if len(data.education) == 0:
            self._extract_education_fallback(data)
        print(f"      ✓ {len(data.education)} entries")

        # Languages fallback
        print("\n[5/16] Languages fallback...")
        if len(data.languages) == 0:
            self._extract_languages_fallback(data)
        print(f"      ✓ {len(data.languages)} languages")

        # Language levels validation
        print("\n[5.5/16] Language levels...")
        self._validate_and_enrich_language_levels(data)

        # Skills filtering
        print("\n[6/16] Skills (IMPROVED)...")
        self._filter_and_enrich_skills(data)
        print(f"      ✓ {len(data.skills)} skills")

        # Certifications deduplication
        print("\n[7/16] Certifications...")
        self._deduplicate_certifications(data)
        print(f"      ✓ {len(data.certifications)} certs")

        # Summary fallback
        print("\n[8/16] Summary...")
        if not data.summary:
            self._extract_summary_fallback(data)
        if data.summary:
            print(f"      ✓ {len(data.summary)} chars")

        # ENHANCED: Experience descriptions enrichment
        print("\n[9/16] Descriptions (ENHANCED)...")
        self._enrich_experience_descriptions_enhanced(data)

        # Country enrichment
        print("\n[10/16] Country...")
        self._enrich_country_info(data)

        # Current jobs detection
        print("\n[11/16] Current jobs...")
        self._detect_is_current_jobs(data)

        # Date cleaning
        print("\n[11.5/16] Date cleaning...")
        self._clean_date_fields(data)

        # Spans extraction
        print("\n[12/16] Spans (ENHANCED)...")
        self._extract_spans_enhanced(data)
        data.collect_all_spans()
        print(f"      ✓ {len(data.all_spans)} spans")

        # Confidence computation
        print("\n[13/16] Confidence...")
        data.gdpr_consent = 'gdpr' in data.full_text[-2000:].lower() if data.full_text else False
        data.detect_missing_sections()
        data.compute_section_confidence()
        data.detect_low_confidence_sections_v2()
        print(f"✓ {data.confidence_score:.2f}")

        if data.warnings:
            print(f"  {len(data.warnings)} warnings")


    # ========================================================================
    #  ENHANCED: EXPERIENCE DESCRIPTIONS ENRICHMENT
    # ========================================================================

    def _enrich_experience_descriptions_enhanced(self, data: ParsedDocument):
        """
        ENHANCED: Enrich experience descriptions with multi-strategy approach.

        Improvements:
        1. Process ALL jobs (max 10, not just 3)
        2. Improve low-quality descriptions (not just null)
        3. Better context extraction (3-tier fallback)
        4. Quality validation (reject bad outputs)
        5. Retry mechanism (2 attempts)
        6. Multi-strategy generation
        """
        if len(data.experience) == 0:
            print("      No experiences to enrich")
            return

        print(f"      Processing {len(data.experience)} experiences...")

        enriched_count = 0
        improved_count = 0
        skipped_count = 0
        max_process = 10  # Performance limit

        for i, exp in enumerate(data.experience[:max_process]):
            # Check if needs enrichment
            if exp.description:
                if self._is_high_quality_description(exp.description):
                    print(f"        [{i+1}/{min(max_process, len(data.experience))}] {exp.title[:30]}: Skip (high quality)")
                    skipped_count += 1
                    continue
                else:
                    print(f"        [{i+1}/{min(max_process, len(data.experience))}] {exp.title[:30]}: Improving...")
                    action = "improve"
            else:
                print(f"        [{i+1}/{min(max_process, len(data.experience))}] {exp.title[:30]}: Generating...")
                action = "generate"

            # Try to generate description (with retry)
            description = self._generate_description_with_retry(data, exp)

            if description:
                exp.description = description
                if action == "improve":
                    improved_count += 1
                    print(f"          ✓ Improved ({len(description)} chars)")
                else:
                    enriched_count += 1
                    print(f"          ✓ Generated ({len(description)} chars)")
            else:
                print(f"          ✗ Failed")

        total_processed = enriched_count + improved_count
        if total_processed > 0:
            print(f"      ✓ Generated: {enriched_count}, Improved: {improved_count}, Skipped: {skipped_count}")
        else:
            print(f"      ✓ Skipped: {skipped_count} (all high quality)")


    def _is_high_quality_description(self, description: str) -> bool:
        """
        NEW: Check if description is high quality.

        Quality criteria:
        - Length: 100-500 chars
        - Has action verbs
        - Has specific details (numbers, technologies, achievements)
        - Not too generic

        Returns:
            True if high quality, False otherwise
        """
        if not description or not isinstance(description, str):
            return False

        desc_lower = description.lower()

        # Check length
        if len(description) < 100 or len(description) > 500:
            return False

        # Check for action verbs (generic indicators of quality)
        action_verbs = [
            'managed', 'developed', 'implemented', 'led', 'created',
            'designed', 'built', 'coordinated', 'achieved', 'improved',
            'gestito', 'sviluppato', 'implementato', 'creato', 'progettato',
            'coordinato', 'migliorato', 'realizzato'
        ]

        has_action = any(verb in desc_lower for verb in action_verbs)
        if not has_action:
            return False

        # Check for specific details (numbers or technical terms)
        has_numbers = bool(re.search(r'\d+', description))
        has_specifics = len(description.split()) > 20  # More than 20 words

        return has_specifics


    def _generate_description_with_retry(self, data: ParsedDocument, exp: Experience, max_attempts: int = 2) -> Optional[str]:
        """
         NEW: Generate description with retry mechanism.

        Strategy (3-tier fallback):
        1. Try context-based generation (from full_text)
        2. Try responsibilities-based generation (from structured data)
        3. Try minimal generation (from title + company only)

        Returns:
            Generated description or None
        """
        for attempt in range(max_attempts):
            # Strategy 1: Context-based (best quality)
            context = self._extract_job_context_enhanced(data.full_text, exp)
            if context and len(context) >= 100:
                desc = self._generate_from_context(exp, context)
                if desc and self._validate_description_quality(desc):
                    return desc

            # Strategy 2: Responsibilities-based (good quality)
            if exp.responsibilities and len(exp.responsibilities) > 0:
                desc = self._generate_from_responsibilities(exp)
                if desc and self._validate_description_quality(desc):
                    return desc

            # Strategy 3: Minimal (acceptable quality)
            if attempt == max_attempts - 1:  # Last attempt
                desc = self._generate_minimal(exp)
                if desc and len(desc) >= 50:
                    return desc

        return None


    def _extract_job_context_enhanced(self, text: str, exp: Experience) -> Optional[str]:
        """
         ENHANCED: Extract job context with 3-tier fallback.

        Strategy:
        1. Try exact match: title + company
        2. Try title only (within experience section)
        3. Try company only (within experience section)

        Returns:
            Context string or None
        """
        if not text or not exp.title:
            return None

        text_lower = text.lower()

        # Strategy 1: Exact match (title + company)
        if exp.title and exp.company:
            title_idx = text_lower.find(exp.title.lower())
            if title_idx != -1:
                window = text_lower[title_idx:title_idx + 300]
                company_clean = exp.company.split('-')[0].strip() if '-' in exp.company else exp.company
                if company_clean.lower() in window:
                    end_idx = min(title_idx + 1000, len(text))
                    return text[title_idx:end_idx]

        # Strategy 2: Title only
        if exp.title:
            title_idx = text_lower.find(exp.title.lower())
            if title_idx != -1:
                end_idx = min(title_idx + 800, len(text))
                return text[title_idx:end_idx]

        # Strategy 3: Company only (less reliable)
        if exp.company:
            company_clean = exp.company.split('-')[0].strip() if '-' in exp.company else exp.company
            company_idx = text_lower.find(company_clean.lower())
            if company_idx != -1:
                end_idx = min(company_idx + 600, len(text))
                return text[company_idx:end_idx]

        return None


    def _generate_from_context(self, exp: Experience, context: str) -> Optional[str]:
        """
         NEW: Generate description from context.

        Uses LLM with context + structured data.
        """
        prompt = f"""Generate a professional job description (150-300 characters).

JOB TITLE: {exp.title}
COMPANY: {exp.company or 'N/A'}

CONTEXT FROM CV:
{context[:700]}

Write a concise summary covering:
- Main responsibilities (2-3 points)
- Key achievements or impact (if mentioned)

OUTPUT: Single paragraph, 150-300 chars. Start directly, no prefix.

DESCRIPTION:"""

        try:
            response = self.llm.invoke(prompt)
            return self._clean_llm_description(response)
        except:
            return None


    def _generate_from_responsibilities(self, exp: Experience) -> Optional[str]:
        """
         NEW: Generate description from responsibilities.

        Fallback when context not available.
        """
        if not exp.responsibilities or len(exp.responsibilities) == 0:
            return None

        resp_text = "\n".join(f"- {r[:120]}" for r in exp.responsibilities[:4])

        prompt = f"""Generate a professional job description (150-300 characters).

JOB TITLE: {exp.title}
COMPANY: {exp.company or 'N/A'}

KEY RESPONSIBILITIES:
{resp_text}

Write a concise summary of the role. Single paragraph, 150-300 chars. No prefix.

DESCRIPTION:"""

        try:
            response = self.llm.invoke(prompt)
            return self._clean_llm_description(response)
        except:
            return None


    def _generate_minimal(self, exp: Experience) -> Optional[str]:
        """
        NEW: Generate minimal description.

        Last resort when no other data available.
        """
        prompt = f"""Generate a brief professional job description (100-200 characters).

JOB TITLE: {exp.title}
COMPANY: {exp.company or 'Company'}

Write a one-sentence summary of typical responsibilities for this role. 100-200 chars. No prefix.

DESCRIPTION:"""

        try:
            response = self.llm.invoke(prompt)
            return self._clean_llm_description(response)
        except:
            return None


    def _clean_llm_description(self, response: str) -> Optional[str]:
        """
         NEW: Clean LLM-generated description.

        Removes:
        - Unwanted prefixes
        - Markdown formatting
        - Extra whitespace
        """
        if not response:
            return None

        desc = response.strip()

        # Remove prefixes
        unwanted_prefixes = [
            'here is', 'job description:', 'summary:', 'description:',
            'the role', 'as a', 'in this role', 'this position'
        ]

        desc_lower = desc.lower()
        for prefix in unwanted_prefixes:
            if desc_lower.startswith(prefix):
                desc = desc[len(prefix):].strip()
                desc = desc.lstrip(':-').strip()
                desc_lower = desc.lower()

        # Remove markdown
        desc = re.sub(r'\*\*(.+?)\*\*', r'\1', desc)
        desc = re.sub(r'^[\*\-\•]\s+', '', desc)

        # Capitalize first letter
        if desc and desc[0].islower():
            desc = desc[0].upper() + desc[1:]

        # Validate length
        if len(desc) < 50:
            return None

        # Rimosso limite di lunghezza: la descrizione non viene più troncata

        return desc


    def _validate_description_quality(self, description: str) -> bool:
        """
         NEW: Validate generated description quality.

        Quick checks:
        - Min length: 50 chars
        - Max length: 500 chars
        - Not too generic

        Returns:
            True if valid, False otherwise
        """
        if not description:
            return False

        # Check length
        if len(description) < 50 or len(description) > 500:
            return False

        # Check if too generic (reject if only stopwords)
        desc_lower = description.lower()
        generic_only_patterns = [
            'responsible for various tasks',
            'performed duties as assigned',
            'worked on projects',
            'handled responsibilities'
        ]

        if any(pattern in desc_lower for pattern in generic_only_patterns):
            return False

        return True


    # ========================================================================
    # SKILLS FILTERING (from v1.7.3)
    # ========================================================================

    def _filter_and_enrich_skills(self, data: ParsedDocument):
        """Filter and enrich skills with smart heuristic."""
        filtered = []
        for skill in data.skills:
            if len(skill.name) > 50:
                continue
            if any(soft in skill.name.lower() for soft in self.soft_skills_exclude):
                continue
            filtered.append(skill)

        data.skills = filtered
        llm_count = len(data.skills)

        if llm_count < 5:
            print(f"      ⚠️  Low skill count ({llm_count}), using heuristic fallback...")
            added = self._add_heuristic_skills(data)
            print(f"      ✓ Added {added} heuristic skills (total: {len(data.skills)})")
        else:
            print(f"      ✓ LLM skills sufficient ({llm_count}), skipping heuristic")

        data.skills = data.skills[:15]


    def _add_heuristic_skills(self, data: ParsedDocument) -> int:
        """Add skills via heuristic with context checking."""
        if not data.full_text:
            return 0

        text_lower = data.full_text.lower()
        existing = {s.name.lower() for s in data.skills}
        added_count = 0

        for keyword in self.skill_keywords:
            if len(data.skills) >= 15:
                break

            count = text_lower.count(keyword)
            if count < 3:
                continue

            if keyword in existing:
                continue

            if self._has_negation_context(text_lower, keyword):
                continue

            skill_name = keyword.upper() if len(keyword) <= 5 else keyword.title()
            data.skills.append(Skill(
                name=skill_name,
                source=SkillSource.heuristic,
                confidence=0.6
            ))
            existing.add(keyword)
            added_count += 1

        return added_count


    def _has_negation_context(self, text_lower: str, keyword: str) -> bool:
        """Check if keyword appears with negation."""
        negation_patterns = [
            f'no experience with {keyword}',
            f'no knowledge of {keyword}',
            f"don't know {keyword}",
            f"do not know {keyword}",
            f"not familiar with {keyword}",
            f"never used {keyword}",
            f"no {keyword}",
            f"non conosco {keyword}",
            f"nessuna esperienza con {keyword}",
            f"mai usato {keyword}",
            f"non ho esperienza con {keyword}",
        ]

        return any(pattern in text_lower for pattern in negation_patterns)


    # ========================================================================
    # ENHANCED SPANS EXTRACTION (from v1.7.2)
    # ========================================================================

    def _extract_spans_enhanced(self, data: ParsedDocument):
        """Extract text spans for explainability (XAI)."""
        if not data.full_text:
            print("      No text for spans")
            return

        print("      Extracting spans...")

        text = data.full_text
        text_lower = text.lower()
        spans_count = 0

        spans_count += self._extract_personal_info_spans(data, text, text_lower)
        spans_count += self._extract_experience_spans(data, text, text_lower)
        spans_count += self._extract_education_spans(data, text, text_lower)
        spans_count += self._extract_skills_spans(data, text, text_lower)
        spans_count += self._extract_languages_spans(data, text, text_lower)
        spans_count += self._extract_certifications_spans(data, text, text_lower)

        print(f"      ✓ Extracted {spans_count} spans")


    def _extract_personal_info_spans(self, data: ParsedDocument, text: str, text_lower: str) -> int:
        """Extract personal info spans."""
        count = 0
        pi = data.personal_info

        if pi.email and len(pi.email) > 5:
            idx = text_lower.find(pi.email.lower())
            if idx != -1:
                data.all_spans.append(Span(
                    start=idx, end=idx + len(pi.email),
                    text=text[idx:idx + len(pi.email)],
                    field="personal_info.email", confidence=0.99
                ))
                count += 1

        if pi.phone and len(pi.phone) > 8:
            idx = text.find(pi.phone)
            if idx != -1:
                data.all_spans.append(Span(
                    start=idx, end=idx + len(pi.phone),
                    text=pi.phone,
                    field="personal_info.phone", confidence=0.95
                ))
                count += 1

        if pi.full_name and len(pi.full_name) > 5:
            idx = text_lower.find(pi.full_name.lower())
            if idx != -1:
                data.all_spans.append(Span(
                    start=idx, end=idx + len(pi.full_name),
                    text=text[idx:idx + len(pi.full_name)],
                    field="personal_info.full_name", confidence=0.95
                ))
                count += 1

        if pi.city and len(pi.city) > 3:
            idx = text_lower.find(pi.city.lower())
            if idx != -1:
                data.all_spans.append(Span(
                    start=idx, end=idx + len(pi.city),
                    text=text[idx:idx + len(pi.city)],
                    field="personal_info.city", confidence=0.90
                ))
                count += 1

        return count


    def _extract_experience_spans(self, data: ParsedDocument, text: str, text_lower: str) -> int:
        """Extract experience spans."""
        count = 0

        for i, exp in enumerate(data.experience[:5]):
            if exp.title and len(exp.title) > 5:
                idx = text_lower.find(exp.title.lower())
                if idx != -1:
                    data.all_spans.append(Span(
                        start=idx, end=idx + len(exp.title),
                        text=text[idx:idx + len(exp.title)],
                        field=f"experience[{i}].title", confidence=0.90
                    ))
                    count += 1

            if exp.company and len(exp.company) > 5:
                company_clean = exp.company.split('-')[0].strip() if '-' in exp.company else exp.company
                idx = text_lower.find(company_clean.lower())
                if idx != -1:
                    data.all_spans.append(Span(
                        start=idx, end=idx + len(company_clean),
                        text=text[idx:idx + len(company_clean)],
                        field=f"experience[{i}].company", confidence=0.90
                    ))
                    count += 1

        return count


    def _extract_education_spans(self, data: ParsedDocument, text: str, text_lower: str) -> int:
        """Extract education spans."""
        count = 0

        for i, edu in enumerate(data.education[:3]):
            if edu.degree and len(edu.degree) > 10:
                idx = text_lower.find(edu.degree.lower())
                if idx != -1:
                    data.all_spans.append(Span(
                        start=idx, end=idx + len(edu.degree),
                        text=text[idx:idx + len(edu.degree)],
                        field=f"education[{i}].degree", confidence=0.85
                    ))
                    count += 1

            if edu.institution and len(edu.institution) > 10:
                idx = text_lower.find(edu.institution.lower())
                if idx != -1:
                    data.all_spans.append(Span(
                        start=idx, end=idx + len(edu.institution),
                        text=text[idx:idx + len(edu.institution)],
                        field=f"education[{i}].institution", confidence=0.85
                    ))
                    count += 1

        return count


    def _extract_skills_spans(self, data: ParsedDocument, text: str, text_lower: str) -> int:
        """Extract skills spans."""
        count = 0

        for i, skill in enumerate(data.skills[:10]):
            if skill.name and len(skill.name) > 3:
                idx = text_lower.find(skill.name.lower())
                if idx != -1:
                    data.all_spans.append(Span(
                        start=idx, end=idx + len(skill.name),
                        text=text[idx:idx + len(skill.name)],
                        field=f"skills[{i}].name", confidence=0.80
                    ))
                    count += 1

        return count


    def _extract_languages_spans(self, data: ParsedDocument, text: str, text_lower: str) -> int:
        """Extract languages spans."""
        count = 0

        for i, lang in enumerate(data.languages):
            if lang.name and len(lang.name) > 4:
                idx = text_lower.find(lang.name.lower())
                if idx != -1:
                    data.all_spans.append(Span(
                        start=idx, end=idx + len(lang.name),
                        text=text[idx:idx + len(lang.name)],
                        field=f"languages[{i}].name", confidence=0.85
                    ))
                    count += 1

        return count


    def _extract_certifications_spans(self, data: ParsedDocument, text: str, text_lower: str) -> int:
        """Extract certifications spans."""
        count = 0

        for i, cert in enumerate(data.certifications[:5]):
            if cert.name and len(cert.name) > 5:
                idx = text_lower.find(cert.name.lower())
                if idx != -1:
                    data.all_spans.append(Span(
                        start=idx, end=idx + len(cert.name),
                        text=text[idx:idx + len(cert.name)],
                        field=f"certifications[{i}].name", confidence=0.85
                    ))
                    count += 1
                else:
                    acronym_match = re.match(r'^([A-Z\-]+)', cert.name)
                    if acronym_match:
                        acronym = acronym_match.group(1)
                        idx = text_lower.find(acronym.lower())
                        if idx != -1:
                            data.all_spans.append(Span(
                                start=idx, end=idx + len(acronym),
                                text=text[idx:idx + len(acronym)],
                                field=f"certifications[{i}].name", confidence=0.75
                            ))
                            count += 1

        return count


    # ========================================================================
    # DATE CLEANING MODULE (from v1.7.1)
    # ========================================================================

    def _clean_date_fields(self, data: ParsedDocument):
        """Clean date fields (remove parentheses content)."""
        print("      Cleaning dates...")

        cleaned_count = 0

        for exp in data.experience:
            if exp.start_date:
                original = exp.start_date
                exp.start_date = self._clean_single_date(exp.start_date)
                if exp.start_date != original:
                    cleaned_count += 1

            if exp.end_date:
                original = exp.end_date
                exp.end_date = self._clean_single_date(exp.end_date)
                if exp.end_date != original:
                    cleaned_count += 1

        for edu in data.education:
            if hasattr(edu, 'start_date') and edu.start_date:
                original = edu.start_date
                edu.start_date = self._clean_single_date(edu.start_date)
                if edu.start_date != original:
                    cleaned_count += 1

        for cert in data.certifications:
            if cert.date_obtained:
                original = cert.date_obtained
                cert.date_obtained = self._clean_single_date(cert.date_obtained)
                if cert.date_obtained != original:
                    cleaned_count += 1

        if cleaned_count > 0:
            print(f"      ✓ Cleaned {cleaned_count} dates")
        else:
            print(f"      ✓ No dates to clean")


    def _clean_single_date(self, date_str: str) -> str:
        """Clean single date string."""
        if not date_str or not isinstance(date_str, str):
            return date_str

        cleaned = re.sub(r'\s*\([^)]*\)', '', date_str)
        cleaned = cleaned.strip().rstrip(',-;')

        return cleaned if cleaned else date_str


    # ========================================================================
    # POST-PROCESSING MODULES (from v1.7.3)
    # ========================================================================

    def _extract_education_fallback(self, data: ParsedDocument):
        """Extract education fallback."""
        edu_section = self._find_section(data.full_text, ['formazione', 'education', 'istruzione'])
        if not edu_section:
            return

        for line in edu_section.split('\n'):
            line = line.strip()

            if '|' in line and len(line) > 20:
                parts = [p.strip() for p in line.split('|')]

                if len(parts) >= 2:
                    degree = parts[0]
                    institution = parts[1]
                    year = None

                    for part in parts:
                        year_match = re.search(r'\b(19|20)\d{2}\b', part)
                        if year_match:
                            year = int(year_match.group(0))
                            break

                    gpa = None
                    gpa_match = re.search(r'(\d{2,3})/(\d{2,3})', line)
                    if gpa_match:
                        gpa = gpa_match.group(0)

                    data.education.append(Education(
                        degree=degree,
                        institution=institution,
                        graduation_year=year,
                        gpa=gpa
                    ))


    def _extract_languages_fallback(self, data: ParsedDocument):
        """Extract languages fallback."""
        lang_section = self._find_section(data.full_text, ['lingue', 'languages'])
        if not lang_section:
            return

        if '|' in lang_section:
            for segment in lang_section.split('|'):
                match = re.match(r'([A-Za-zàèéìòù\s]+):\s*([^\n\|]{3,100})', segment.strip())
                if match:
                    lang_name = match.group(1).strip()
                    prof = match.group(2).strip()

                    if lang_name.lower() in self.language_database:
                        canonical, _ = self.language_database[lang_name.lower()]
                        data.languages.append(Language(
                            name=canonical,
                            proficiency=prof,
                            level=None
                        ))


    def _validate_and_enrich_language_levels(self, data: ParsedDocument):
        """Validate and enrich language levels."""
        if len(data.languages) == 0:
            return

        print("      Validating levels...")

        valid_cefr = {'C2', 'C1', 'B2', 'B1', 'A2', 'A1'}

        level_map = {
            'madrelingua': 'C2', 'native': 'C2',
            'fluente': 'C1', 'fluent': 'C1', 'avanzato': 'C1', 'advanced': 'C1',
            'buono': 'B2', 'good': 'B2', 'intermedio': 'B2', 'intermediate': 'B2',
            'base': 'A2', 'basic': 'A2',
        }

        enriched = 0

        for lang in data.languages:
            if not lang.proficiency:
                continue

            prof_lower = lang.proficiency.lower()
            original = lang.level

            if not lang.level:
                for cefr in valid_cefr:
                    if re.search(rf'\b{cefr.lower()}\b|\({cefr.lower()}\)', prof_lower):
                        lang.level = cefr
                        enriched += 1
                        break

                if not lang.level:
                    for kw, lv in level_map.items():
                        if kw in prof_lower:
                            lang.level = lv
                            enriched += 1
                            break

            if lang.level:
                lang.level = lang.level.upper().strip()
                if lang.level not in valid_cefr:
                    lang.level = None

        levels_set = sum(1 for l in data.languages if l.level)
        if enriched > 0:
            print(f"      ✓ Enriched {enriched}, {levels_set}/{len(data.languages)} total")


    def _deduplicate_certifications(self, data: ParsedDocument):
        """Deduplicate certifications."""
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
            best = certs[0]
            if not best.issuer:
                for cert in certs:
                    if cert.issuer:
                        best.issuer = cert.issuer
                        break
            unique.append(best)

        data.certifications = unique


    def _extract_summary_fallback(self, data: ParsedDocument):
        """Extract summary fallback."""
        summary_section = self._find_section(data.full_text, [
            'profilo professionale', 'professional profile',
            'professional summary', 'about me', 'riepilogo'
        ])

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
        """Enrich country."""
        if not data.personal_info.country and data.personal_info.city:
            italian_cities = {'milano', 'roma', 'padova', 'napoli', 'torino', 'bologna', 'mortara'}
            if data.personal_info.city.lower() in italian_cities:
                data.personal_info.country = 'Italy'


    def _detect_is_current_jobs(self, data):
        """Detect current jobs."""
        for exp in data.experience:
            if not exp.end_date or any(w in str(exp.end_date).lower() for w in ['present', 'presente', 'corso']):
                exp.is_current = True
                exp.end_date = None


    def _find_section(self, text, indicators):
        """Find section."""
        if not text:
            return None
        text_lower = text.lower()
        for ind in indicators:
            idx = text_lower.find(ind)
            if idx != -1:
                end = len(text)
                next_secs = ['esperienza', 'experience', 'formazione', 'education', 'competenze', 'skills', 'certificazioni', 'lingue', 'progetti']
                for sec in next_secs:
                    next_idx = text_lower.find(sec, idx + len(ind) + 10)
                    if next_idx != -1 and next_idx < end:
                        end = next_idx
                return text[idx:min(end, idx + 3000)]
        return None


    def _create_empty_document(self):
        """Create empty document."""
        return ParsedDocument(document_type=DocumentType.cv, parsed_at=datetime.now())


    def _compute_file_hash(self, path):
        """Compute hash."""
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""): h.update(chunk)
        return h.hexdigest()


    def _extract_text_from_pdf(self, path, max_pages=10):
        """Extract text from PDF."""
        try:
            from pdf2image import convert_from_path
            import pytesseract
            images = convert_from_path(path, dpi=200)[:max_pages]
            text = ""
            for i, img in enumerate(images, 1):
                print(f"  Page {i}/{len(images)}...")
                text += pytesseract.image_to_string(img, lang='eng+ita') + "\n\n"
            return text.strip()
        except Exception as e:
            return f"[OCR ERROR: {e}]"


print("="*80)
"""
===============================================================================
CELLA 6: VALIDATION & DISPLAY FUNCTIONS
===============================================================================
Helper functions per validazione qualità e display risultati.
"""

print("="*80)
print("STEP 6: Creating Validation & Display Functions")
print("="*80)


def display_parsing_results(result: ParsedDocument, verbose: bool = True):
    """
    Display parsing results in a formatted way.

    Args:
        result: ParsedDocument object
        verbose: If True, show detailed information
    """
    print("\n" + "="*80)
    print("PARSING RESULTS")
    print("="*80)

    # Document metadata
    print(f"\n[Document Metadata]")
    print(f"  Document ID: {result.document_id}")
    print(f"  Overall Confidence: {getattr(result, 'confidence_score', 0.0):.2%}")
    print(f"  Parsing Method: {getattr(result, 'parsing_method', '')}")
    if getattr(result, 'parsed_at', None):
        print(f"  Parsed At: {result.parsed_at.strftime('%Y-%m-%d %H:%M:%S')}")

    # Personal Info
    print(f"\n[Personal Info]")
    if result.personal_info.full_name:
        print(f"  Name: {result.personal_info.full_name}")
    if result.personal_info.email:
        print(f"  Email: {result.personal_info.email}")
    if result.personal_info.phone:
        print(f"  Phone: {result.personal_info.phone}")
    if result.personal_info.city:
        print(f"  Location: {result.personal_info.city}, {result.personal_info.country or ''}")
    if result.personal_info.linkedin:
        print(f"  LinkedIn: {result.personal_info.linkedin}")
    if result.personal_info.github:
        print(f"  GitHub: {result.personal_info.github}")

    # Summary
    if result.summary:
        print(f"\n[Professional Summary]")
        summary_preview = result.summary[:150] + "..." if len(result.summary) > 150 else result.summary
        print(f"  {summary_preview}")

    # Experience
    print(f"\n[Work Experience]: {len(getattr(result, 'experience', []))} entries")
    for i, exp in enumerate(getattr(result, 'experience', []), 1):
        current_marker = " [CURRENT]" if getattr(exp, 'is_current', False) else ""
        print(f"  {i}. {getattr(exp, 'title', 'N/A')} @ {getattr(exp, 'company', 'N/A')}{current_marker}")
        if verbose:
            print(f"     Period: {getattr(exp, 'start_date', 'N/A')} - {getattr(exp, 'end_date', 'Present')}")
            print(f"     Location: {getattr(exp, 'city', 'N/A')}")
            if getattr(exp, 'responsibilities', []):
                print(f"     Responsibilities: {len(getattr(exp, 'responsibilities', []))} items")

    # Education
    print(f"\n[Education]: {len(getattr(result, 'education', []))} entries")
    for i, edu in enumerate(getattr(result, 'education', []), 1):
        print(f"  {i}. {getattr(edu, 'degree', 'N/A')}")
        if verbose:
            print(f"     Institution: {getattr(edu, 'institution', 'N/A')}")
            print(f"     Year: {getattr(edu, 'graduation_year', 'N/A')}")
            if getattr(edu, 'gpa', None):
                print(f"     GPA: {getattr(edu, 'gpa')}")

    # Skills
    print(f"\n[Skills]: {len(getattr(result, 'skills', []))} entries")
    if verbose:
        for i, skill in enumerate(getattr(result, 'skills', []), 1):
            source_marker = f"[{getattr(skill, 'source', '')}]"
            print(f"  {i}. {getattr(skill, 'name', '')} {source_marker} (confidence: {getattr(skill, 'confidence', 0.0):.2f})")
    else:
        for i, skill in enumerate(getattr(result, 'skills', [])[:5], 1):
            print(f"  {i}. {getattr(skill, 'name', '')}")
        if len(getattr(result, 'skills', [])) > 5:
            print(f"  ... and {len(getattr(result, 'skills', [])) - 5} more")

    # Languages
    print(f"\n[Languages]: {len(getattr(result, 'languages', []))} entries")
    for i, lang in enumerate(getattr(result, 'languages', []), 1):
        level_str = f" ({getattr(lang, 'level', '')})" if getattr(lang, 'level', None) else ""
        cert_str = f" - {getattr(lang, 'certificate', '')}" if getattr(lang, 'certificate', None) else ""
        year_str = f" ({getattr(lang, 'certificate_year', '')})" if getattr(lang, 'certificate_year', None) else ""
        print(f"  {i}. {getattr(lang, 'name', '')}{level_str}{cert_str}{year_str}")

    # Certifications
    print(f"\n[Certifications]: {len(getattr(result, 'certifications', []))} entries")
    for i, cert in enumerate(getattr(result, 'certifications', []), 1):
        year_str = f" ({getattr(cert, 'date_obtained', '')})" if getattr(cert, 'date_obtained', None) else ""
        cert_name = getattr(cert, 'name', '')
        cert_name = cert_name[:60] + "..." if len(cert_name) > 60 else cert_name
        print(f"  {i}. {cert_name}{year_str}")

    # Preferences
    print(f"\n[Job Preferences]")
    prefs = getattr(result, 'preferences', None)
    if prefs:
        if getattr(prefs, 'work_modality', None):
            print(f"  Modality: {getattr(prefs, 'work_modality')}")
        if getattr(prefs, 'contract_type', None):
            print(f"  Contract: {getattr(prefs, 'contract_type')}")
        if getattr(prefs, 'locations', None):
            print(f"  Locations: {', '.join(getattr(prefs, 'locations'))}")
        if getattr(prefs, 'salary_min', None) and getattr(prefs, 'salary_max', None):
            print(f"  Salary: {getattr(prefs, 'salary_min'):,}-{getattr(prefs, 'salary_max'):,} EUR/year")
    else:
        print("  None detected")

    # GDPR
    gdpr_status = "Detected" if result.gdpr_consent else "Not detected"
    print(f"\n[GDPR Consent]: {gdpr_status}")

    # Spans
    print(f"\n[XAI Spans]: {len(result.all_spans)} extracted")
    if verbose and result.all_spans:
        span_categories = {}
        for span in result.all_spans:
            category = span.field.split('[')[0].split('.')[0]
            span_categories[category] = span_categories.get(category, 0) + 1
        for category, count in span_categories.items():
            print(f"  - {category}: {count} spans")

    # Warnings
    if result.warnings:
        print(f"\n[Warnings]: {len(result.warnings)} issues")
        for i, warning in enumerate(result.warnings[:5], 1):
            severity = warning.split(':')[0] if ':' in warning else 'INFO'
            print(f"  [{severity}] {i}. {warning}")
        if len(result.warnings) > 5:
            print(f"  ... and {len(result.warnings) - 5} more")
    else:
        print(f"\n[Status]: No warnings - parsing complete")


def compute_extraction_stats(result: ParsedDocument) -> dict:
    """
    Compute extraction statistics.

    Returns:
        Dictionary with statistics
    """
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

    # Population rate (% of non-empty sections)
    total_sections = 8  # experience, education, skills, languages, certs, summary, preferences, personal_info
    populated_sections = 0

    if len(result.experience) > 0: populated_sections += 1
    if len(result.education) > 0: populated_sections += 1
    if len(result.skills) > 0: populated_sections += 1
    if len(result.languages) > 0: populated_sections += 1
    if len(result.certifications) > 0: populated_sections += 1
    if result.summary: populated_sections += 1
    if result.preferences: populated_sections += 1
    if result.personal_info.full_name or result.personal_info.email: populated_sections += 1

    stats['population_rate'] = populated_sections / total_sections

    return stats


def validate_parsing_quality(result: ParsedDocument) -> dict:
    """
    Validate parsing quality and return report.

    Returns:
        Dictionary with validation results
    """
    report = {
        'critical_issues': [],
        'warnings': [],
        'info': [],
        'passed_checks': []
    }

    # Critical checks
    if not result.personal_info.full_name:
        report['critical_issues'].append("Missing full_name")
    else:
        report['passed_checks'].append("[PASS] Full name present")

    if not result.personal_info.email:
        report['critical_issues'].append("Missing email")
    else:
        report['passed_checks'].append("[PASS] Email present")

    if len(result.experience) == 0:
        report['critical_issues'].append("No experience entries")
    else:
        report['passed_checks'].append(f"[PASS] Experience: {len(result.experience)} entries")

    if len(result.education) == 0:
        report['critical_issues'].append("No education entries")
    else:
        report['passed_checks'].append(f"[PASS] Education: {len(result.education)} entries")

    # Warnings
    if len(result.skills) < 3:
        report['warnings'].append(f"Low skill count: {len(result.skills)} (expected 3+)")
    else:
        report['passed_checks'].append(f"[PASS] Skills: {len(result.skills)} entries")

    if len(result.languages) == 0:
        report['warnings'].append("No languages detected")
    else:
        report['passed_checks'].append(f"[PASS] Languages: {len(result.languages)} entries")

    if result.confidence_score < 0.7:
        report['warnings'].append(f"Low confidence: {result.confidence_score:.2%}")
    else:
        report['passed_checks'].append(f"[PASS] Confidence: {result.confidence_score:.2%}")

    # Info
    if len(result.all_spans) < 10:
        report['info'].append(f"Limited spans: {len(result.all_spans)} (expected 10+)")
    else:
        report['passed_checks'].append(f"[PASS] Spans: {len(result.all_spans)} extracted")

    if not result.preferences:
        report['info'].append("No job preferences detected")
    else:
        report['passed_checks'].append("[PASS] Job preferences extracted")

    if not result.gdpr_consent:
        report['info'].append("No GDPR consent detected")
    else:
        report['passed_checks'].append("[PASS] GDPR consent detected")

    return report


def print_validation_report(report: dict):
    """Print validation report in a formatted way."""

    if report['critical_issues']:
        print("\n[CRITICAL ISSUES]")
        for issue in report['critical_issues']:
            print(f"  - {issue}")

    if report['warnings']:
        print("\n[WARNINGS]")
        for warning in report['warnings']:
            print(f"  - {warning}")

    if report['info']:
        print("\n[INFO]")
        for info in report['info']:
            print(f"  - {info}")

    if report['passed_checks']:
        print("\n[PASSED CHECKS]")
        for check in report['passed_checks']:
            print(f"  {check}")

    # Overall status
    if not report['critical_issues']:
        print("\n[OVERALL STATUS]: PASS")
    else:
        print("\n[OVERALL STATUS]: FAIL (critical issues found)")


print("SUCCESS: Validation & display functions created")
print("  * display_parsing_results()")
print("  * compute_extraction_stats()")
print("  * validate_parsing_quality()")
print("  * print_validation_report()")

print("\n" + "="*80)
print("VALIDATION FUNCTIONS READY")
print("="*80)

