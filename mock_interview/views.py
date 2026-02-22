import json
import logging
import os
import random
import re
import tempfile
from difflib import SequenceMatcher

import docx2txt
import openai
import pdfplumber
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from google import genai
from google.genai import types

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

    def text(self, prompt, temperature=0.7, max_tokens=300, prefer_json=False):
        errors = []
        if self.gemini_key:
            try:
                return self._call_gemini(prompt, temperature, max_tokens, prefer_json=prefer_json)
            except Exception as exc:
                errors.append(str(exc))
        if self.openai_key:
            try:
                return self._call_openai(prompt, temperature, max_tokens)
            except Exception as exc:
                errors.append(str(exc))
        raise RuntimeError("; ".join(errors) if errors else "No AI provider configured")


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
        }

    prompt = (
        "Extract structured candidate profile from this resume.\n"
        "Return ONLY JSON with keys:\n"
        "summary, candidate_name, preferred_role, skills, projects, experience_highlights, education_highlights, tools_tech, hr_signals.\n"
        "Rules:\n"
        "- projects: list of short lines with project and impact.\n"
        "- experience_highlights: list of measurable achievements.\n"
        "- hr_signals: communication/team/leadership indicators from resume.\n"
        f"Role hint: {role_hint}\n"
        f"Interview track: {track}\n"
        f"Resume:\n{resume_text[:18000]}"
    )
    try:
        text, _, _ = AI.text(prompt, temperature=0.2, max_tokens=900, prefer_json=True)
        data = _parse_json(text) or {}
    except Exception:
        data = {}

    # heuristic fallback/augmentation
    lowered = resume_text.lower()
    heuristic_skills = [topic for topic in TECHNICAL_TOPICS if topic in lowered]
    heuristic_tools = [item for item in ["python", "sql", "pandas", "numpy", "django", "react", "aws", "docker", "excel", "tableau", "power bi"] if item in lowered]
    lines = [ln.strip("-• ").strip() for ln in resume_text.splitlines() if ln.strip()]
    project_lines = [ln for ln in lines if "project" in ln.lower()][:6]
    exp_lines = [ln for ln in lines if any(k in ln.lower() for k in ["intern", "worked", "developed", "built", "implemented", "led"])][:8]
    edu_lines = [ln for ln in lines if any(k in ln.lower() for k in ["b.tech", "btech", "mca", "bca", "degree", "university", "college"])][:5]
    hr_lines = [ln for ln in lines if any(k in ln.lower() for k in ["team", "communication", "lead", "collaborat", "responsib", "managed"])][:6]

    profile = {
        "summary": _strip(data.get("summary")) or _strip(" ".join(lines[:3]))[:320],
        "candidate_name": _strip(data.get("candidate_name")),
        "preferred_role": _strip(data.get("preferred_role")) or role_hint,
        "skills": _safe_list(data.get("skills")) or heuristic_skills[:10],
        "projects": _safe_list(data.get("projects")) or project_lines,
        "experience_highlights": _safe_list(data.get("experience_highlights")) or exp_lines,
        "education_highlights": _safe_list(data.get("education_highlights")) or edu_lines,
        "tools_tech": _safe_list(data.get("tools_tech")) or heuristic_tools[:12],
        "hr_signals": _safe_list(data.get("hr_signals")) or hr_lines,
    }
    return profile


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
    action_words = ["built", "designed", "implemented", "optimized", "led", "improved", "delivered"]
    metric_markers = ["%", "x", "ms", "days", "weeks", "users", "latency", "throughput", "revenue"]
    has_action = any(word in text.lower() for word in action_words)
    has_metric = any(marker in text.lower() for marker in metric_markers)
    score = 0
    score += 35 if len(words) >= 40 else 20 if len(words) >= 20 else 8
    score += 35 if has_action else 10
    score += 30 if has_metric else 8
    return {
        "word_count": len(words),
        "has_action_language": has_action,
        "has_metrics": has_metric,
        "quality_score": min(100, score),
    }


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

    skills = [s.strip() for s in (session.key_skills or "").split(",") if s.strip()]
    resume_skills = _safe_list(profile.get("skills")) + _safe_list(profile.get("tools_tech"))
    top_skills = (skills or resume_skills or (TECHNICAL_TOPICS if track == "technical" else HR_TOPICS))[:6]
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
        "resume_anchor": {
            "candidate_name": _strip(profile.get("candidate_name")),
            "summary": _strip(profile.get("summary")),
            "projects": _safe_list(profile.get("projects"))[:5],
            "experience_highlights": _safe_list(profile.get("experience_highlights"))[:5],
            "hr_signals": _safe_list(profile.get("hr_signals"))[:5],
        },
    }


