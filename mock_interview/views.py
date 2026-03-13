import json
import logging
import os
import random
import re
import tempfile
import time
import threading
from decimal import Decimal
from difflib import SequenceMatcher

import docx2txt
import openai
import pdfplumber
from django.conf import settings
from django.core.cache import cache
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from google import genai
from google.genai import types
try:
    from django_q.tasks import async_task
except Exception:  # pragma: no cover - qcluster may be unavailable in tests
    async_task = None

from .forms import InterviewSetupForm
from .models import InterviewTurn, MockInterviewSession

logger = logging.getLogger(__name__)

MAX_INTERVIEW_QUESTIONS = getattr(settings, "MOCK_INTERVIEW_MAX_QUESTIONS", 8)
MIN_INTERVIEW_QUESTIONS = getattr(settings, "MOCK_INTERVIEW_MIN_QUESTIONS", 5)
DEFAULT_GEMINI_MODELS = ["models/gemini-2.0-flash", "models/gemini-1.5-flash"]
DEFAULT_OPENAI_MODELS = ["gpt-4o-mini", "gpt-4.1-mini"]
FALLBACK_CLOSING = "Thank you for completing your interview. Check your report for detailed feedback."
INTERVIEW_TRACKS = {"technical", "hr"}

TECHNICAL_TOPICS = [
    "programming",
    "algorithms",
    "data structures",
    "system design",
    "database",
    "api development",
    "cloud",
    "testing",
    "debugging",
    "machine learning",
]

HR_TOPICS = [
    "communication",
    "teamwork",
    "conflict resolution",
    "ownership",
    "time management",
    "leadership",
    "adaptability",
    "motivation",
]