def _build_question_prompt(session, turns, user_response):
    next_q = turns.count() + 1
    parsed = session.parsed_resume_data if isinstance(session.parsed_resume_data, dict) else {}
    track = _strip(parsed.get("interview_track")) or "technical"
    if track not in INTERVIEW_TRACKS:
        track = "technical"
    stage = _question_stage(next_q, track=track)
    plan = (session.parsed_resume_data or {}).get("interview_plan", {})
    focus_skills = ", ".join(plan.get("skills_focus", [])) if isinstance(plan, dict) else ""
    resume_anchor = plan.get("resume_anchor", {}) if isinstance(plan, dict) else {}
    resume_projects = "; ".join(_safe_list(resume_anchor.get("projects"))[:3])
    resume_exp = "; ".join(_safe_list(resume_anchor.get("experience_highlights"))[:3])
    resume_hr = "; ".join(_safe_list(resume_anchor.get("hr_signals"))[:3])
    candidate_name = _strip(resume_anchor.get("candidate_name"))
    question_style = "fundamental skill-based technical question" if (track == "technical" and next_q > 1 and next_q % 2 == 0) else "resume-anchored question"

    history = []
    recent_turns = list(turns.order_by("-turn_number")[:6])[::-1]
    for t in recent_turns:
        if t.ai_question:
            history.append(f"Interviewer: {t.ai_question}")
        if t.user_answer:
            history.append(f"Candidate: {t.user_answer}")
    return (
        "You are Elevo, a warm and professional interviewer speaking simple, clear English.\n"
        f"Role: {session.job_role}\nTrack: {track}\nSkills: {session.key_skills}\n"
        f"Question number now: {next_q}/{MAX_INTERVIEW_QUESTIONS}\n"
        f"Current stage: {stage}\n"
        f"Question style target now: {question_style}\n"
        f"Candidate name from resume: {candidate_name or 'Candidate'}\n"
        f"Primary focus skills: {focus_skills or session.key_skills or 'general'}\n"
        f"Resume projects: {resume_projects or 'Not available'}\n"
        f"Resume experience highlights: {resume_exp or 'Not available'}\n"
        f"Resume HR signals: {resume_hr or 'Not available'}\n"
        f"Latest answer: {user_response or '(start)'}\n"
        f"History:\n{chr(10).join(history) if history else 'None'}\n"
        "Instructions:\n"
        "- Start with one short appreciation/acknowledgement sentence.\n"
        "- Then ask one non-repetitive, realistic next question.\n"
        "- Keep total response under 75 words.\n"
        "- Use easy, natural human wording. No robotic phrasing.\n"
        "- If candidate asks clarification, clarify briefly and continue.\n"
        "- Never use meta lines like 'when I asked' or 'as mentioned earlier'.\n"
        "- STRICT: Ask based on resume details only.\n"
        "- If track is technical and question_number > 1: ask only technical questions.\n"
        "- In technical mode, mix resume-based questions with core fundamentals from skills (e.g., Python list vs tuple, SQL joins, ML metrics).\n"
        "- If current question style target is fundamental, ask a direct technical concept question from candidate skills.\n"
        "- If track is hr and question_number > 1: ask only HR/behavioral/situational question.\n"
        "- Return plain text only."
    )