CANONICAL_SKILL_KEYWORDS = {
    "python": ["python", "py"],
    "java": ["java"],
    "c++": ["c++", "cpp"],
    "c": [" c ", "language c"],
    "javascript": ["javascript", "js", "nodejs", "node.js"],
    "typescript": ["typescript", "ts"],
    "django": ["django"],
    "flask": ["flask"],
    "fastapi": ["fastapi"],
    "react": ["react", "reactjs", "react.js"],
    "angular": ["angular"],
    "vue": ["vue", "vuejs"],
    "sql": ["sql", "mysql", "postgresql", "postgres", "sqlite"],
    "mongodb": ["mongodb", "mongo"],
    "redis": ["redis"],
    "aws": ["aws", "amazon web services"],
    "azure": ["azure"],
    "gcp": ["gcp", "google cloud"],
    "docker": ["docker"],
    "kubernetes": ["kubernetes", "k8s"],
    "git": ["git", "github", "gitlab"],
    "rest api": ["rest api", "restful", "api development", "http api"],
    "machine learning": ["machine learning", "ml"],
    "deep learning": ["deep learning", "cnn", "rnn"],
    "nlp": ["nlp", "natural language processing"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "power bi": ["power bi"],
    "tableau": ["tableau"],
    "excel": ["excel"],
}

ROLE_HINTS = [
    ("Data Scientist", ["machine learning", "deep learning", "nlp", "pandas", "numpy"]),
    ("Data Analyst", ["power bi", "tableau", "excel", "sql", "analytics"]),
    ("Backend Developer", ["django", "flask", "fastapi", "rest api", "sql", "docker"]),
    ("Frontend Developer", ["react", "angular", "vue", "javascript", "typescript"]),
    ("Full Stack Developer", ["react", "javascript", "django", "node", "sql"]),
    ("DevOps Engineer", ["docker", "kubernetes", "aws", "azure", "ci/cd"]),
    ("Software Engineer", ["python", "java", "c++", "sql", "api"]),
]

FUNDAMENTAL_TECH_QUESTION_BANK = {
    "python": [
        "Good. In Python, what is the difference between list and tuple, and when would you use each?",
        "Nice. What is the difference between deep copy and shallow copy in Python?",
        "Can you explain Python dictionary time complexity for lookup, insert, and delete?",
    ],
    "sql": [
        "Great. What is the difference between WHERE and HAVING in SQL?",
        "Can you explain INNER JOIN vs LEFT JOIN with a practical example?",
        "How do indexes improve SQL performance, and what is the tradeoff?",
    ],
    "machine learning": [
        "Good. What is overfitting, and which techniques do you use to reduce it?",
        "Can you explain precision, recall, and F1 score in simple terms?",
        "What is the difference between supervised and unsupervised learning?",
    ],
    "data structures": [
        "Nice. What is the difference between array and linked list in terms of operations and complexity?",
        "Can you explain stack vs queue with real use cases?",
        "What is the time complexity of binary search and when can it be used?",
    ],
    "algorithms": [
        "Good. What is the difference between time complexity and space complexity?",
        "Can you explain recursion vs iteration and when recursion may be risky?",
        "What is dynamic programming, and how is it different from greedy approach?",
    ],
    "django": [
        "Nice. What is the difference between Django middleware and view logic?",
        "Can you explain Django ORM select_related vs prefetch_related?",
        "How do you handle authentication and authorization in Django applications?",
    ],
    "react": [
        "Good. What is the difference between state and props in React?",
        "Can you explain useEffect dependency behavior and common mistakes?",
        "What is virtual DOM and why is it useful?",
    ],
    "api": [
        "Great. What is the difference between REST and RPC style APIs?",
        "How do you design idempotent API endpoints?",
        "What status codes do you commonly use for create, validation error, and unauthorized?",
    ],
    "cloud": [
        "Can you explain horizontal scaling vs vertical scaling?",
        "What is the difference between containers and virtual machines?",
        "How do you approach high availability in a cloud service?",
    ],
}

GENERIC_TECH_QUESTIONS = [
    "Could you explain OOP principles with one practical example from your work?",
    "How do you debug a production issue when logs are limited?",
    "What is your approach to writing clean and maintainable code?",
    "How do you choose between normalization and denormalization in database design?",
]

BAND_ORDER = ["foundation", "standard", "advanced"]
BAND_TO_DIFFICULTY = {
    "foundation": "easy",
    "standard": "medium",
    "advanced": "hard",
}
INTERVIEW_PACKS = {
    "default": {
        "id": "default",
        "name": "General Adaptive",
        "difficulty_mix": {"easy": 0.3, "medium": 0.5, "hard": 0.2},
        "question_style": "resume-grounded",
        "stage_minutes": {"introduction": 2, "core": 5, "depth": 5, "final": 3},
    },
    "mnc_fresher": {
        "id": "mnc_fresher",
        "name": "MNC Fresher",
        "difficulty_mix": {"easy": 0.5, "medium": 0.4, "hard": 0.1},
        "question_style": "structured-fundamentals",
        "stage_minutes": {"introduction": 3, "core": 6, "depth": 4, "final": 2},
    },
    "startup_backend": {
        "id": "startup_backend",
        "name": "Startup Backend",
        "difficulty_mix": {"easy": 0.2, "medium": 0.5, "hard": 0.3},
        "question_style": "tradeoff-and-scaling",
        "stage_minutes": {"introduction": 2, "core": 4, "depth": 7, "final": 2},
    },
    "data_analyst": {
        "id": "data_analyst",
        "name": "Data Analyst",
        "difficulty_mix": {"easy": 0.3, "medium": 0.5, "hard": 0.2},
        "question_style": "metrics-and-insights",
        "stage_minutes": {"introduction": 2, "core": 5, "depth": 6, "final": 2},
    },
}


def is_student(user):
    return user.is_authenticated and hasattr(user, "profile") and user.profile.role == "STUDENT"


def _strip(text):
    return (text or "").strip()


def _parse_json(text):
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*\}|\[[\s\S]*\])\s*```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


def _gemini_text(response):
    if getattr(response, "text", None):
        return response.text
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        parts = [getattr(p, "text", "") for p in getattr(content, "parts", []) or []]
        merged = "\n".join([p for p in parts if p])
        if merged:
            return merged
    return ""


class AIService:
    def __init__(self):
        self.gemini_key = getattr(settings, "GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
        self.openai_key = getattr(settings, "OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
        self.gemini_models = [getattr(settings, "GEMINI_MODEL", "").strip()] if getattr(settings, "GEMINI_MODEL", "").strip() else list(DEFAULT_GEMINI_MODELS)
        self.openai_models = [getattr(settings, "OPENAI_MODEL", "").strip()] if getattr(settings, "OPENAI_MODEL", "").strip() else list(DEFAULT_OPENAI_MODELS)
        self._gemini = None
        self._gemini_models_resolved = False

    @property
    def enabled(self):
        return bool(self.gemini_key or self.openai_key)

    def _call_gemini(self, prompt, temperature, max_tokens, prefer_json=False):
        if not self.gemini_key:
            raise RuntimeError("Gemini key missing")
        if self._gemini is None:
            self._gemini = genai.Client(api_key=self.gemini_key)
        self._resolve_gemini_models()
        last = None
        for model in self.gemini_models:
            try:
                cfg = {"temperature": temperature, "max_output_tokens": max_tokens}
                if prefer_json:
                    cfg["response_mime_type"] = "application/json"
                r = self._gemini.models.generate_content(model=model, contents=prompt, config=types.GenerateContentConfig(**cfg))
                t = _strip(_gemini_text(r))
                if t:
                    return t, "gemini", model
            except Exception as exc:
                last = exc
        raise RuntimeError(f"Gemini failed: {last}")

    def _resolve_gemini_models(self):
        if self._gemini_models_resolved:
            return
        self._gemini_models_resolved = True

        candidates = []
        for model in self.gemini_models:
            if not model:
                continue
            base = model.replace("models/", "")
            candidates.append(model)
            candidates.append(base)
            candidates.append(f"models/{base}")

        try:
            available = []
            for model in self._gemini.models.list():
                name = getattr(model, "name", "")
                if not name:
                    continue
                actions = getattr(model, "supported_actions", []) or []
                methods = getattr(model, "supported_generation_methods", []) or []
                if "generateContent" in actions or "generateContent" in methods:
                    available.append(name)

            # Prefer stable flash variants from available models first.
            preferred = sorted(
                available,
                key=lambda n: (
                    0 if ("flash" in n and "preview" not in n and "exp" not in n) else
                    1 if "flash" in n else
                    2
                ),
            )
            candidates = preferred + candidates
        except Exception as exc:
            logger.warning("Gemini model discovery failed, using configured candidates: %s", exc)

        # De-duplicate while preserving order.
        seen = set()
        merged = []
        for model in candidates:
            key = model.strip().lower()
            if key and key not in seen:
                seen.add(key)
                merged.append(model.strip())
        if merged:
            self.gemini_models = merged

    def _call_openai(self, prompt, temperature, max_tokens):
        if not self.openai_key:
            raise RuntimeError("OpenAI key missing")
        from openai import OpenAI
        client = OpenAI(api_key=self.openai_key)
        last = None
        for model in self.openai_models:
            try:
                r = client.responses.create(
                    model=model,
                    input=prompt,
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
                t = _strip(getattr(r, "output_text", ""))
                if t:
                    return t, "openai", model
            except Exception as exc:
                last = exc

        for model in self.openai_models:
            try:
                r = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are an interview assistant."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                t = _strip(r.choices[0].message.content if r.choices else "")
                if t:
                    return t, "openai", model
            except Exception as exc:
                last = exc
        raise RuntimeError(f"OpenAI failed: {last}")

    # --- Reliability helpers ---------------------------------------------------
    _RETRY_DELAYS = (0.5, 1.0)        # exponential backoff for 2 retries
    _CALL_TIMEOUT  = 30               # seconds per provider call

    @staticmethod
    def _estimate_tokens(text):
        """Rough token count: ~4 chars per token."""
        return max(1, len(text or "") // 4)

    @staticmethod
    def _compute_cost(provider, input_tokens, output_tokens):
        pricing = getattr(settings, "AI_COST_PER_1K_TOKENS", {}).get(provider, {})
        inp = Decimal(str(pricing.get("input", 0))) * Decimal(input_tokens) / 1000
        out = Decimal(str(pricing.get("output", 0))) * Decimal(output_tokens) / 1000
        return round(inp + out, 6)

    @staticmethod
    def _check_quota(organization):
        """Return True if org is within its monthly AI token quota."""
        if organization is None:
            return True
        from organizations.models import Organization
        if not isinstance(organization, Organization):
            return True
        sub = organization.active_subscription
        if not sub:
            return True  # no plan â†’ allow (free-tier default)
        limit = sub.plan.ai_tokens_monthly
        if limit == -1:
            return True  # unlimited
        from django.utils import timezone as tz
        month_start = tz.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        from mock_interview.ai_models import AIUsageLog
        from django.db.models import Sum
        used = AIUsageLog.objects.filter(
            organization=organization,
            created_at__gte=month_start,
            status__in=["success", "fallback"],
        ).aggregate(total=Sum("input_tokens") + Sum("output_tokens"))["total"] or 0
        return used < limit

    def _call_with_timeout(self, fn, *args, **kwargs):
        """Run *fn* in a thread; raise RuntimeError on timeout."""
        result = [None]
        error  = [None]
        def _target():
            try:
                result[0] = fn(*args, **kwargs)
            except Exception as exc:
                error[0] = exc
        t = threading.Thread(target=_target, daemon=True)
        t.start()
        t.join(timeout=self._CALL_TIMEOUT)
        if t.is_alive():
            raise RuntimeError(f"AI call timed out after {self._CALL_TIMEOUT}s")
        if error[0]:
            raise error[0]
        return result[0]

    def _log_usage(self, *, provider, model_name, operation, input_tokens,
                   output_tokens, cost, latency_ms, status, error_message="",
                   user=None, organization=None):
        try:
            from mock_interview.ai_models import AIUsageLog
            AIUsageLog.objects.create(
                user=user, organization=organization,
                provider=provider, model_name=model_name or "",
                operation=operation,
                input_tokens=input_tokens, output_tokens=output_tokens,
                estimated_cost_usd=cost,
                latency_ms=latency_ms, status=status,
                error_message=error_message[:500] if error_message else "",
            )
        except Exception as log_exc:
            logger.warning("AIUsageLog write failed: %s", log_exc)

    def text(self, prompt, temperature=0.7, max_tokens=300, prefer_json=False,
             user=None, organization=None, operation="unknown"):
        # --- Quota gate ---
        if not self._check_quota(organization):
            self._log_usage(
                provider="none", model_name="", operation=operation,
                input_tokens=0, output_tokens=0, cost=Decimal(0),
                latency_ms=0, status="quota_exceeded",
                error_message="Monthly AI token quota exceeded",
                user=user, organization=organization,
            )
            raise RuntimeError("Monthly AI token quota exceeded")

        errors = []
        start = time.time()
        # --- Try Gemini with retry ---
        if self.gemini_key:
            for attempt in range(1 + len(self._RETRY_DELAYS)):
                try:
                    result = self._call_with_timeout(
                        self._call_gemini, prompt, temperature, max_tokens,
                        prefer_json=prefer_json,
                    )
                    latency = int((time.time() - start) * 1000)
                    text_result, provider, model = result
                    inp_tok = self._estimate_tokens(prompt)
                    out_tok = self._estimate_tokens(text_result)
                    cost = self._compute_cost(provider, inp_tok, out_tok)
                    self._log_usage(
                        provider=provider, model_name=model, operation=operation,
                        input_tokens=inp_tok, output_tokens=out_tok, cost=cost,
                        latency_ms=latency, status="success",
                        user=user, organization=organization,
                    )
                    return result
                except Exception as exc:
                    errors.append(str(exc))
                    if attempt < len(self._RETRY_DELAYS):
                        time.sleep(self._RETRY_DELAYS[attempt])

        # --- Try OpenAI with retry (fallback) ---
        if self.openai_key:
            fallback_start = time.time()
            for attempt in range(1 + len(self._RETRY_DELAYS)):
                try:
                    result = self._call_with_timeout(
                        self._call_openai, prompt, temperature, max_tokens,
                    )
                    latency = int((time.time() - start) * 1000)
                    text_result, provider, model = result
                    inp_tok = self._estimate_tokens(prompt)
                    out_tok = self._estimate_tokens(text_result)
                    cost = self._compute_cost(provider, inp_tok, out_tok)
                    self._log_usage(
                        provider=provider, model_name=model, operation=operation,
                        input_tokens=inp_tok, output_tokens=out_tok, cost=cost,
                        latency_ms=latency,
                        status="fallback" if self.gemini_key else "success",
                        user=user, organization=organization,
                    )
                    return result
                except Exception as exc:
                    errors.append(str(exc))
                    if attempt < len(self._RETRY_DELAYS):
                        time.sleep(self._RETRY_DELAYS[attempt])

        # --- Both failed ---
        latency = int((time.time() - start) * 1000)
        err_msg = "; ".join(errors) if errors else "No AI provider configured"
        self._log_usage(
            provider="none", model_name="", operation=operation,
            input_tokens=self._estimate_tokens(prompt), output_tokens=0,
            cost=Decimal(0), latency_ms=latency, status="error",
            error_message=err_msg, user=user, organization=organization,
        )
        raise RuntimeError(err_msg)


AI = AIService()


def _resume_text(upload, filename):
    name = (filename or getattr(upload, "name", "")).lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    upload.seek(0)
    if ext == "pdf":
        with pdfplumber.open(upload) as pdf:
            return "\n".join([(p.extract_text() or "") for p in pdf.pages]).strip()
    if ext == "docx":
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            tmp.write(upload.read())
            path = tmp.name
        try:
            return _strip(docx2txt.process(path))
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
    if ext == "txt":
        return upload.read().decode("utf-8", errors="ignore").strip()
    raise ValueError("Unsupported resume type")


def _safe_list(value):
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _skill_matches_in_text(resume_text):
    lowered = " " + (resume_text or "").lower() + " "
    matches = []
    for canonical, aliases in CANONICAL_SKILL_KEYWORDS.items():
        for alias in aliases:
            alias_norm = alias.lower().strip()
            if alias_norm == "c":
                if re.search(r"\bc\b", lowered):
                    matches.append(canonical)
                    break
            elif alias_norm in lowered:
                matches.append(canonical)
                break
    return matches


def _extract_explicit_skills(resume_text):
    lines = [ln.strip(" -•\t").strip() for ln in (resume_text or "").splitlines() if ln.strip()]
    skill_lines = []
    section_mode = False
    for raw in lines:
        low = raw.lower()
        if re.match(r"^(skills|technical skills|key skills|competencies|tools)\b[:\-]?$", low):
            section_mode = True
            continue
        if section_mode and re.match(r"^[A-Z][A-Za-z ]{0,30}$", raw) and ":" not in raw and len(raw.split()) <= 4:
            section_mode = False
        if section_mode:
            skill_lines.append(raw)
        if re.match(r"^(skills|technical skills|key skills|competencies|tools)\b[:\-]", low):
            skill_lines.append(re.sub(r"^(skills|technical skills|key skills|competencies|tools)\b[:\-]\s*", "", raw, flags=re.IGNORECASE))

    from_section = _skill_matches_in_text("\n".join(skill_lines)) if skill_lines else []
    from_full = _skill_matches_in_text(resume_text)
    merged = []
    for item in from_section + from_full:
        if item not in merged:
            merged.append(item)
    return merged[:16]


def _extract_candidate_name(resume_text):
    for line in (resume_text or "").splitlines()[:8]:
        cleaned = re.sub(r"[^A-Za-z\s]", " ", line).strip()
        if 2 <= len(cleaned.split()) <= 4 and len(cleaned) <= 40:
            if not any(tok in cleaned.lower() for tok in ["resume", "curriculum", "vitae", "email", "phone", "linkedin"]):
                return cleaned
    return ""


def _infer_target_role(resume_text, role_hint, skills):
    lowered = (resume_text or "").lower()
    scored = []
    for role, hints in ROLE_HINTS:
        score = 0
        for hint in hints:
            if hint in lowered:
                score += 2
            if hint in skills:
                score += 3
        if role.lower() in lowered:
            score += 4
        scored.append((role, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    best_role, best_score = scored[0]
    if _strip(role_hint):
        if best_score >= 8:
            return best_role, min(98, 60 + best_score * 4)
        return _strip(role_hint), 70
    if best_score <= 2:
        return "", 0
    return best_role, min(98, 55 + best_score * 4)


def _merge_unique(primary, fallback, limit=12):
    merged = []
    seen = set()
    for item in (primary or []) + (fallback or []):
        val = str(item).strip()
        key = val.lower()
        if val and key not in seen:
            seen.add(key)
            merged.append(val)
        if len(merged) >= limit:
            break
    return merged


def _extract_resume_profile(resume_text, role_hint="", track="technical"):
    role_hint = _strip(role_hint)
    if not _strip(resume_text):
        return {
            "summary": "",
            "candidate_name": "",
            "preferred_role": role_hint,
            "skills": [],
            "projects": [],
            "experience_highlights": [],
            "education_highlights": [],
            "tools_tech": [],
            "hr_signals": [],
            "role_confidence": 0,
            "skills_confidence": 0,
        }

    heuristic_skills = _extract_explicit_skills(resume_text)
    inferred_role, role_confidence = _infer_target_role(resume_text, role_hint, heuristic_skills)
    candidate_name_heur = _extract_candidate_name(resume_text)

    prompt = (
        "Extract structured candidate profile from this resume with high precision.\n"
        "Return ONLY JSON with keys:\n"
        "summary, candidate_name, preferred_role, skills, projects, experience_highlights, education_highlights, tools_tech, hr_signals.\n"
        "Rules:\n"
        "- Do NOT invent information. If unknown, return empty string/list.\n"
        "- projects: list of short lines with project and impact.\n"
        "- experience_highlights: list of measurable achievements.\n"
        "- hr_signals: communication/team/leadership indicators from resume.\n"
        "- preferred_role: infer from evidence in resume content and skills, not generic assumptions.\n"
        "- skills/tools_tech: include only explicit or strongly implied technical skills.\n"
        f"Role hint: {role_hint}\n"
        f"Interview track: {track}\n"
        f"Resume:\n{resume_text[:18000]}"
    )
    try:
        text, _, _ = AI.text(prompt, temperature=0.15, max_tokens=900, prefer_json=True, operation="resume_parse")
        data = _parse_json(text) or {}
    except Exception:
        data = {}

    lines = [ln.strip(" -•\t").strip() for ln in (resume_text or "").splitlines() if ln.strip()]
    project_lines = [ln for ln in lines if "project" in ln.lower()][:6]
    exp_lines = [ln for ln in lines if any(k in ln.lower() for k in ["intern", "worked", "developed", "built", "implemented", "led"])][:8]
    edu_lines = [ln for ln in lines if any(k in ln.lower() for k in ["b.tech", "btech", "mca", "bca", "degree", "university", "college"])][:5]
    hr_lines = [ln for ln in lines if any(k in ln.lower() for k in ["team", "communication", "lead", "collaborat", "responsib", "managed"])][:6]

    ai_skills = _safe_list(data.get("skills"))
    ai_tools = _safe_list(data.get("tools_tech"))
    merged_skills = _merge_unique(ai_skills, heuristic_skills, limit=14)
    merged_tools = _merge_unique(ai_tools, heuristic_skills, limit=14)
    preferred_role = _strip(data.get("preferred_role")) or inferred_role or role_hint

    return {
        "summary": _strip(data.get("summary")) or _strip(" ".join(lines[:3]))[:320],
        "candidate_name": _strip(data.get("candidate_name")) or candidate_name_heur,
        "preferred_role": preferred_role,
        "skills": merged_skills,
        "projects": _safe_list(data.get("projects")) or project_lines,
        "experience_highlights": _safe_list(data.get("experience_highlights")) or exp_lines,
        "education_highlights": _safe_list(data.get("education_highlights")) or edu_lines,
        "tools_tech": merged_tools,
        "hr_signals": _safe_list(data.get("hr_signals")) or hr_lines,
        "role_confidence": role_confidence,
        "skills_confidence": min(98, 45 + (len(merged_skills) * 4)),
    }


def _compute_resume_ats_insights(profile, role_hint="", skills_hint="", track="technical", resume_text=""):
    role_hint = _strip(role_hint)
    skill_targets = [s.strip().lower() for s in (skills_hint or "").split(",") if s.strip()]
    resume_skills = [s.strip().lower() for s in (_safe_list(profile.get("skills")) + _safe_list(profile.get("tools_tech")))]
    resume_skill_set = set(resume_skills)

    # Keyword match
    if skill_targets:
        matched = [s for s in skill_targets if s in resume_skill_set]
        keyword_match = int(round((len(matched) / max(1, len(skill_targets))) * 100))
        missing = [s for s in skill_targets if s not in resume_skill_set][:8]
    else:
        keyword_match = min(95, 55 + min(40, len(resume_skill_set) * 4))
        missing = []

    # Structure quality
    project_count = len(_safe_list(profile.get("projects")))
    exp_count = len(_safe_list(profile.get("experience_highlights")))
    edu_count = len(_safe_list(profile.get("education_highlights")))
    structure_points = 0
    structure_points += 35 if project_count >= 2 else 20 if project_count == 1 else 8
    structure_points += 35 if exp_count >= 2 else 20 if exp_count == 1 else 10
    structure_points += 30 if edu_count >= 1 else 10
    structure_quality = min(100, structure_points)

    # Impact evidence
    metric_markers = ["%", "x", "users", "latency", "accuracy", "revenue", "ms", "reduced", "improved"]
    source_lines = _safe_list(profile.get("projects")) + _safe_list(profile.get("experience_highlights"))
    metric_hits = 0
    for ln in source_lines:
        low = ln.lower()
        if any(m in low for m in metric_markers):
            metric_hits += 1
    impact_evidence = min(100, 30 + metric_hits * 18)

    # Readability
    text_len = len(_strip(resume_text))
    sentence_count = max(1, _strip(resume_text).count(".") + _strip(resume_text).count("\n"))
    avg_len = text_len / sentence_count if sentence_count else text_len
    if text_len < 600:
        readability = 62
    elif text_len > 12000:
        readability = 68
    else:
        readability = 82
    if avg_len > 180:
        readability -= 8
    readability = max(45, min(95, int(readability)))

    ats_score = int(round((0.38 * keyword_match) + (0.22 * structure_quality) + (0.24 * impact_evidence) + (0.16 * readability)))
    if ats_score >= 85:
        band = "excellent"
        summary = "Strong ATS readiness. Your resume is well aligned for screening."
    elif ats_score >= 72:
        band = "good"
        summary = "Good ATS readiness. A few targeted improvements can increase shortlist chances."
    elif ats_score >= 58:
        band = "average"
        summary = "Moderate ATS readiness. Improve role alignment and quantified impact."
    else:
        band = "needs-work"
        summary = "ATS readiness is low. Improve structure, role keywords, and measurable outcomes."

    detected_highlights = []
    if _strip(profile.get("preferred_role")):
        detected_highlights.append(f"Role alignment detected: {profile.get('preferred_role')}")
    if project_count:
        detected_highlights.append(f"{project_count} project section(s) detected")
    if exp_count:
        detected_highlights.append(f"{exp_count} experience highlight(s) detected")
    if len(resume_skill_set):
        detected_highlights.append(f"{min(12, len(resume_skill_set))} relevant skills identified")

    suggestions = []
    if keyword_match < 70:
        suggestions.append("Add more role-specific keywords from your target job description.")
    if impact_evidence < 70:
        suggestions.append("Add measurable outcomes (%, scale, time saved, users impacted).")
    if structure_quality < 75:
        suggestions.append("Improve section structure: Projects, Experience, and Education with clear bullets.")
    if readability < 75:
        suggestions.append("Use concise bullet points and avoid long dense paragraphs.")
    if not suggestions:
        suggestions = [
            "Tailor resume keywords to each role before applying.",
            "Keep strongest quantified achievements near top sections.",
            "Refresh project descriptions with specific technical decisions.",
        ]

    return {
        "ats_score": ats_score,
        "band": band,
        "summary": summary,
        "breakdown": {
            "keyword_match": keyword_match,
            "structure_quality": structure_quality,
            "impact_evidence": impact_evidence,
            "readability": readability,
        },
        "missing_keywords": missing,
        "detected_highlights": detected_highlights[:6],
        "suggestions": suggestions[:6],
        "track": track,
        "target_role": role_hint or profile.get("preferred_role", ""),
    }


def _extract_jd_requirements(jd_text):
    jd_text = _strip(jd_text)
    if not jd_text:
        return []
    canonical = _skill_matches_in_text(jd_text)
    lines = [ln.strip(" -•\t").strip() for ln in jd_text.splitlines() if ln.strip()]
    req_lines = []
    for ln in lines:
        low = ln.lower()
        if any(k in low for k in ["require", "must", "preferred", "skill", "experience with", "proficient in"]):
            req_lines.append(ln)
    from_req_lines = _skill_matches_in_text("\n".join(req_lines)) if req_lines else []
    return _merge_unique(from_req_lines, canonical, limit=20)


def _extract_jd_role_hint(jd_text):
    jd_text = _strip(jd_text)
    if not jd_text:
        return ""
    top = " ".join(jd_text.splitlines()[:12]).lower()
    for role, hints in ROLE_HINTS:
        if role.lower() in top:
            return role
        if sum(1 for h in hints if h in top) >= 2:
            return role
    return ""


def _compute_jd_fit_insights(profile, jd_text, role_hint="", track="technical"):
    jd_text = _strip(jd_text)
    if not jd_text:
        return None
    resume_skills = {s.lower() for s in (_safe_list(profile.get("skills")) + _safe_list(profile.get("tools_tech")))}
    jd_requirements = [s.lower() for s in _extract_jd_requirements(jd_text)]
    if not jd_requirements:
        return {
            "fit_score": 0,
            "summary": "Job description parsed, but no clear technical requirements were detected.",
            "matched_skills": [],
            "missing_skills": [],
            "coverage_percent": 0,
            "target_role": _extract_jd_role_hint(jd_text) or role_hint or "",
        }

    matched = [s for s in jd_requirements if s in resume_skills]
    missing = [s for s in jd_requirements if s not in resume_skills]
    coverage = int(round((len(matched) / max(1, len(jd_requirements))) * 100))
    jd_role = _extract_jd_role_hint(jd_text) or role_hint
    resume_role = _strip(profile.get("preferred_role")).lower()
    role_alignment = 100 if jd_role and resume_role and jd_role.lower() in resume_role else 70 if jd_role else 60
    fit_score = int(round((0.75 * coverage) + (0.25 * role_alignment)))

    if fit_score >= 80:
        summary = "Strong JD fit. Your resume aligns well with the role requirements."
    elif fit_score >= 60:
        summary = "Moderate JD fit. You match core requirements but can improve alignment."
    else:
        summary = "Low JD fit. Add more evidence for required tools/skills in your resume."

    return {
        "fit_score": fit_score,
        "summary": summary,
        "matched_skills": matched[:12],
        "missing_skills": missing[:12],
        "coverage_percent": coverage,
        "target_role": jd_role or "",
        "total_requirements": len(jd_requirements),
    }


def _question_stage(question_number, track="technical"):
    track = track if track in INTERVIEW_TRACKS else "technical"
    if question_number <= 1:
        return "introduction"
    if track == "technical":
        if question_number <= 3:
            return "technical-core"
        if question_number <= 5:
            return "technical-depth"
        if question_number <= 7:
            return "problem-solving"
    else:
        if question_number <= 3:
            return "hr-core"
        if question_number <= 5:
            return "behavioral"
        if question_number <= 7:
            return "situational-hr"
    return "final-evaluation"


def _response_quality(answer):
    text = _strip(answer)
    words = text.split()
    
    # Action-oriented and strategic language
    action_words = ["built", "designed", "implemented", "optimized", "led", "improved", "delivered", "solved", "analyzed", "managed"]
    # Indicators of measurable impact
    metric_markers = ["%", "x", "ms", "days", "weeks", "users", "latency", "throughput", "revenue", "cost", "conversion"]
    # Indicators of structured thinking (STAR)
    structure_words = ["because", "therefore", "result", "initially", "challenge", "situation", "task", "impact"]
    
    has_action = any(word in text.lower() for word in action_words)
    has_metric = any(marker in text.lower() for marker in metric_markers)
    has_structure = any(word in text.lower() for word in structure_words)
    
    score = 0
    # Length: 40+ words is usually a good detail level
    score += 30 if len(words) >= 45 else 20 if len(words) >= 25 else 5
    # Substance: Action verbs show ownership
    score += 25 if has_action else 5
    # Impact: Numbers/metrics show results
    score += 25 if has_metric else 5
    # Structure: Logical connectors show clear thinking
    score += 20 if has_structure else 5
    
    return {
        "word_count": len(words),
        "has_action_language": has_action,
        "has_metrics": has_metric,
        "has_structure": has_structure,
        "quality_score": min(100, score),
    }


def _to_band(value):
    value = _strip(value).lower()
    return value if value in BAND_ORDER else "standard"


def _clamp_score(value):
    try:
        return float(max(0, min(100, round(float(value), 2))))
    except Exception:
        return 0.0


def _profile_skill_tags(session):
    parsed = session.parsed_resume_data if isinstance(session.parsed_resume_data, dict) else {}
    profile = parsed.get("resume_profile", {}) if isinstance(parsed.get("resume_profile"), dict) else {}
    tags = []
    tags.extend(_technical_skill_tokens(session))
    tags.extend([s.strip().lower() for s in _safe_list(profile.get("hr_signals"))])
    dedup = []
    seen = set()
    for item in tags:
        cleaned = re.sub(r"\s+", " ", str(item).strip().lower())
        if cleaned and cleaned not in seen:
            dedup.append(cleaned)
            seen.add(cleaned)
    return dedup[:12]


def _extract_skill_tags(session, answer):
    tags = []
    text = _strip(answer).lower()
    for token in _profile_skill_tags(session):
        if token in text:
            tags.append(token)

    heuristics = {
        "communication": ["communicat", "explain", "present", "collaborat"],
        "ownership": ["owned", "ownership", "responsib", "initiative", "led"],
        "problem-solving": ["debug", "solved", "fixed", "root cause", "issue"],
        "metrics": ["%", "latency", "throughput", "users", "revenue", "cost"],
        "architecture": ["architecture", "design", "microservice", "scal", "system"],
    }
    for tag, words in heuristics.items():
        if any(w in text for w in words):
            tags.append(tag)

    dedup = []
    seen = set()
    for item in tags:
        item = str(item).strip().lower()
        if item and item not in seen:
            dedup.append(item)
            seen.add(item)
    return dedup[:8]


def _assign_starting_band(user, track, ats_score=None):
    recent_scores = list(
        MockInterviewSession.objects.filter(user=user, score__isnull=False)
        .exclude(status="CANCELLED")
        .order_by("-created_at")
        .values_list("score", flat=True)[:5]
    )
    recent_avg = float(sum(float(s) for s in recent_scores) / len(recent_scores)) if recent_scores else None
    score_seed = recent_avg if recent_avg is not None else 68
    if ats_score is not None:
        score_seed = (0.65 * score_seed) + (0.35 * float(ats_score))
    if track == "hr":
        score_seed -= 2
    if score_seed >= 82:
        return "advanced", 74.0
    if score_seed <= 56:
        return "foundation", 74.0
    return "standard", 68.0


def _score_turn(session, answer):
    quality = _response_quality(answer)
    text = _strip(answer).lower()
    comm = (
        (35 if quality["word_count"] >= 30 else 18)
        + (30 if quality["has_structure"] else 10)
        + (20 if any(w in text for w in ["team", "stakeholder", "collaborat", "communicat"]) else 8)
        + (15 if any(w in text for w in ["clearly", "therefore", "result"]) else 7)
    )
    tech = (
        (40 if quality["has_action_language"] else 12)
        + (30 if quality["has_metrics"] else 10)
        + (20 if any(w in text for w in ["tradeoff", "latency", "scal", "design", "complexity"]) else 8)
        + (10 if quality["word_count"] >= 45 else 4)
    )
    conf = (
        (40 if quality["word_count"] >= 25 else 15)
        + (35 if quality["has_action_language"] else 12)
        + (25 if not any(w in text for w in ["maybe", "not sure", "i think", "probably"]) else 8)
    )
    comm = _clamp_score(comm)
    tech = _clamp_score(tech)
    conf = _clamp_score(conf)
    turn_score = _clamp_score((0.3 * comm) + (0.45 * tech) + (0.25 * conf))
    return {
        "turn_score": turn_score,
        "communication_score": comm,
        "technical_score": tech,
        "confidence_score": conf,
        "word_count": quality["word_count"],
        "has_action_language": quality["has_action_language"],
        "has_metrics": quality["has_metrics"],
        "has_structure": quality["has_structure"],
        "quality_score": quality["quality_score"],
        "quality_snapshot": quality,
        "skill_tags": _extract_skill_tags(session, answer),
    }


def _band_transition(current_band, recent_turn_scores):
    current_band = _to_band(current_band)
    if len(recent_turn_scores) < 2:
        return current_band
    last_two = recent_turn_scores[-2:]
    idx = BAND_ORDER.index(current_band)
    if min(last_two) >= 75 and idx < len(BAND_ORDER) - 1:
        return BAND_ORDER[idx + 1]
    if max(last_two) <= 45 and idx > 0:
        return BAND_ORDER[idx - 1]
    return current_band


def _update_session_skill_memory(session):
    answered_turns = session.turns.exclude(turn_score__isnull=True).order_by("turn_number")
    weak = []
    strong = []
    for turn in answered_turns:
        tags = [str(t).strip().lower() for t in (turn.skill_tags or []) if str(t).strip()]
        if not tags:
            continue
        if float(turn.turn_score or 0) <= 50:
            weak.extend(tags)
        if float(turn.turn_score or 0) >= 75:
            strong.extend(tags)

    def _top(items):
        counts = {}
        for item in items:
            counts[item] = counts.get(item, 0) + 1
        ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        return [k for k, _ in ranked][:6]

    session.weak_skill_tags = _top(weak)
    session.strong_skill_tags = _top(strong)


def _next_focus_skills(session):
    parsed = session.parsed_resume_data if isinstance(session.parsed_resume_data, dict) else {}
    jd_fit = parsed.get("jd_fit", {}) if isinstance(parsed.get("jd_fit"), dict) else {}
    jd_missing = [s for s in _safe_list(jd_fit.get("missing_skills")) if s]
    weak = [s for s in (session.weak_skill_tags or []) if s]
    strong = [s for s in (session.strong_skill_tags or []) if s]
    pool = weak[:3] + [s for s in jd_missing if s not in weak][:3]
    pool = pool[:3]
    if len(pool) < 3:
        for skill in _technical_skill_tokens(session):
            if skill not in pool:
                pool.append(skill)
            if len(pool) == 3:
                break
    if len(pool) < 3:
        for skill in strong:
            if skill not in pool:
                pool.append(skill)
            if len(pool) == 3:
                break
    return pool[:3]


def _difficulty_for_question(session, stage):
    band = _to_band(session.current_band or session.performance_band or "standard")
    if stage == "final-evaluation":
        return "medium" if band == "foundation" else "hard" if band == "advanced" else "medium"
    return BAND_TO_DIFFICULTY.get(band, "medium")


def _session_track(session):
    parsed = session.parsed_resume_data if isinstance(session.parsed_resume_data, dict) else {}
    track = _strip(parsed.get("interview_track")) or "technical"
    return track if track in INTERVIEW_TRACKS else "technical"


def _technical_skill_tokens(session):
    parsed = session.parsed_resume_data if isinstance(session.parsed_resume_data, dict) else {}
    profile = parsed.get("resume_profile", {}) if isinstance(parsed.get("resume_profile"), dict) else {}
    raw = []
    raw.extend([s.strip().lower() for s in (session.key_skills or "").split(",") if s.strip()])
    raw.extend([s.strip().lower() for s in _safe_list(profile.get("skills"))])
    raw.extend([s.strip().lower() for s in _safe_list(profile.get("tools_tech"))])
    dedup = []
    seen = set()
    for item in raw:
        if item and item not in seen:
            seen.add(item)
            dedup.append(item)
    return dedup


def _technical_fundamental_question(session, turns):
    skills = _technical_skill_tokens(session)
    candidates = []
    for skill in skills:
        for key, questions in FUNDAMENTAL_TECH_QUESTION_BANK.items():
            if key in skill or skill in key:
                candidates.extend(questions)
    candidates.extend(GENERIC_TECH_QUESTIONS)

    if not candidates:
        candidates = list(GENERIC_TECH_QUESTIONS)

    # Rotate to avoid always picking first and keep deterministic by turn count.
    offset = turns.count() % len(candidates)
    ordered = candidates[offset:] + candidates[:offset]
    for q in ordered:
        if not _is_repetitive_question(q, turns):
            return q
    return ordered[0]


def _build_interview_plan(session):
    parsed = session.parsed_resume_data if isinstance(session.parsed_resume_data, dict) else {}
    track = _strip(parsed.get("interview_track")) or "technical"
    if track not in INTERVIEW_TRACKS:
        track = "technical"
    profile = parsed.get("resume_profile", {}) if isinstance(parsed.get("resume_profile"), dict) else {}
    jd_fit = parsed.get("jd_fit", {}) if isinstance(parsed.get("jd_fit"), dict) else {}
    if not jd_fit and _strip(parsed.get("job_description")):
        jd_fit = _compute_jd_fit_insights(
            profile,
            parsed.get("job_description", ""),
            role_hint=session.job_role,
            track=track,
        ) or {}

    skills = [s.strip() for s in (session.key_skills or "").split(",") if s.strip()]
    resume_skills = _safe_list(profile.get("skills")) + _safe_list(profile.get("tools_tech"))
    jd_missing = _safe_list(jd_fit.get("missing_skills"))
    jd_matched = _safe_list(jd_fit.get("matched_skills"))
    top_skills = (jd_missing + skills + resume_skills + jd_matched or (TECHNICAL_TOPICS if track == "technical" else HR_TOPICS))[:6]
    focus_tracks = [
        {"stage": "introduction", "goal": "Resume-based introduction and context setup"},
    ]
    if track == "technical":
        focus_tracks.extend(
            [
                {"stage": "technical-core", "goal": "Core technical work from resume projects"},
                {"stage": "technical-depth", "goal": "Depth on architecture, choices, debugging"},
                {"stage": "problem-solving", "goal": "Scenario-based technical reasoning"},
            ]
        )
    else:
        focus_tracks.extend(
            [
                {"stage": "hr-core", "goal": "Motivation, communication, collaboration"},
                {"stage": "behavioral", "goal": "Ownership, conflict, growth examples"},
                {"stage": "situational-hr", "goal": "Workplace scenarios and judgement"},
            ]
        )
    focus_tracks.append({"stage": "final-evaluation", "goal": "Closing and reflective wrap-up"})
    return {
        "role": session.job_role or "General role",
        "track": track,
        "total_questions": MAX_INTERVIEW_QUESTIONS,
        "focus_tracks": focus_tracks,
        "skills_focus": top_skills,
        "jd_context": {
            "target_role": _strip(jd_fit.get("target_role")),
            "fit_score": jd_fit.get("fit_score"),
            "matched_skills": jd_matched[:8],
            "missing_skills": jd_missing[:8],
        },
        "resume_anchor": {
            "candidate_name": _strip(profile.get("candidate_name")),
            "summary": _strip(profile.get("summary")),
            "projects": _safe_list(profile.get("projects"))[:5],
            "experience_highlights": _safe_list(profile.get("experience_highlights"))[:5],
            "hr_signals": _safe_list(profile.get("hr_signals"))[:5],
        },
    }


def _build_question_prompt(session, turns, user_response, time_remaining=None, difficulty_level="medium", focus_skills=None):
    next_q = turns.count() + 1
    parsed = session.parsed_resume_data if isinstance(session.parsed_resume_data, dict) else {}
    track = _strip(parsed.get("interview_track")) or "technical"
    if track not in INTERVIEW_TRACKS:
        track = "technical"
    stage = _question_stage(next_q, track=track)
    plan = (session.parsed_resume_data or {}).get("interview_plan", {})
    plan_skills = ", ".join(plan.get("skills_focus", [])) if isinstance(plan, dict) else ""
    resume_anchor = plan.get("resume_anchor", {}) if isinstance(plan, dict) else {}
    jd_context = plan.get("jd_context", {}) if isinstance(plan, dict) else {}
    resume_projects = "; ".join(_safe_list(resume_anchor.get("projects"))[:3])
    resume_exp = "; ".join(_safe_list(resume_anchor.get("experience_highlights"))[:3])
    resume_hr = "; ".join(_safe_list(resume_anchor.get("hr_signals"))[:3])
    jd_missing = ", ".join(_safe_list(jd_context.get("missing_skills"))[:5])
    jd_matched = ", ".join(_safe_list(jd_context.get("matched_skills"))[:5])
    jd_target_role = _strip(jd_context.get("target_role"))
    candidate_name = _strip(resume_anchor.get("candidate_name"))
    question_style = "fundamental skill-based technical question" if (track == "technical" and next_q > 1 and next_q % 2 == 0) else "resume-anchored question"
    adaptive_band = _to_band(session.current_band or session.performance_band)
    focus_text = ", ".join(focus_skills or _next_focus_skills(session))
    if adaptive_band == "foundation":
        adaptive_instruction = "Keep the question straightforward, avoid heavy jargon, and guide with concrete context."
    elif adaptive_band == "advanced":
        adaptive_instruction = "Ask a high-rigor question requiring tradeoffs, edge cases, and measurable reasoning."
    else:
        adaptive_instruction = "Ask a balanced question with practical depth linked to resume context."

    history = []
    recent_turns = list(turns.order_by("-turn_number")[:6])[::-1]
    for t in recent_turns:
        if t.ai_question:
            history.append(f"Interviewer: {t.ai_question}")
        if t.user_answer:
            history.append(f"Candidate: {t.user_answer}")
    time_str = f"{time_remaining // 60}m {time_remaining % 60}s" if time_remaining is not None else "15m 00s"
    return (
        "SYSTEM: You are Elevo, an empathetic, expert AI interviewer. Your goal is to conduct a high-quality mock interview that feels like a natural conversation with a human mentor.\n"
        "CORE PERSONA:\n"
        "- Warm, supportive, and professional.\n"
        "- Practice ACTIVE LISTENING. Acknowledge the candidate's specific points before pivoting to the next question.\n"
        "- Avoid generic responses like 'Great job' or 'Nice work'. Instead, say something like 'That's a solid approach to [topic]...' or 'Your experience with [project] sounds quite relevant...'\n\n"
        f"SESSION CONTEXT:\n"
        f"- Target Role: {session.job_role}\n"
        f"- Session Track: {track}\n"
        f"- Time Remaining: {time_str}\n"
        f"- Progress: {next_q}/{MAX_INTERVIEW_QUESTIONS}\n"
        f"- Candidate: {candidate_name or 'Friend'}\n"
        f"- Skills Focus: {focus_text or plan_skills or session.key_skills or 'general'}\n"
        f"- Adaptive Band: {adaptive_band}\n"
        f"- Difficulty: {difficulty_level}\n"
        f"- Interview Pack: {session.selected_pack or 'default'}\n"
        f"RESUME GROUNDING:\n"
        f"- Projects: {resume_projects or 'None'}\n"
        f"- Work Highlights: {resume_exp or 'None'}\n\n"
        f"JD CONTEXT:\n"
        f"- Target JD Role: {jd_target_role or 'None'}\n"
        f"- JD Matched Skills: {jd_matched or 'None'}\n"
        f"- JD Missing Skills to Probe: {jd_missing or 'None'}\n\n"
        f"CONVERSATION HISTORY:\n"
        f"{chr(10).join(history) if history else 'None'}\n\n"
        f"CANDIDATE'S LATEST RESPONSE:\n{user_response or '(Start of interview)'}\n\n"
        "TASK:\n"
        "1. Start with a brief (1 sentence) 'Active Listening' acknowledgement that references a detail from their latest response.\n"
        f"2. Ask ONE high-quality leading question for the '{stage}' stage.\n"
        "- If Technical: Dig into architecture, technical decisions, or troubleshooting.\n"
        "- If HR/Behavioral: Use situational scenarios or explore their ownership/communication style.\n"
        "- Ensure the question is grounded in their resume context.\n"
        f"- Adaptive rule: {adaptive_instruction}\n"
        f"- Desired question style: {question_style}\n"
        "- Keep total response under 60 words. Plain text only."
    )


def _generate_personalized_opening(session):
    """
    Generate a warm, AI-driven opening message based on resume context.
    """
    parsed = session.parsed_resume_data if isinstance(session.parsed_resume_data, dict) else {}
    plan = parsed.get("interview_plan", {}) if isinstance(parsed.get("interview_plan"), dict) else {}
    anchor = plan.get("resume_anchor", {}) if isinstance(plan.get("resume_anchor"), dict) else {}
    
    role = session.job_role or "your target role"
    track = _strip(parsed.get("interview_track")) or "technical"
    candidate_name = _strip(anchor.get("candidate_name"))
    summary = _strip(anchor.get("summary"))
    projects = _safe_list(anchor.get("projects"))
    
    prompt = (
        "You are Elevo, a friendly and professional AI interviewer. Write a warm, human-like opening for a mock interview.\n"
        f"Candidate: {candidate_name or 'there'}\n"
        f"Role: {role}\n"
        f"Track: {track}\n"
        f"Resume Summary: {summary[:500]}\n"
        f"Top Project: {projects[0] if projects else 'N/A'}\n"
        "Requirements:\n"
        "- Start with a warm greeting.\n"
        "- Mention one specific highlight from their resume summary or project to show you've read it.\n"
        "- Explain that this is a mock session for the target role.\n"
        "- End by asking them to introduce themselves and summarize their recent work.\n"
        "- Keep it under 65 words. Plain text only."
    )
    
    try:
        text, provider, model = AI.text(prompt, temperature=0.7, max_tokens=400, operation="opening")
        opening = _strip(text)
        if opening and len(opening.split()) >= 12:
            return opening
        # If the opening was too short / truncated, retry once with higher token budget
        logger.warning("Opening too short (%d words), retrying with higher budget", len((opening or '').split()))
        text2, _, _ = AI.text(prompt, temperature=0.7, max_tokens=600, operation="opening_retry")
        opening2 = _strip(text2)
        if opening2 and len(opening2.split()) >= 12:
            return opening2
    except Exception as exc:
        logger.warning("Personalized opening failed: %s", exc)
        
    # Fallback to the original static style but slightly improved
    intro_name = f" {candidate_name}" if candidate_name else ""
    mode_label = "technical" if track == "technical" else "HR"
    return (
        f"Hi{intro_name}, I'm Elevo! It's great to meet you. I've been looking over your profile, and I'm excited to dive in. "
        f"We'll be conducting a {mode_label} mock interview for the {role} position today. "
        "To get us started, could you please introduce yourself and give me a quick overview of your background?"
    )


def _opening_message(session):
    return _generate_personalized_opening(session)


def _is_incomplete_turn(text):
    msg = _strip(text)
    if not msg:
        return True
    low = msg.lower()
    words = msg.split()
    dangling = {"it", "this", "that", "and", "but", "so", "because", "then", "also", "about"}
    if len(words) < 9:
        return True
    if words[-1].strip(".,!?").lower() in dangling:
        return True
    if msg.endswith(",") or msg.endswith(":") or msg.endswith("-"):
        return True
    if "?" not in msg:
        return True
    # Avoid meta/robotic fragment style that often appears in truncated outputs.
    if "when i asked" in low or "as mentioned earlier" in low:
        return True
    return False


def _repair_turn_prompt(session, stage, broken_text, user_response):
    return (
        "Rewrite the interviewer response into one complete natural message.\n"
        "Rules:\n"
        "- First: one short appreciation sentence.\n"
        "- Second: one clear interview question.\n"
        "- Use simple human English.\n"
        "- 22 to 55 words total.\n"
        "- Must end with '?'\n"
        f"Role: {session.job_role}\n"
        f"Stage: {stage}\n"
        f"Candidate latest response: {user_response}\n"
        f"Broken draft to repair: {broken_text}\n"
        "Return plain text only."
    )


def _normalize_for_match(text):
    cleaned = re.sub(r"[^a-z0-9\s]", " ", _strip(text).lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _is_repetitive_question(candidate_text, turns):
    new_q = _normalize_for_match(candidate_text)
    if not new_q:
        return True
    recent_questions = [t.ai_question for t in turns.order_by("-turn_number")[:4] if t.ai_question]
    for old in recent_questions:
        old_q = _normalize_for_match(old)
        if not old_q:
            continue
        sim = SequenceMatcher(None, new_q, old_q).ratio()
        if sim >= 0.78:
            return True
        old_tokens = set(old_q.split())
        new_tokens = set(new_q.split())
        overlap = len(old_tokens & new_tokens) / max(1, len(new_tokens))
        if overlap >= 0.75:
            return True
    return False


def _targeted_followup_prompt(session, stage, user_response, recent_questions):
    parsed = session.parsed_resume_data if isinstance(session.parsed_resume_data, dict) else {}
    track = _strip(parsed.get("interview_track")) or "technical"
    plan = parsed.get("interview_plan", {}) if isinstance(parsed.get("interview_plan"), dict) else {}
    anchor = plan.get("resume_anchor", {}) if isinstance(plan.get("resume_anchor"), dict) else {}
    resume_projects = "; ".join(_safe_list(anchor.get("projects"))[:3])
    resume_exp = "; ".join(_safe_list(anchor.get("experience_highlights"))[:3])
    resume_hr = "; ".join(_safe_list(anchor.get("hr_signals"))[:3])
    recent = "\n".join([f"- {q}" for q in recent_questions]) if recent_questions else "- none"
    return (
        "You are Elevo, an expert interviewer practicing active listening.\n"
        "TASK: Write a personalized follow-up response that digs deeper into the candidate's last answer.\n\n"
        "REQUIREMENTS:\n"
        "- ACKNOWLEDGE: Briefly mention a specific technical or behavioral point they just made.\n"
        "- PROBE: Ask a 'Why' or 'How' question that explores their specific contribution or decision-making process.\n"
        "- NO REPETITION: Do not repeat or paraphrase previous questions.\n"
        "- CONCISE: 25-55 words total. Plain text only.\n\n"
        f"Role: {session.job_role} | Track: {track} | Stage: {stage}\n"
        f"Resume context: {resume_projects or resume_exp or 'N/A'}\n"
        f"Candidate answer: {user_response}\n"
        f"Recent questions to avoid:\n{recent}\n"
    )


def _fallback_followup_question(stage, user_response, turns, session, difficulty_level="medium", focus_skills=None):
    answer = _strip(user_response).lower()
    role = session.job_role or "this role"
    parsed = session.parsed_resume_data if isinstance(session.parsed_resume_data, dict) else {}
    track = _strip(parsed.get("interview_track")) or "technical"
    plan = parsed.get("interview_plan", {}) if isinstance(parsed.get("interview_plan"), dict) else {}
    anchor = plan.get("resume_anchor", {}) if isinstance(plan.get("resume_anchor"), dict) else {}
    resume_projects = _safe_list(anchor.get("projects"))
    resume_exp = _safe_list(anchor.get("experience_highlights"))
    resume_hr = _safe_list(anchor.get("hr_signals"))
    project_anchor = resume_projects[0] if resume_projects else "one project from your resume"
    exp_anchor = resume_exp[0] if resume_exp else "one experience item from your resume"
    hr_anchor = resume_hr[0] if resume_hr else "one teamwork or communication example in your resume"

    focus_primary = (focus_skills or _next_focus_skills(session) or ["core fundamentals"])[0]
    if track == "technical":
        fundamentals_q = _technical_fundamental_question(session, turns)
        stage_options = {
            "introduction": [
                f"Thanks for sharing. Which resume project best represents your fit for {role}, and why?",
                f"Nice introduction. In {project_anchor}, what specific technical responsibility did you own?",
            ],
            "technical-core": [
                f"Good start. In your resume project '{project_anchor}', what stack did you use and why?",
                f"Thanks. Can you explain the core logic or pipeline in {project_anchor}?",
                fundamentals_q,
            ],
            "technical-depth": [
                f"Understood. In {project_anchor}, what was the toughest technical issue and how did you debug it?",
                f"Thanks. Based on {exp_anchor}, what tradeoff did you make between speed and quality?",
                fundamentals_q,
                f"Can you walk through one deeper technical decision around {focus_primary} and why you chose that path?",
            ],
            "problem-solving": [
                f"If {project_anchor} had 10x more data/users, what technical changes would you make first?",
                f"In {project_anchor}, how would you improve performance or reliability in the next iteration?",
                fundamentals_q,
                f"Suppose {focus_primary} fails in production. What would be your first diagnosis and rollback strategy?",
            ],
            "final-evaluation": [
                f"Great discussion. From your resume work, which technical area do you want to deepen next for {role}?",
                f"Thanks. What technical outcome would you target in your first month if hired for {role}?",
            ],
        }
    else:
        stage_options = {
            "introduction": [
                f"Thanks for sharing. What motivated you to pursue {role} based on your resume journey?",
                f"Nice introduction. Which resume experience shaped your work style the most?",
            ],
            "hr-core": [
                f"In '{hr_anchor}', what communication approach helped you work effectively with others?",
                f"Thanks. From your resume experience, how do you prioritize when tasks compete for time?",
            ],
            "behavioral": [
                f"Can you share a situation from your resume where you handled disagreement constructively?",
                f"From your listed experience, what feedback changed the way you work?",
            ],
            "situational-hr": [
                "If a teammate misses deadlines repeatedly, how would you handle it professionally?",
                "How would you explain a complex issue to a non-technical manager in simple language?",
            ],
            "final-evaluation": [
                f"What values from your resume experiences will you bring to this {role} role from day one?",
                "How do you define success for yourself in the first 90 days of a new team?",
            ],
        }

    # If candidate says they had no problem/challenge, pivot to positive contribution instead of repeating challenge question.
    if "no problem" in answer or "no issues" in answer or "none" == answer.strip():
        stage_options["technical-depth"] = [
            f"No worries. In {project_anchor}, what design choice are you most confident about, and why?",
            f"That is fine. What was the most successful technical decision you made in {project_anchor}?",
        ]
        stage_options["behavioral"] = [
            f"No worries. From your resume, share one example where you supported a teammate effectively.",
            f"That is fine. Which responsibility in your resume best shows your ownership style?",
        ]

    default_stage = "technical-core" if track == "technical" else "hr-core"
    options = stage_options.get(stage, stage_options.get(default_stage, []))

    # In technical mode, alternate resume question and fundamentals after introduction.
    if track == "technical" and stage in {"technical-core", "technical-depth", "problem-solving"} and turns.count() % 2 == 0:
        options = [_technical_fundamental_question(session, turns)] + options
    if difficulty_level == "easy":
        options = list(reversed(options))
    elif difficulty_level == "hard":
        options = options + [
            f"What tradeoff did you make around {focus_primary}, and what alternative would you test next?",
            f"How would you validate that your {focus_primary} decision improved reliability or performance?",
        ]
    for candidate in options:
        if not _is_repetitive_question(candidate, turns):
            return candidate

    # Last-resort dynamic fallback guaranteed to change by turn count.
    return (
        f"Thanks for sharing. Based on your answer, what is one specific improvement you would make "
        f"if you did a similar task again for {role}?"
    )


def _default_feedback(session):
    return {
        "overall_score": 70,
        "communication_score": 68,
        "confidence_level": "Developing",
        "strengths": ["Completed the session", "Stayed engaged", "Discussed relevant topics"],
        "areas_for_improvement": ["Use STAR examples", "Add measurable impact", "Improve structure"],
        "technical_assessment": f"Baseline fit for {session.job_role or 'target role'}; improve depth and tradeoff discussion.",
        "recommendations": ["Practice concise storytelling", "Prepare project examples", "Run mock interviews regularly"],
        "encouragement_note": "Good progress. Keep practicing and refine your responses.",
    }


def _coerce_feedback(payload, session):
    base = _default_feedback(session)
    if not isinstance(payload, dict):
        return base
    merged = {k: payload.get(k, base[k]) for k in base}
    for key in ["strengths", "areas_for_improvement", "recommendations"]:
        if isinstance(merged[key], str):
            merged[key] = [merged[key]]
        elif not isinstance(merged[key], list):
            merged[key] = [str(merged[key])]
    for key in ["overall_score", "communication_score"]:
        try:
            merged[key] = max(0, min(100, int(float(merged[key]))))
        except Exception:
            merged[key] = base[key]
    return merged


def _generate_feedback(session):
    turns = session.turns.all().order_by("turn_number")
    transcript = []
    for t in turns:
        if t.ai_question:
            transcript.append(f"Q{t.turn_number}: {t.ai_question}")
        if t.user_answer:
            transcript.append(f"A{t.turn_number}: {t.user_answer}")
    prompt = (
        "You are an expert Interview Coach. Analyze the following interview transcript and provide constructive, detailed feedback.\n"
        "Return ONLY valid JSON with keys: overall_score, communication_score, confidence_level, strengths, "
        "areas_for_improvement, technical_assessment, recommendations, encouragement_note.\n\n"
        "EVALUATION CRITERIA:\n"
        "- Did the candidate use the STAR method (Situation, Task, Action, Result)?\n"
        "- Was there clear measurable impact (%, numbers, scale)?\n"
        "- How deep was the technical maturity shown?\n"
        "- Was the communication structured and professional?\n\n"
        f"Target Role: {session.job_role}\n"
        f"Required Skills: {session.key_skills}\n"
        f"Transcript:\n{chr(10).join(transcript)}"
    )
    try:
        text, provider, model = AI.text(prompt, temperature=0.35, max_tokens=800, prefer_json=True,
                                          operation="feedback")
        logger.info("Feedback generated by %s/%s", provider, model)
        return _coerce_feedback(_parse_json(text), session)
    except Exception as exc:
        logger.warning("Feedback generation fallback: %s", exc)
        return _default_feedback(session)


def _next_question(session, turns, user_response, time_remaining=None):
    next_q = turns.count() + 1
    parsed = session.parsed_resume_data if isinstance(session.parsed_resume_data, dict) else {}
    track = _strip(parsed.get("interview_track")) or "technical"
    if track not in INTERVIEW_TRACKS:
        track = "technical"
    stage = _question_stage(next_q, track=track)
    difficulty_level = _difficulty_for_question(session, stage)
    focus_skills = _next_focus_skills(session)
    recent_questions = [t.ai_question for t in turns.order_by("-turn_number")[:4] if t.ai_question]
    prompt = _build_question_prompt(
        session,
        turns,
        user_response,
        time_remaining=time_remaining,
        difficulty_level=difficulty_level,
        focus_skills=focus_skills,
    )
    broken_text = ""
    try:
        text, provider, model = AI.text(prompt, temperature=0.6, max_tokens=300,
                                          operation="question")
        question = _strip(text)
        if question and not _is_incomplete_turn(question):
            return question, {
                "provider": provider,
                "model": model,
                "stage": stage,
                "difficulty_level": difficulty_level,
                "focus_skills": focus_skills,
            }
        # Store the broken/truncated text for repair attempt
        broken_text = question or ""
        logger.warning("Incomplete question detected (%d words), attempting repair", len(broken_text.split()))
    except Exception as exc:
        logger.warning("Question generation error: %s", exc)

    # --- Repair attempt: ask AI to fix the broken/truncated response ---
    if broken_text:
        try:
            repair_prompt = _repair_turn_prompt(session, stage, broken_text, user_response)
            repaired, rprov, rmodel = AI.text(repair_prompt, temperature=0.5, max_tokens=300,
                                               operation="question_repair")
            repaired_q = _strip(repaired)
            if repaired_q and not _is_incomplete_turn(repaired_q):
                return repaired_q, {
                    "provider": rprov,
                    "model": rmodel,
                    "stage": stage,
                    "difficulty_level": difficulty_level,
                    "focus_skills": focus_skills,
                }
        except Exception as exc:
            logger.warning("Question repair failed: %s", exc)

    choice = _fallback_followup_question(
        stage,
        user_response,
        turns,
        session,
        difficulty_level=difficulty_level,
        focus_skills=focus_skills,
    )
    return choice, {
        "provider": "fallback",
        "model": "static",
        "stage": stage,
        "difficulty_level": difficulty_level,
        "focus_skills": focus_skills,
    }


def _closing(session, answered_count):
    prompt = (
        "Write a warm interview closing message in 3-4 sentences in simple English. Plain text only.\n"
        f"Role: {session.job_role}\nAnswered questions: {answered_count}"
    )
    try:
        text, provider, model = AI.text(prompt, temperature=0.6, max_tokens=180,
                                          operation="closing")
        if _strip(text):
            return _strip(text), {"provider": provider, "model": model}
    except Exception as exc:
        logger.warning("Closing generation fallback: %s", exc)
    return FALLBACK_CLOSING, {"provider": "fallback", "model": "static"}


def _queue_feedback_generation(session):
    if async_task is None:
        try:
            feedback = _generate_feedback(session)
            session.overall_feedback = json.dumps(feedback)
            session.score = feedback.get("overall_score")
            session.feedback_status = "ready"
            session.status = "COMPLETED"
            session.save(update_fields=["overall_feedback", "score", "feedback_status", "status", "updated_at"])
        except Exception as exc:
            session.feedback_status = "failed"
            session.feedback_error = str(exc)[:500]
            session.status = "COMPLETED"
            session.save(update_fields=["feedback_status", "feedback_error", "status", "updated_at"])
        return
    try:
        async_task("mock_interview.tasks.async_generate_feedback", session.id)
    except Exception as exc:
        logger.warning("Async feedback queue failed, using sync fallback: %s", exc)
        feedback = _generate_feedback(session)
        session.overall_feedback = json.dumps(feedback)
        session.score = feedback.get("overall_score")
        session.feedback_status = "ready"
        session.status = "COMPLETED"
        session.save(update_fields=["overall_feedback", "score", "feedback_status", "status", "updated_at"])


@login_required
@user_passes_test(is_student, login_url="/login/")
def start_mock_interview(request):
    return redirect("mock_interview:interview_setup")


@login_required
@user_passes_test(is_student, login_url="/login/")
def interview_setup(request):
    """
    Step 1: Onboarding for mock interview.
    Collect job role, skills, and optionally a resume (file or profile-based).
    """
    # --- Subscription Limit Check ---
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    interviews_this_month = MockInterviewSession.objects.filter(
        user=request.user,
        created_at__gte=month_start
    ).count()

    # Determine limit (from org plan or default free tier)
    monthly_limit = 2 # Default for individual free users
    if hasattr(request, 'premium_plan') and request.premium_plan:
        monthly_limit = request.premium_plan.max_interviews_monthly
    
    if monthly_limit != -1 and interviews_this_month >= monthly_limit:
        messages.warning(
            request, 
            f"You've reached your monthly limit of {monthly_limit} AI Mock Interviews. "
            "Get 'Elevo Pro' through your institution for unlimited interviews!"
        )
        return render(request, 'aptitude/limit_reached.html', {
            'limit': monthly_limit,
            'feature': 'Mock Interviews (Monthly)',
            'is_individual': not getattr(request, 'is_premium', False)
        })

    insights = None
    pack_options = list(INTERVIEW_PACKS.values())
    selected_pack = "default"
    if request.method == "POST":
        action = request.POST.get("action", "start")
        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        form = InterviewSetupForm(request.POST, request.FILES)
        resume = request.FILES.get("resume_file")
        job_description_text = _strip(request.POST.get("job_description"))
        use_profile_resume = request.POST.get("use_profile_resume") == "true"
        
        # If user chose to use profile resume and didn't upload a new one
        if use_profile_resume and not resume and request.user.profile.resume:
            resume = request.user.profile.resume

        parsed = None
        requested_track = _strip(request.POST.get("interview_track")) or "technical"
        requested_pack = _strip(request.POST.get("interview_pack")) or "default"
        if requested_pack not in INTERVIEW_PACKS:
            requested_pack = "default"
        selected_pack = requested_pack
        if requested_track not in INTERVIEW_TRACKS:
            requested_track = "technical"

        if resume:
            try:
                # Handle both uploaded files and FileField objects
                if hasattr(resume, 'open'):
                    resume.open()
                
                text = _resume_text(resume, resume.name)
                role_hint = _strip(request.POST.get("job_role"))
                resume_profile = _extract_resume_profile(text, role_hint=role_hint, track=requested_track)
                merged_role = _strip(resume_profile.get("preferred_role")) or role_hint
                merged_skills = _merge_unique(
                    _safe_list(resume_profile.get("skills")),
                    _safe_list(resume_profile.get("tools_tech")),
                    limit=12,
                )

                parsed = {
                    "job_role": merged_role,
                    "skills": merged_skills,
                    "resume_text_preview": text[:5000],
                    "resume_profile": resume_profile,
                    "interview_track": requested_track,
                    "interview_pack": requested_pack,
                    "job_description": job_description_text,
                }
                insights = _compute_resume_ats_insights(
                    resume_profile,
                    role_hint=role_hint,
                    skills_hint=_strip(request.POST.get("key_skills")),
                    track=requested_track,
                    resume_text=text,
                )
                jd_fit = _compute_jd_fit_insights(
                    resume_profile,
                    job_description_text,
                    role_hint=role_hint,
                    track=requested_track,
                )
                insights["detected_role"] = merged_role or ""
                insights["detected_skills"] = merged_skills[:12]
                insights["text_length"] = len(text)
                insights["role_confidence"] = resume_profile.get("role_confidence", 0)
                insights["skills_confidence"] = resume_profile.get("skills_confidence", 0)
                insights["jd_fit"] = jd_fit
                parsed["jd_fit"] = jd_fit

                post = request.POST.copy()
                if not post.get("job_role") and merged_role:
                    post["job_role"] = merged_role
                if not post.get("key_skills") and merged_skills:
                    post["key_skills"] = ", ".join(merged_skills[:12])
                if job_description_text:
                    post["job_description"] = job_description_text
                post["interview_track"] = requested_track
                post["interview_pack"] = requested_pack
                form = InterviewSetupForm(post, request.FILES)
                request.session["mock_resume_context"] = parsed
            except Exception as exc:
                if action == "analyze" and is_ajax:
                    return JsonResponse({"success": False, "error": f"Resume parse failed: {exc}"}, status=400)
                messages.warning(request, f"Resume parse failed: {exc}")

        if action == "analyze":
            if not resume:
                if is_ajax:
                    return JsonResponse({"success": False, "error": "Upload a resume first."}, status=400)
                messages.warning(request, "Upload a resume first.")
            elif insights:
                if is_ajax:
                    insights_html = render_to_string(
                        "mock_interview/partials/resume_insights_card.html",
                        {"resume_insights": insights},
                        request=request,
                    )
                    return JsonResponse(
                        {
                            "success": True,
                            "message": "Resume analyzed.",
                            "resume_insights_html": insights_html,
                            "detected_role": insights.get("detected_role", ""),
                            "detected_skills": ", ".join(insights.get("detected_skills", [])),
                            "role_confidence": insights.get("role_confidence", 0),
                            "skills_confidence": insights.get("skills_confidence", 0),
                            "jd_fit": insights.get("jd_fit"),
                        }
                    )
                messages.success(request, "Resume analyzed.")
            elif is_ajax:
                return JsonResponse({"success": False, "error": "Could not extract insights from this resume."}, status=400)
            return render(
                request,
                "mock_interview/interview_setup.html",
                {
                    "form": form,
                    "resume_insights": insights,
                    "ai_available": AI.enabled,
                    "pack_options": pack_options,
                    "selected_pack": selected_pack,
                },
            )

        if form.is_valid():
            track = form.cleaned_data.get("interview_track") or "technical"
            if track not in INTERVIEW_TRACKS:
                track = "technical"
            session = form.save(commit=False)
            session.user = request.user
            session.status = "STARTED"
            session.start_time = timezone.now()
            data = parsed or request.session.get("mock_resume_context")
            if not data or not _strip(data.get("resume_text_preview")):
                messages.error(request, "Resume is required. Upload and analyze your resume before starting interview.")
                return render(
                    request,
                    "mock_interview/interview_setup.html",
                    {
                        "form": form,
                        "resume_insights": insights,
                        "ai_available": AI.enabled,
                        "pack_options": pack_options,
                        "selected_pack": selected_pack,
                    },
                )

            session.parsed_resume_data = {
                "job_role": data.get("job_role", ""),
                "skills": data.get("skills", []),
                "resume_profile": data.get("resume_profile", {}),
                "interview_track": track,
                "interview_pack": data.get("interview_pack") or requested_pack,
                "job_description": data.get("job_description") or job_description_text,
                "jd_fit": data.get("jd_fit"),
            }
            session.extracted_resume_text = data.get("resume_text_preview", "")
            ats_score = (insights or {}).get("ats_score")
            initial_band, confidence = _assign_starting_band(request.user, track, ats_score=ats_score)
            session.selected_pack = data.get("interview_pack") or requested_pack
            session.starting_band = initial_band
            session.current_band = initial_band
            session.performance_band = initial_band
            session.band_confidence = confidence
            session.feedback_status = "pending"

            interview_plan = _build_interview_plan(session)
            if not isinstance(session.parsed_resume_data, dict):
                session.parsed_resume_data = {}
            session.parsed_resume_data["interview_plan"] = interview_plan
            session.parsed_resume_data["adaptive"] = {
                "starting_band": initial_band,
                "current_band": initial_band,
                "band_confidence": confidence,
            }
            session.parsed_resume_data["pack"] = INTERVIEW_PACKS.get(session.selected_pack, INTERVIEW_PACKS["default"])
            if resume:
                ext = resume.name.lower().rsplit(".", 1)[-1] if "." in resume.name else ""
                if ext in {"pdf", "docx"}:
                    resume.seek(0)
                    session.resume_file = resume
            session.save()
            request.session.pop("mock_resume_context", None)
            messages.success(request, "Interview session created.")
            return redirect("mock_interview:main_interview", session_id=session.id)
    else:
        form = InterviewSetupForm()

    return render(
        request,
        "mock_interview/interview_setup.html",
        {
            "form": form,
            "resume_insights": insights,
            "ai_available": AI.enabled,
            "pack_options": pack_options,
            "selected_pack": selected_pack,
        },
    )


@login_required
@user_passes_test(is_student, login_url="/login/")
def main_interview(request, session_id):
    session = get_object_or_404(MockInterviewSession, id=session_id, user=request.user)
    track = _session_track(session)
    if request.method == "POST":
        turns = session.turns.all().order_by("turn_number")
        if not turns.exists():
            question = _opening_message(session)
            meta = {"provider": "system", "model": "opening-script", "stage": "introduction"}
            InterviewTurn.objects.create(
                session=session,
                turn_number=1,
                ai_question=question,
                ai_internal_analysis=json.dumps({"type": "start", **meta}),
                difficulty_level=_difficulty_for_question(session, "introduction"),
                skill_tags=_next_focus_skills(session),
                band_after_turn=session.current_band or session.performance_band or "standard",
            )
            return JsonResponse({"success": True, "ai_response_text": question, "ai_audio_url": None, "current_question": 1})
        last = turns.last()
        return JsonResponse({"success": True, "ai_response_text": last.ai_question, "ai_audio_url": None, "current_question": last.turn_number})

    if session.status in {"COMPLETED", "REVIEWED", "FEEDBACK_PROCESSING"}:
        return redirect("mock_interview:review_interview", session_id=session.id)

    history = []
    turns = session.turns.all().order_by("turn_number")
    for t in turns:
        if t.ai_question:
            history.append({"role": "model", "parts": [{"text": t.ai_question}]})
        if t.user_answer:
            history.append({"role": "user", "parts": [{"text": t.user_answer}]})
    context = {
        "session_id": session.id,
        "job_role": session.job_role,
        "key_skills": session.key_skills,
        "interview_track": track,
        "performance_band": session.current_band or session.performance_band or "standard",
        "selected_pack": session.selected_pack or "default",
        "interview_plan_json": json.dumps((session.parsed_resume_data or {}).get("interview_plan", _build_interview_plan(session))),
        "initial_chat_history_json": json.dumps(history),
        "interview_progress": json.dumps(
            {
                "total_questions": turns.count(),
                "in_progress": turns.exists(),
                "current_question": max(1, turns.count()),
                "max_questions": MAX_INTERVIEW_QUESTIONS,
                "stage": _question_stage(max(1, turns.count()), track=track),
                "performance_band": session.current_band or session.performance_band or "standard",
            }
        ),
        "ai_initialized": AI.enabled,
        "edge_tts_available": False,
    }
    return render(request, "mock_interview/main_interview.html", context)


@login_required
@user_passes_test(is_student, login_url="/login/")
def interact_with_ai(request, interview_id):
    return ai_interaction_api(request, interview_id)


@login_required
@user_passes_test(is_student, login_url="/login/")
def ai_interaction_api(request, session_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required."}, status=405)
    session = get_object_or_404(MockInterviewSession, id=session_id, user=request.user)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    interaction_id = _strip(payload.get("interaction_id"))
    user_response = _strip(payload.get("user_response"))
    time_remaining = payload.get("time_remaining")
    if not user_response:
        return JsonResponse({"error": "No user response provided."}, status=400)
    if interaction_id:
        idem_key = f"mock_interview:idem:{session.id}:{interaction_id}"
        cached = cache.get(idem_key)
        if cached:
            return JsonResponse(cached)

    turns = session.turns.all().order_by("turn_number")
    if not turns.exists():
        return JsonResponse({"error": "Interview has not started."}, status=400)

    with transaction.atomic():
        last_turn = session.turns.select_for_update().order_by("-turn_number").first()
        if not last_turn:
            return JsonResponse({"error": "Interview has not started."}, status=400)
        if not _strip(last_turn.user_answer):
            turn_eval = _score_turn(session, user_response)
            last_turn.user_answer = user_response
            last_turn.skill_tags = turn_eval["skill_tags"]
            last_turn.turn_score = turn_eval["turn_score"]
            last_turn.communication_score = turn_eval["communication_score"]
            last_turn.technical_score = turn_eval["technical_score"]
            last_turn.confidence_score = turn_eval["confidence_score"]
            last_turn.band_after_turn = session.current_band or session.performance_band or "standard"
            last_turn.save(
                update_fields=[
                    "user_answer",
                    "skill_tags",
                    "turn_score",
                    "communication_score",
                    "technical_score",
                    "confidence_score",
                    "band_after_turn",
                ]
            )

    refreshed = session.turns.all().order_by("turn_number")
    track = _session_track(session)
    answered_count = refreshed.filter(user_answer__isnull=False).exclude(user_answer="").count()
    duration_minutes = (timezone.now() - session.start_time).total_seconds() / 60 if session.start_time else 0
    finish_requested = payload.get("request_type") == "finish"
    quality = _score_turn(session, user_response)
    recent_scores = [
        float(v)
        for v in refreshed.exclude(turn_score__isnull=True).order_by("turn_number").values_list("turn_score", flat=True)
    ]
    prev_band = session.current_band or session.performance_band or "standard"
    new_band = _band_transition(prev_band, recent_scores)
    session.current_band = new_band
    session.performance_band = new_band
    session.band_confidence = _clamp_score((session.band_confidence or 50) + (4 if new_band == prev_band else 8))
    _update_session_skill_memory(session)
    session.save(update_fields=["current_band", "performance_band", "band_confidence", "weak_skill_tags", "strong_skill_tags", "updated_at"])
    if refreshed.exists():
        latest_answered = refreshed.filter(user_answer__isnull=False).exclude(user_answer="").order_by("-turn_number").first()
        if latest_answered and latest_answered.band_after_turn != new_band:
            latest_answered.band_after_turn = new_band
            latest_answered.save(update_fields=["band_after_turn"])
    completion_gate_met = answered_count >= MIN_INTERVIEW_QUESTIONS

    if (finish_requested and completion_gate_met) or answered_count >= MAX_INTERVIEW_QUESTIONS:
        closing_text, meta = _closing(session, answered_count)
        InterviewTurn.objects.create(
            session=session,
            turn_number=refreshed.count() + 1,
            ai_question=closing_text,
            ai_internal_analysis=json.dumps({"type": "closing", **meta}),
            difficulty_level=_difficulty_for_question(session, "final-evaluation"),
            skill_tags=_next_focus_skills(session),
            band_after_turn=session.current_band or session.performance_band or "standard",
        )
        session.status = "FEEDBACK_PROCESSING"
        session.feedback_status = "processing"
        session.feedback_error = ""
        session.end_time = timezone.now()
        session.save(update_fields=["status", "feedback_status", "feedback_error", "end_time", "updated_at"])
        _queue_feedback_generation(session)
        response_data = {
            "success": True,
            "ai_response_text": closing_text,
            "ai_audio_url": None,
            "interview_complete": True,
            "feedback_status": session.feedback_status,
            "interview_progress": {
                "current_question": answered_count,
                "duration_minutes": round(duration_minutes, 1),
                "questions_remaining": 0,
                "stage": "completed",
                "performance_band": session.current_band or session.performance_band or "standard",
                "next_focus_skills": _next_focus_skills(session),
            },
            "quality_snapshot": quality,
            "adaptive": {
                "performance_band": session.current_band or session.performance_band or "standard",
                "weak_skill_tags": session.weak_skill_tags or [],
                "strong_skill_tags": session.strong_skill_tags or [],
            },
            "debug_info": {"provider": meta.get("provider"), "model": meta.get("model"), "tts_method": "disabled"},
        }
        if interaction_id:
            cache.set(idem_key, response_data, timeout=600)
        return JsonResponse(
            {
                **response_data,
            }
        )

    if finish_requested and not completion_gate_met:
        return JsonResponse(
            {
                "error": f"Complete at least {MIN_INTERVIEW_QUESTIONS} answers before finishing.",
                "interview_progress": {
                    "current_question": answered_count,
                    "duration_minutes": round(duration_minutes, 1),
                    "questions_remaining": max(0, MIN_INTERVIEW_QUESTIONS - answered_count),
                    "stage": _question_stage(answered_count + 1, track=track),
                },
            },
            status=400,
        )

    question, meta = _next_question(session, refreshed, user_response, time_remaining=time_remaining)
    new_turn = InterviewTurn.objects.create(
        session=session,
        turn_number=refreshed.count() + 1,
        ai_question=question,
        ai_internal_analysis=json.dumps({"type": "followup", **meta}),
        difficulty_level=meta.get("difficulty_level", _difficulty_for_question(session, meta.get("stage"))),
        skill_tags=meta.get("focus_skills") or _next_focus_skills(session),
        band_after_turn=session.current_band or session.performance_band or "standard",
    )
    response_data = {
        "success": True,
        "ai_response_text": question,
        "ai_audio_url": None,
        "interview_complete": False,
        "feedback_status": session.feedback_status or "pending",
        "interview_progress": {
            "current_question": answered_count + 1,
            "duration_minutes": round(duration_minutes, 1),
            "questions_remaining": max(0, MAX_INTERVIEW_QUESTIONS - answered_count),
            "stage": meta.get("stage", _question_stage(answered_count + 1, track=track)),
            "performance_band": session.current_band or session.performance_band or "standard",
            "next_focus_skills": _next_focus_skills(session),
        },
        "quality_snapshot": quality,
        "adaptive": {
            "performance_band": session.current_band or session.performance_band or "standard",
            "difficulty_level": new_turn.difficulty_level,
            "skill_tags": new_turn.skill_tags or [],
            "turn_score": float(quality["turn_score"]),
            "communication_score": float(quality["communication_score"]),
            "technical_score": float(quality["technical_score"]),
            "confidence_score": float(quality["confidence_score"]),
            "weak_skill_tags": session.weak_skill_tags or [],
            "strong_skill_tags": session.strong_skill_tags or [],
        },
        "debug_info": {"provider": meta.get("provider"), "model": meta.get("model"), "tts_method": "disabled"},
    }
    if interaction_id:
        cache.set(idem_key, response_data, timeout=600)
    return JsonResponse(response_data)


@login_required
@user_passes_test(is_student, login_url="/login/")
def my_mock_interviews(request):
    sessions = MockInterviewSession.objects.filter(user=request.user).order_by("-created_at")
    for item in sessions:
        end_time = item.end_time or (item.turns.order_by("-timestamp").first().timestamp if item.turns.exists() else None)
        if item.start_time and end_time:
            mins = (end_time - item.start_time).total_seconds() / 60
            item.duration_display = f"{int(mins)} min" if mins >= 1 else f"{int(mins * 60)} sec"
        else:
            item.duration_display = "N/A"
        item.total_questions = item.turns.count()
        feedback = _parse_json(item.overall_feedback or "") or {}
        item.feedback_summary = {
            "confidence": feedback.get("confidence_level", "Pending"),
            "communication": feedback.get("communication_score"),
            "top_strength": (feedback.get("strengths") or [None])[0],
            "performance_band": item.current_band or item.performance_band or "standard",
            "feedback_status": item.feedback_status or "pending",
        }
    return render(request, "mock_interview/my_mock_interviews.html", {"sessions": sessions})


@login_required
@user_passes_test(is_student, login_url="/login/")
def review_interview(request, session_id):
    session = get_object_or_404(MockInterviewSession, id=session_id, user=request.user)
    turns = session.turns.all().order_by("turn_number")
    if not turns.exists():
        messages.info(request, "Interview not started yet.")
        return redirect("mock_interview:main_interview", session_id=session.id)

    if session.status == "FEEDBACK_PROCESSING" and (session.feedback_status or "pending") == "processing":
        messages.info(request, "Your feedback is still processing. Refresh in a moment.")
    if session.status == "STARTED" and turns.filter(user_answer__isnull=False).exclude(user_answer="").count() >= 3:
        session.status = "COMPLETED"
        if not session.end_time:
            session.end_time = timezone.now()
        if not _strip(session.overall_feedback):
            feedback = _generate_feedback(session)
            session.overall_feedback = json.dumps(feedback)
            session.score = feedback.get("overall_score")
            session.feedback_status = "ready"
        session.save()

    feedback = _coerce_feedback(_parse_json(session.overall_feedback or ""), session)
    if not _strip(session.overall_feedback) and (session.feedback_status or "pending") != "processing":
        session.overall_feedback = json.dumps(feedback)
        session.score = feedback.get("overall_score")
        session.feedback_status = "ready"
        session.save(update_fields=["overall_feedback", "score", "feedback_status", "updated_at"])

    duration_minutes = None
    if session.start_time and session.end_time:
        duration_minutes = (session.end_time - session.start_time).total_seconds() / 60
    total_words = sum(len((t.user_answer or "").split()) for t in turns)
    answered = turns.filter(user_answer__isnull=False).exclude(user_answer="").count()
    avg_quality = 0
    quality_points = []
    stage_counts = {
        "introduction": 0,
        "technical-core": 0,
        "technical-depth": 0,
        "problem-solving": 0,
        "hr-core": 0,
        "behavioral": 0,
        "situational-hr": 0,
        "final-evaluation": 0,
    }
    for t in turns:
        if t.user_answer:
            quality_points.append(_response_quality(t.user_answer)["quality_score"])
        meta = _parse_json(t.ai_internal_analysis or "") or {}
        stage = meta.get("stage")
        if stage in stage_counts:
            stage_counts[stage] += 1
    if quality_points:
        avg_quality = round(sum(quality_points) / len(quality_points), 1)
    replay_steps = []
    weak_skill_trend = []
    band_transitions = []
    last_band = None
    cumulative_weak = 0
    for t in turns:
        if not t.ai_question:
            continue
        score_val = float(t.turn_score or 0)
        tags = [str(x).strip() for x in (t.skill_tags or []) if str(x).strip()]
        weak_tags = tags if score_val <= 50 else []
        if weak_tags:
            cumulative_weak += len(weak_tags)
        step = {
            "turn": t.turn_number,
            "question": t.ai_question or "",
            "answer": t.user_answer or "",
            "band": t.band_after_turn or session.current_band or "standard",
            "difficulty": t.difficulty_level or "medium",
            "score": round(score_val, 1),
            "skill_tags": tags[:6],
            "weak_tags": weak_tags[:6],
        }
        replay_steps.append(step)
        weak_skill_trend.append(
            {
                "turn": t.turn_number,
                "weak_count": len(weak_tags),
                "cumulative_weak": cumulative_weak,
            }
        )
        if last_band is not None and step["band"] != last_band:
            band_transitions.append(
                {
                    "turn": t.turn_number,
                    "from": last_band,
                    "to": step["band"],
                }
            )
        last_band = step["band"]
    context = {
        "session": session,
        "turns": turns,
        "transcript": turns,
        "ai_feedback": feedback,
        "score_deg": feedback.get("overall_score", 70) * 3.6,
        "adaptive_timeline": [
            {
                "turn": t.turn_number,
                "band": t.band_after_turn or session.current_band or "standard",
                "difficulty": t.difficulty_level or "medium",
                "score": float(t.turn_score or 0),
                "skills": t.skill_tags or [],
            }
            for t in turns
            if t.ai_question
        ],
        "next_action_plan": [
            f"Focus on weak area: {tag}" for tag in (session.weak_skill_tags or [])[:3]
        ] or ["Continue structured mock practice and quantify impact in answers."],
        "replay_steps": replay_steps,
        "weak_skill_trend": weak_skill_trend,
        "band_transitions": band_transitions,
        "interview_metrics": {
            "duration_minutes": round(duration_minutes, 1) if duration_minutes is not None else None,
            "total_questions": turns.count(),
            "total_words": total_words,
            "avg_response_length": round(total_words / max(answered, 1), 1),
            "confidence_score": feedback.get("communication_score", 0),
            "engagement_score": min(100, 40 + answered * 8),
            "avg_answer_quality": avg_quality,
            "stage_distribution": stage_counts,
            "performance_band": session.current_band or session.performance_band or "standard",
            "weak_skill_tags": session.weak_skill_tags or [],
            "strong_skill_tags": session.strong_skill_tags or [],
            "feedback_status": session.feedback_status or "pending",
            "tts_enhanced": False,
        },
    }
    return render(request, "mock_interview/review_interview.html", context)


@login_required
@user_passes_test(is_student, login_url="/login/")
def delete_session(request, session_id):
    session = get_object_or_404(MockInterviewSession, id=session_id, user=request.user)
    role = session.job_role or "Unknown role"
    session.delete()
    messages.success(request, f"Deleted interview session for {role}.")
    return redirect("mock_interview:my_mock_interviews")


@login_required
@user_passes_test(is_student, login_url="/login/")
def clear_all_sessions(request):
    if request.method == "POST":
        count = MockInterviewSession.objects.filter(user=request.user).count()
        MockInterviewSession.objects.filter(user=request.user).delete()
        messages.success(request, f"Deleted {count} interview sessions.")
    else:
        messages.warning(request, "Invalid request method.")
    return redirect("mock_interview:my_mock_interviews")


@login_required
@user_passes_test(is_student, login_url="/login/")
def get_interview_hints_api(request, session_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required."}, status=405)
    session = get_object_or_404(MockInterviewSession, id=session_id, user=request.user)
    track = _session_track(session)
    stage = _question_stage(max(1, session.turns.count()), track=track)
    cache_key = f"mock_interview:hints:{session.id}:{stage}:{session.current_band or session.performance_band}"
    cached_hints = cache.get(cache_key)
    if cached_hints:
        return JsonResponse(cached_hints)
    profile = {}
    jd_fit = {}
    if isinstance(session.parsed_resume_data, dict):
        profile = session.parsed_resume_data.get("resume_profile", {}) or {}
        jd_fit = session.parsed_resume_data.get("jd_fit", {}) or {}
    latest = session.turns.order_by("-turn_number").first()
    prompt = (
        "Provide exactly 3 interview hints as JSON array of strings.\n"
        f"Role: {session.job_role}\nTrack: {track}\nSkills: {session.key_skills}\n"
        f"Resume projects: {_safe_list(profile.get('projects'))[:3]}\n"
        f"JD missing skills: {_safe_list(jd_fit.get('missing_skills'))[:5]}\n"
        f"Current question: {(latest.ai_question if latest else '')}"
    )
    hints = None
    provider = "fallback"
    model = "static"
    try:
        text, provider, model = AI.text(prompt, temperature=0.4, max_tokens=180, prefer_json=True)
        parsed = _parse_json(text)
        if isinstance(parsed, list):
            hints = [str(x) for x in parsed if str(x).strip()][:3]
    except Exception:
        pass
    if not hints:
        hints = [
            "Answer directly in the first line.",
            "Use one concrete project example.",
            "End with a measurable result.",
        ]
    response_data = {
        "success": True,
        "hints": hints,
        "session_id": session.id,
            "context": {
                "stage": stage,
                "provider": provider,
                "model": model,
                "track": track,
                "performance_band": session.current_band or session.performance_band or "standard",
                "next_focus_skills": _next_focus_skills(session),
                "jd_fit_score": jd_fit.get("fit_score"),
            },
        }
    cache.set(cache_key, response_data, timeout=300)
    return JsonResponse(response_data)


@login_required
@user_passes_test(is_student, login_url="/login/")
def practice_question_api(request, session_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required."}, status=405)
    session = get_object_or_404(MockInterviewSession, id=session_id, user=request.user)
    track = _session_track(session)
    profile = {}
    jd_fit = {}
    if isinstance(session.parsed_resume_data, dict):
        profile = session.parsed_resume_data.get("resume_profile", {}) or {}
        jd_fit = session.parsed_resume_data.get("jd_fit", {}) or {}
    payload = json.loads(request.body or "{}")
    focus = payload.get("focus_area") or session.key_skills or session.job_role or "general"
    stage = _question_stage(max(1, session.turns.count()), track=track)
    cache_key = f"mock_interview:practice:{session.id}:{stage}:{focus}:{session.current_band or session.performance_band}"
    cached_questions = cache.get(cache_key)
    if cached_questions:
        return JsonResponse(cached_questions)
    prompt = (
        "Generate 4 practice interview questions and return JSON {\"questions\":[...]}.\n"
        f"Role: {session.job_role}\nTrack: {track}\nFocus: {focus}\n"
        f"Resume anchors: projects={_safe_list(profile.get('projects'))[:3]}, experience={_safe_list(profile.get('experience_highlights'))[:3]}\n"
        f"JD missing skills to target: {_safe_list(jd_fit.get('missing_skills'))[:6]}\n"
        "Technical track: only technical questions.\n"
        "HR track: only HR/behavioral/situational questions."
    )
    questions = None
    provider = "fallback"
    model = "static"
    try:
        text, provider, model = AI.text(prompt, temperature=0.6, max_tokens=260, prefer_json=True)
        parsed = _parse_json(text)
        if isinstance(parsed, dict) and isinstance(parsed.get("questions"), list):
            questions = [str(x) for x in parsed["questions"] if str(x).strip()][:4]
    except Exception:
        pass
    if not questions:
        if track == "technical":
            questions = [
                "From your resume, explain one technical project architecture and your decisions.",
                "How would you debug a failing pipeline or production bug in one of your projects?",
                "Which optimization did you implement and how did you measure improvement?",
                "What technical tradeoff did you make in your recent project and why?",
            ]
        else:
            questions = [
                "From your resume, share a time you handled a team challenge effectively.",
                "How do you prioritize tasks when multiple stakeholders request updates?",
                "Describe a situation where you received feedback and improved your approach.",
                "How would you handle conflict with a teammate while preserving collaboration?",
            ]
    typed = [
        {"type": "technical", "question": questions[0]},
        {"type": "problem-solving", "question": questions[1]},
        {"type": "quality", "question": questions[2]},
        {"type": "ownership", "question": questions[3]},
    ]
    response_data = {
        "success": True,
        "session_id": session.id,
        "job_role": session.job_role,
        "questions": questions,
        "question_bank": typed,
        "context": {
            "provider": provider,
            "model": model,
            "focus": focus,
            "track": track,
            "stage": stage,
            "performance_band": session.current_band or session.performance_band or "standard",
            "next_focus_skills": _next_focus_skills(session),
            "jd_fit_score": jd_fit.get("fit_score"),
        },
    }
    cache.set(cache_key, response_data, timeout=300)
    return JsonResponse(response_data)


def ai_health_check(request):
    return JsonResponse(
        {
            "status": "ok",
            "platform": "elevo-interview-studio-v2",
            "timestamp": timezone.now().isoformat(),
            "ai": {
                "has_provider": AI.enabled,
                "gemini_configured": bool(AI.gemini_key),
                "openai_configured": bool(AI.openai_key),
                "fallback_order": ["gemini", "openai"],
                "gemini_models": AI.gemini_models,
                "openai_models": AI.openai_models,
            },
            "interview": {"max_questions": MAX_INTERVIEW_QUESTIONS, "min_questions": MIN_INTERVIEW_QUESTIONS},
            "tracks": ["technical", "hr"],
            "adaptive_bands": BAND_ORDER,
            "packs": list(INTERVIEW_PACKS.keys()),
        }
    )