def _opening_message(session):
    parsed = session.parsed_resume_data if isinstance(session.parsed_resume_data, dict) else {}
    plan = parsed.get("interview_plan", {}) if isinstance(parsed.get("interview_plan"), dict) else {}
    anchor = plan.get("resume_anchor", {}) if isinstance(plan.get("resume_anchor"), dict) else {}
    role = session.job_role or "your target role"
    track = _strip(parsed.get("interview_track")) or "technical"
    candidate_name = _strip(anchor.get("candidate_name"))
    intro_name = f" {candidate_name}" if candidate_name else ""
    mode_label = "technical" if track == "technical" else "HR"
    return (
        f"Hi{intro_name}, I am Elevo. Nice to meet you. "
        f"We will run a {mode_label} mock interview for {role}, based on your resume. "
        "To begin, please introduce yourself and briefly summarize your recent resume highlights."
    )


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
        "You are Elevo, a natural human interviewer.\n"
        "Write one fresh follow-up response in simple English.\n"
        "Requirements:\n"
        "- Start with one short appreciation line.\n"
        "- Ask one NEW question based on the candidate's latest answer.\n"
        "- Do NOT repeat or paraphrase recent questions.\n"
        "- Focus on one concrete detail from the candidate answer.\n"
        "- Keep total 22-60 words and end with '?'\n"
        "- STRICT: use only resume-grounded context.\n"
        "- Technical track -> only technical question after intro.\n"
        "- HR track -> only HR/behavioral/situational question after intro.\n"
        f"Role: {session.job_role}\n"
        f"Track: {track}\n"
        f"Stage: {stage}\n"
        f"Resume projects: {resume_projects or 'Not available'}\n"
        f"Resume experience: {resume_exp or 'Not available'}\n"
        f"Resume HR signals: {resume_hr or 'Not available'}\n"
        f"Candidate latest answer: {user_response}\n"
        f"Recent questions to avoid:\n{recent}\n"
        "Return plain text only."
    )


def _fallback_followup_question(stage, user_response, turns, session):
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
            ],
            "problem-solving": [
                f"If {project_anchor} had 10x more data/users, what technical changes would you make first?",
                f"In {project_anchor}, how would you improve performance or reliability in the next iteration?",
                fundamentals_q,
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
        "Return ONLY valid JSON with keys: overall_score, communication_score, confidence_level, strengths, "
        "areas_for_improvement, technical_assessment, recommendations, encouragement_note.\n"
        f"Role: {session.job_role}\nSkills: {session.key_skills}\nTranscript:\n{chr(10).join(transcript)}"
    )
    try:
        text, provider, model = AI.text(prompt, temperature=0.35, max_tokens=800, prefer_json=True)
        logger.info("Feedback generated by %s/%s", provider, model)
        return _coerce_feedback(_parse_json(text), session)
    except Exception as exc:
        logger.warning("Feedback generation fallback: %s", exc)
        return _default_feedback(session)


def _next_question(session, turns, user_response):
    next_q = turns.count() + 1
    parsed = session.parsed_resume_data if isinstance(session.parsed_resume_data, dict) else {}
    track = _strip(parsed.get("interview_track")) or "technical"
    if track not in INTERVIEW_TRACKS:
        track = "technical"
    stage = _question_stage(next_q, track=track)
    recent_questions = [t.ai_question for t in turns.order_by("-turn_number")[:4] if t.ai_question]
    prompt = _build_question_prompt(session, turns, user_response)
    try:
        text, provider, model = AI.text(prompt, temperature=0.7, max_tokens=220)
        question = _strip(text)
        if question and not _is_incomplete_turn(question) and not _is_repetitive_question(question, turns):
            return question, {"provider": provider, "model": model, "stage": stage}

        # One repair pass if model returned truncated/weak output.
        try:
            repair_prompt = _repair_turn_prompt(session, stage, question or "", user_response)
            repaired_text, r_provider, r_model = AI.text(repair_prompt, temperature=0.55, max_tokens=220)
            repaired = _strip(repaired_text)
            if repaired and not _is_incomplete_turn(repaired) and not _is_repetitive_question(repaired, turns):
                return repaired, {"provider": r_provider, "model": r_model, "stage": stage}
        except Exception as repair_exc:
            logger.warning("Question repair fallback: %s", repair_exc)

        # Second pass: generate a targeted fresh follow-up anchored in latest answer.
        try:
            followup_prompt = _targeted_followup_prompt(session, stage, user_response, recent_questions)
            follow_text, f_provider, f_model = AI.text(followup_prompt, temperature=0.65, max_tokens=220)
            followup = _strip(follow_text)
            if followup and not _is_incomplete_turn(followup) and not _is_repetitive_question(followup, turns):
                return followup, {"provider": f_provider, "model": f_model, "stage": stage}
        except Exception as followup_exc:
            logger.warning("Targeted follow-up fallback: %s", followup_exc)
    except Exception as exc:
        logger.warning("Question generation fallback: %s", exc)
    choice = _fallback_followup_question(stage, user_response, turns, session)
    return choice, {"provider": "fallback", "model": "static", "stage": stage}


def _closing(session, answered_count):
    prompt = (
        "Write a warm interview closing message in 3-4 sentences in simple English. Plain text only.\n"
        f"Role: {session.job_role}\nAnswered questions: {answered_count}"
    )
    try:
        text, provider, model = AI.text(prompt, temperature=0.6, max_tokens=180)
        if _strip(text):
            return _strip(text), {"provider": provider, "model": model}
    except Exception as exc:
        logger.warning("Closing generation fallback: %s", exc)
    return FALLBACK_CLOSING, {"provider": "fallback", "model": "static"}


@login_required
@user_passes_test(is_student, login_url="/login/")
def start_mock_interview(request):
    return redirect("mock_interview:interview_setup")


@login_required
@user_passes_test(is_student, login_url="/login/")
def interview_setup(request):
    insights = None
    if request.method == "POST":
        action = request.POST.get("action", "start")
        form = InterviewSetupForm(request.POST, request.FILES)
        resume = request.FILES.get("resume_file")
        parsed = None
        requested_track = _strip(request.POST.get("interview_track")) or "technical"
        if requested_track not in INTERVIEW_TRACKS:
            requested_track = "technical"

        if resume:
            try:
                text = _resume_text(resume, resume.name)
                lowered = text.lower()
                detected_skills = [s for s in ["python", "django", "react", "sql", "aws", "docker"] if s in lowered]
                detected_role = "Software Engineer" if any(k in lowered for k in ["python", "api", "backend", "frontend"]) else ""
                role_hint = _strip(request.POST.get("job_role")) or detected_role
                resume_profile = _extract_resume_profile(text, role_hint=role_hint, track=requested_track)
                merged_role = _strip(resume_profile.get("preferred_role")) or detected_role
                merged_skills = _safe_list(resume_profile.get("skills")) or detected_skills

                parsed = {
                    "job_role": merged_role,
                    "skills": merged_skills,
                    "resume_text_preview": text[:5000],
                    "resume_profile": resume_profile,
                    "interview_track": requested_track,
                }
                insights = _compute_resume_ats_insights(
                    resume_profile,
                    role_hint=role_hint,
                    skills_hint=_strip(request.POST.get("key_skills")),
                    track=requested_track,
                    resume_text=text,
                )
                insights["detected_role"] = merged_role or "Not detected"
                insights["detected_skills"] = merged_skills[:12]
                insights["text_length"] = len(text)

                post = request.POST.copy()
                if not post.get("job_role") and merged_role:
                    post["job_role"] = merged_role
                if not post.get("key_skills") and merged_skills:
                    post["key_skills"] = ", ".join(merged_skills[:12])
                post["interview_track"] = requested_track
                form = InterviewSetupForm(post, request.FILES)
                request.session["mock_resume_context"] = parsed
            except Exception as exc:
                messages.warning(request, f"Resume parse failed: {exc}")

        if action == "analyze":
            if not resume:
                messages.warning(request, "Upload a resume first.")
            elif insights:
                messages.success(request, "Resume analyzed.")
            return render(request, "mock_interview/interview_setup.html", {"form": form, "resume_insights": insights, "ai_available": AI.enabled})

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
                return render(request, "mock_interview/interview_setup.html", {"form": form, "resume_insights": insights, "ai_available": AI.enabled})

            session.parsed_resume_data = {
                "job_role": data.get("job_role", ""),
                "skills": data.get("skills", []),
                "resume_profile": data.get("resume_profile", {}),
                "interview_track": track,
            }
            session.extracted_resume_text = data.get("resume_text_preview", "")

            interview_plan = _build_interview_plan(session)
            if not isinstance(session.parsed_resume_data, dict):
                session.parsed_resume_data = {}
            session.parsed_resume_data["interview_plan"] = interview_plan
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

    return render(request, "mock_interview/interview_setup.html", {"form": form, "resume_insights": insights, "ai_available": AI.enabled})


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
            )
            return JsonResponse({"success": True, "ai_response_text": question, "ai_audio_url": None, "current_question": 1})
        last = turns.last()
        return JsonResponse({"success": True, "ai_response_text": last.ai_question, "ai_audio_url": None, "current_question": last.turn_number})

    if session.status in {"COMPLETED", "REVIEWED"}:
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
        "interview_plan_json": json.dumps((session.parsed_resume_data or {}).get("interview_plan", _build_interview_plan(session))),
        "initial_chat_history_json": json.dumps(history),
        "interview_progress": json.dumps(
            {
                "total_questions": turns.count(),
                "in_progress": turns.exists(),
                "current_question": max(1, turns.count()),
                "max_questions": MAX_INTERVIEW_QUESTIONS,
                "stage": _question_stage(max(1, turns.count()), track=track),
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

    user_response = _strip(payload.get("user_response"))
    if not user_response:
        return JsonResponse({"error": "No user response provided."}, status=400)

    turns = session.turns.all().order_by("turn_number")
    if not turns.exists():
        return JsonResponse({"error": "Interview has not started."}, status=400)

    last_turn = turns.last()
    if last_turn and not _strip(last_turn.user_answer):
        last_turn.user_answer = user_response
        last_turn.save(update_fields=["user_answer"])

    refreshed = session.turns.all().order_by("turn_number")
    track = _session_track(session)
    answered_count = refreshed.filter(user_answer__isnull=False).exclude(user_answer="").count()
    duration_minutes = (timezone.now() - session.start_time).total_seconds() / 60 if session.start_time else 0
    finish_requested = payload.get("request_type") == "finish"
    quality = _response_quality(user_response)
    completion_gate_met = answered_count >= MIN_INTERVIEW_QUESTIONS

    if (finish_requested and completion_gate_met) or answered_count >= MAX_INTERVIEW_QUESTIONS:
        closing_text, meta = _closing(session, answered_count)
        InterviewTurn.objects.create(
            session=session,
            turn_number=refreshed.count() + 1,
            ai_question=closing_text,
            ai_internal_analysis=json.dumps({"type": "closing", **meta}),
        )
        session.status = "COMPLETED"
        session.end_time = timezone.now()
        feedback = _generate_feedback(session)
        session.overall_feedback = json.dumps(feedback)
        session.score = feedback.get("overall_score")
        session.save(update_fields=["status", "end_time", "overall_feedback", "score", "updated_at"])
        return JsonResponse(
            {
                "success": True,
                "ai_response_text": closing_text,
                "ai_audio_url": None,
                "interview_complete": True,
                "interview_progress": {
                    "current_question": answered_count,
                    "duration_minutes": round(duration_minutes, 1),
                    "questions_remaining": 0,
                    "stage": "completed",
                },
                "quality_snapshot": quality,
                "debug_info": {"provider": meta.get("provider"), "model": meta.get("model"), "tts_method": "disabled"},
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

    question, meta = _next_question(session, refreshed, user_response)
    InterviewTurn.objects.create(
        session=session,
        turn_number=refreshed.count() + 1,
        ai_question=question,
        ai_internal_analysis=json.dumps({"type": "followup", **meta}),
    )
    return JsonResponse(
        {
            "success": True,
            "ai_response_text": question,
            "ai_audio_url": None,
            "interview_complete": False,
            "interview_progress": {
                "current_question": answered_count + 1,
                "duration_minutes": round(duration_minutes, 1),
                "questions_remaining": max(0, MAX_INTERVIEW_QUESTIONS - answered_count),
                "stage": meta.get("stage", _question_stage(answered_count + 1, track=track)),
            },
            "quality_snapshot": quality,
            "debug_info": {"provider": meta.get("provider"), "model": meta.get("model"), "tts_method": "disabled"},
        }
    )


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

    if session.status == "STARTED" and turns.filter(user_answer__isnull=False).exclude(user_answer="").count() >= 3:
        session.status = "COMPLETED"
        if not session.end_time:
            session.end_time = timezone.now()
        if not _strip(session.overall_feedback):
            feedback = _generate_feedback(session)
            session.overall_feedback = json.dumps(feedback)
            session.score = feedback.get("overall_score")
        session.save()

    feedback = _coerce_feedback(_parse_json(session.overall_feedback or ""), session)
    if not _strip(session.overall_feedback):
        session.overall_feedback = json.dumps(feedback)
        session.score = feedback.get("overall_score")
        session.save(update_fields=["overall_feedback", "score", "updated_at"])

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
    context = {
        "session": session,
        "turns": turns,
        "transcript": turns,
        "ai_feedback": feedback,
        "score_deg": feedback.get("overall_score", 70) * 3.6,
        "interview_metrics": {
            "duration_minutes": round(duration_minutes, 1) if duration_minutes is not None else None,
            "total_questions": turns.count(),
            "total_words": total_words,
            "avg_response_length": round(total_words / max(answered, 1), 1),
            "confidence_score": feedback.get("communication_score", 0),
            "engagement_score": min(100, 40 + answered * 8),
            "avg_answer_quality": avg_quality,
            "stage_distribution": stage_counts,
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
    profile = {}
    if isinstance(session.parsed_resume_data, dict):
        profile = session.parsed_resume_data.get("resume_profile", {}) or {}
    latest = session.turns.order_by("-turn_number").first()
    prompt = (
        "Provide exactly 3 interview hints as JSON array of strings.\n"
        f"Role: {session.job_role}\nTrack: {track}\nSkills: {session.key_skills}\n"
        f"Resume projects: {_safe_list(profile.get('projects'))[:3]}\n"
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
    return JsonResponse(
        {
            "success": True,
            "hints": hints,
            "session_id": session.id,
            "context": {
                "stage": _question_stage(max(1, session.turns.count()), track=track),
                "provider": provider,
                "model": model,
                "track": track,
            },
        }
    )


@login_required
@user_passes_test(is_student, login_url="/login/")
def practice_question_api(request, session_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required."}, status=405)
    session = get_object_or_404(MockInterviewSession, id=session_id, user=request.user)
    track = _session_track(session)
    profile = {}
    if isinstance(session.parsed_resume_data, dict):
        profile = session.parsed_resume_data.get("resume_profile", {}) or {}
    payload = json.loads(request.body or "{}")
    focus = payload.get("focus_area") or session.key_skills or session.job_role or "general"
    prompt = (
        "Generate 4 practice interview questions and return JSON {\"questions\":[...]}.\n"
        f"Role: {session.job_role}\nTrack: {track}\nFocus: {focus}\n"
        f"Resume anchors: projects={_safe_list(profile.get('projects'))[:3]}, experience={_safe_list(profile.get('experience_highlights'))[:3]}\n"
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
    return JsonResponse(
        {
            "success": True,
            "session_id": session.id,
            "job_role": session.job_role,
            "questions": questions,
            "question_bank": typed,
            "context": {"provider": provider, "model": model, "focus": focus, "track": track},
        }
    )


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
        }
    )
