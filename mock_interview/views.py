import json
import time
import base64
import logging
from io import BytesIO
import tempfile
import re
import os
import uuid
import asyncio
import random
import threading
from datetime import timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.conf import settings

# Resume parsing libs
import pdfplumber
import docx2txt

# AI providers
import openai
import google.generativeai as genai
from google.genai import types
from google.generativeai.types import HarmCategory # <-- ADDED THIS IMPORT

logger = logging.getLogger(__name__)

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
    logger.info("✓ edge-tts library imported successfully")
except ImportError:
    EDGE_TTS_AVAILABLE = False
    logger.warning("⚠ edge-tts not available, will use gTTS fallback")

try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
    logger.info("✓ gTTS library imported successfully")
except ImportError:
    GTTS_AVAILABLE = False
    logger.error("✗ gTTS not available - TTS will be disabled")

# ADD DEBUG CODE HERE - RIGHT AFTER logger definition
logger.info(f"=== AI CONFIGURATION DEBUG ===")
logger.info(f"AI_PROVIDER from settings: {getattr(settings, 'AI_PROVIDER', 'NOT SET')}")
logger.info(f"GEMINI_API_KEY present: {bool(getattr(settings, 'GEMINI_API_KEY', ''))}")
logger.info(f"GEMINI_API_KEY length: {len(getattr(settings, 'GEMINI_API_KEY', ''))}")
logger.info(f"OPENAI_API_KEY present: {bool(getattr(settings, 'OPENAI_API_KEY', ''))}")
logger.info(f"Environment AI_PROVIDER: {os.getenv('AI_PROVIDER', 'NOT SET')}")
logger.info(f"Environment GEMINI_API_KEY present: {bool(os.getenv('GEMINI_API_KEY', ''))}")
logger.info(f"================================")

from .models import MockInterviewSession, InterviewTurn
from .forms import InterviewSetupForm

# -------------------------
# Role check helpers
# -------------------------
def is_student(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'STUDENT'

def is_tutor(user):
    return user.is_authenticated and hasattr(user, 'profile') and user.profile.role == 'TUTOR' and user.profile.is_approved_tutor

def is_admin(user):
    return user.is_authenticated and user.is_superuser

# -------------------------
# Enhanced AI Provider Setup with Error Handling
# -------------------------
AI_PROVIDER = getattr(settings, "AI_PROVIDER", "gemini").lower()
GEMINI_API_KEY = getattr(settings, "GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
OPENAI_API_KEY = getattr(settings, "OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))

GEMINI_MODEL_NAME = None  # Will be auto-detected

def detect_available_gemini_model():
    """Detect which Gemini model is available in the current API version."""
    global GEMINI_MODEL_NAME
    
    if not GEMINI_API_KEY:
        logger.error("No Gemini API key configured")
        return None
    
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        # List all available models
        available_models = []
        for model in genai.list_models():
            if 'generateContent' in model.supported_generation_methods:
                available_models.append(model.name)
        
        logger.info(f"Available Gemini models: {available_models}")
        
        # Prioritize flash models - they have MUCH higher rate limits
        preferred_models = [
            'models/gemini-1.5-flash-8b',    # Fastest, highest limits
            'models/gemini-1.5-flash',        # Fast with good limits
            'models/gemini-1.5-flash-latest',
            'models/gemini-1.5-pro',          # Slower, lower limits
            'models/gemini-2.0-flash-exp',    # Experimental
        ]
        
        # Find first available preferred model
        for preferred in preferred_models:
            for available in available_models:
                if preferred in available:
                    GEMINI_MODEL_NAME = available
                    logger.info(f"✓ Using Gemini model: {GEMINI_MODEL_NAME}")
                    return GEMINI_MODEL_NAME
        
        # If no preferred model found, use first available
        if available_models:
            GEMINI_MODEL_NAME = available_models[0]
            logger.info(f"✓ Using first available Gemini model: {GEMINI_MODEL_NAME}")
            return GEMINI_MODEL_NAME
        
        logger.error("No compatible Gemini models found")
        return None
        
    except Exception as e:
        logger.error(f"Failed to detect Gemini models: {e}")
        return None

# Initialize AI providers with better error handling
def initialize_ai_providers():
    """Initialize AI providers with proper error handling and validation"""
    global AI_PROVIDER, GEMINI_API_KEY, OPENAI_API_KEY, GEMINI_MODEL_NAME
    
    providers_initialized = []
    
    if AI_PROVIDER == "openai" and OPENAI_API_KEY:
        try:
            openai.api_key = OPENAI_API_KEY
            if OPENAI_API_KEY.startswith('sk-') and len(OPENAI_API_KEY) > 20:
                providers_initialized.append("OpenAI")
                logger.info("OpenAI API initialized successfully")
            else:
                logger.error("OpenAI API key appears to be invalid format")
        except Exception as e:
            logger.error(f"OpenAI initialization failed: {e}")
                
    elif AI_PROVIDER == "gemini" and GEMINI_API_KEY:
        try:
            # Detect and set the correct model
            model_name = detect_available_gemini_model()
            
            if model_name:
                providers_initialized.append("Gemini")
                logger.info(f"Gemini API initialized successfully with model: {model_name}")
            else:
                logger.error("Failed to find compatible Gemini model")
                
        except Exception as e:
            logger.error(f"Gemini initialization failed: {e}")
    
    if not providers_initialized:
        logger.warning(f"No valid AI provider configured. AI_PROVIDER={AI_PROVIDER}")
        return False
    
    logger.info(f"AI providers initialized: {', '.join(providers_initialized)}")
    return True

# Initialize on module load
AI_INITIALIZED = initialize_ai_providers()

# -------------------------
# Enhanced TTS Functions with Better Error Handling
# -------------------------

# Indian English voices for edge-tts
EDGE_TTS_INDIAN_VOICES = [
    "en-IN-NeerjaNeural",
    "en-IN-PrabhatNeural", 
    "en-IN-NeerjaExpressiveNeural",
]

SARAH_VOICE = "en-IN-NeerjaNeural"

async def synthesize_speech_edge_tts(text, filename):
    """Convert text to speech using edge-tts with better error handling."""
    try:
        if not EDGE_TTS_AVAILABLE:
            raise ImportError("edge-tts not available")
        
        # Clean text for TTS
        clean_text = re.sub(r'[^\w\s.,!?;:()\'-]', '', text).strip()
        if len(clean_text) < 5:
            raise ValueError("Text too short for TTS")
        
        # Create media/audio directory
        audio_dir = os.path.join(settings.MEDIA_ROOT, "audio")
        os.makedirs(audio_dir, exist_ok=True)
        
        file_path = os.path.join(audio_dir, filename)
        
        # Use edge-tts with timeout
        communicate = edge_tts.Communicate(clean_text, SARAH_VOICE)
        await asyncio.wait_for(communicate.save(file_path), timeout=30.0)
        
        # Verify file was created and has content
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            raise Exception("Generated audio file is empty or missing")
        
        # Optional: Apply audio processing
        try:
            from pydub import AudioSegment
            sound = AudioSegment.from_file(file_path)
            faster_sound = sound.speedup(playback_speed=1.2)
            normalized = faster_sound.normalize()
            normalized.export(file_path, format="mp3")
            logger.info("Applied audio processing to edge-tts output")
        except ImportError:
            logger.info("pydub not available, using raw edge-tts output")
        except Exception as e:
            logger.warning(f"Audio processing failed: {e}, using raw edge-tts output")
        
        return settings.MEDIA_URL + "audio/" + filename
        
    except asyncio.TimeoutError:
        logger.error("edge-tts timeout")
        return None
    except Exception as e:
        logger.error(f"edge-tts failed: {e}")
        return None

def synthesize_speech_gtts(text, filename):
    """Convert text to speech using gTTS with better error handling."""
    try:
        # Clean and validate text
        clean_text = re.sub(r'[^\w\s.,!?;:()\'-]', '', text).strip()
        if len(clean_text) < 5:
            raise ValueError("Text too short for TTS")
        
        # Create TTS object with error handling
        tts = gTTS(
            text=clean_text,
            lang='en',
            tld='co.in',
            slow=False
        )

        # Create directory
        audio_dir = os.path.join(settings.MEDIA_ROOT, "audio")
        os.makedirs(audio_dir, exist_ok=True)

        file_path = os.path.join(audio_dir, filename)
        
        # Save with timeout (using threading for timeout)
        def save_with_timeout():
            tts.save(file_path)
        
        thread = threading.Thread(target=save_with_timeout)
        thread.start()
        thread.join(timeout=30.0)
        
        if thread.is_alive():
            logger.error("gTTS save operation timed out")
            return None
        
        # Verify file
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            raise Exception("Generated audio file is empty or missing")

        # Optional speed adjustment
        try:
            from pydub import AudioSegment
            sound = AudioSegment.from_file(file_path)
            faster_sound = sound.speedup(playback_speed=1.25)
            faster_sound.export(file_path, format="mp3")
            logger.info("Applied speed boost to gTTS output")
        except ImportError:
            logger.info("pydub not installed, skipping speed boost")
        except Exception as e:
            logger.warning(f"pydub processing failed: {e}")

        return settings.MEDIA_URL + "audio/" + filename

    except Exception as e:
        logger.error(f"gTTS failed: {e}")
        return None

def run_edge_tts_sync(text, filename):
    """Synchronous wrapper for edge-tts with better error handling."""
    try:
        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run with timeout
        result = loop.run_until_complete(
            asyncio.wait_for(
                synthesize_speech_edge_tts(text, filename),
                timeout=30.0
            )
        )
        return result
        
    except asyncio.TimeoutError:
        logger.error("edge-tts sync wrapper timed out")
        return None
    except Exception as e:
        logger.error(f"edge-tts sync wrapper failed: {e}")
        return None
    finally:
        try:
            loop.close()
        except:
            pass

# -------------------------
# Enhanced AI Call Function with Better Error Handling
# -------------------------
def call_ai_model(prompt, model_type="text", max_tokens=150, temperature=0.7, safety_settings=None): # <-- ADDED safety_settings
    """
    Enhanced AI model calling with better error handling and fallbacks.
    """
    if not AI_INITIALIZED:
        logger.error("AI providers not properly initialized")
        return _get_fallback_response(model_type)

    try:
        if AI_PROVIDER == "gemini":
            return _call_gemini_model(prompt, model_type, max_tokens, temperature, safety_settings) # <-- PASSED safety_settings
        elif AI_PROVIDER == "openai":
            return _call_openai_model(prompt, model_type, max_tokens, temperature) # No change needed here
        else:
            raise ValueError(f"Unknown AI provider: {AI_PROVIDER}")

    except Exception as e:
        logger.exception(f"AI model call failed (type={model_type}): {e}")
        
        # Check if it's an API key issue
        if any(keyword in str(e).lower() for keyword in ['api_key', 'invalid', 'expired', 'unauthorized']):
            logger.error("API key appears to be invalid or expired. Please check your configuration.")
        
        return _get_fallback_response(model_type)

def _call_gemini_model(prompt, model_type, max_tokens, temperature, safety_settings=None): # <-- ADDED safety_settings
    """Call Gemini model with enhanced error handling."""
    global GEMINI_MODEL_NAME
    
    # Make sure we have a model name
    if not GEMINI_MODEL_NAME:
        logger.error("No Gemini model name set. Re-detecting...")
        GEMINI_MODEL_NAME = detect_available_gemini_model()
        if not GEMINI_MODEL_NAME:
            logger.error("Could not find any Gemini model. Aborting call.")
            return "" # Return empty string on failure
    
    if model_type == "tts":
        # Gemini native TTS not available in older versions
        logger.info("Gemini native TTS not available, will use edge-tts/gTTS fallback")
        return {"audio_base64": "", "mime": ""}

    elif model_type in ["edge_tts", "gtts"]:
        # Handle external TTS
        try:
            audio_filename = f"interview_{int(time.time())}_{uuid.uuid4().hex[:8]}.mp3"
            
            if model_type == "edge_tts" and EDGE_TTS_AVAILABLE:
                audio_url = run_edge_tts_sync(prompt, audio_filename)
                if audio_url:
                    return {"audio_url": audio_url, "mime": "audio/mpeg", "method": "edge_tts"}
                else:
                    # Fallback to gTTS
                    audio_url = synthesize_speech_gtts(prompt, audio_filename)
                    if audio_url:
                        return {"audio_url": audio_url, "mime": "audio/mpeg", "method": "gtts_fallback"}
            else:
                audio_url = synthesize_speech_gtts(prompt, audio_filename)
                if audio_url:
                    return {"audio_url": audio_url, "mime": "audio/mpeg", "method": "gtts"}
            
            return {"audio_url": None, "mime": "", "method": f"{model_type}_failed"}
            
        except Exception as e:
            logger.error(f"{model_type} failed: {e}")
            return {"audio_url": None, "mime": "", "method": f"{model_type}_failed"}

    else:
        # Text generation - USE THE DETECTED MODEL NAME
        
        try:
            # --- OPTIMIZATION ---
            # We now force GEMINI_MODEL_NAME to be 'gemini-1.5-flash' (or similar)
            # from the detection function, ensuring a fast and cheap model is used.
            model = genai.GenerativeModel(GEMINI_MODEL_NAME)
            
            generation_config = {
                'temperature': temperature,
                'top_p': 0.9,
                'top_k': 40,
                'max_output_tokens': max_tokens,
            }
            
            # Add retry logic
            for attempt in range(3):
                try:
                    response = model.generate_content(
                        prompt, 
                        generation_config=generation_config,
                        safety_settings=safety_settings # <-- PASSED safety_settings
                    )
                    
                    if response.text:
                        return response.text.strip()
                    else:
                        # This handles the safety block: response.text is empty
                        # Check for safety finish_reason
                        try:
                            if response.candidates[0].finish_reason.name == "SAFETY":
                                logger.error(f"Gemini attempt {attempt + 1} blocked for SAFETY reasons.")
                                raise Exception("Content blocked by safety settings.")
                        except Exception:
                            # Fallback for other empty responses
                            logger.warning(f"Empty response from Gemini on attempt {attempt + 1}")
                        
                except Exception as e:
                    error_message = str(e)
                    logger.warning(f"Gemini attempt {attempt + 1} failed: {error_message}")
                    
                    # Do not retry on quota errors, it will just fail again
                    if "429" in error_message or "quota" in error_message.lower():
                        logger.error("Quota exceeded. Aborting retries.")
                        raise e # Re-raise the quota error
                        
                    if "SAFETY" in error_message.upper():
                        logger.error("Safety block detected. Aborting retries.")
                        raise e # Re-raise the safety error

                    if attempt == 2:  # Last attempt
                        raise e
                    time.sleep(1)  # Wait before retry
            
            return ""
            
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            return ""

def _call_openai_model(prompt, model_type, max_tokens, temperature):
    """Call OpenAI model with enhanced error handling."""
    if model_type == "tts":
        try:
            response = openai.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=prompt[:4000],
                speed=1.2,
                response_format="mp3"
            )
            audio_bytes = response.content
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            return {"audio_base64": audio_base64, "mime": "audio/mpeg"}
            
        except Exception as e:
            logger.error(f"OpenAI TTS failed: {e}")
            return {"audio_base64": "", "mime": ""}

    elif model_type in ["edge_tts", "gtts"]:
        # Handle external TTS (same as Gemini)
        try:
            audio_filename = f"interview_{int(time.time())}_{uuid.uuid4().hex[:8]}.mp3"
            
            if model_type == "edge_tts" and EDGE_TTS_AVAILABLE:
                audio_url = run_edge_tts_sync(prompt, audio_filename)
                if audio_url:
                    return {"audio_url": audio_url, "mime": "audio/mpeg", "method": "edge_tts"}
                else:
                    # Fallback to gTTS
                    audio_url = synthesize_speech_gtts(prompt, audio_filename)
                    if audio_url:
                        return {"audio_url": audio_url, "mime": "audio/mpeg", "method": "gtts_fallback"}
            else:
                audio_url = synthesize_speech_gtts(prompt, audio_filename)
                if audio_url:
                    return {"audio_url": audio_url, "mime": "audio/mpeg", "method": "gtts"}
            
            return {"audio_url": None, "mime": "", "method": f"{model_type}_failed"}
            
        except Exception as e:
            logger.error(f"{model_type} failed: {e}")
            return {"audio_url": None, "mime": "", "method": f"{model_type}_failed"}

    else:
        # Text generation with retry logic
        for attempt in range(3):
            try:
                resp = openai.chat.completions.create(
                    model="gpt-4o-mini", # Using the cost-effective 4o-mini
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=30.0
                )
                
                if resp.choices and resp.choices[0].message.content:
                    return resp.choices[0].message.content.strip()
                else:
                    logger.warning(f"Empty response from OpenAI on attempt {attempt + 1}")
                    
            except Exception as e:
                error_message = str(e)
                logger.warning(f"OpenAI attempt {attempt + 1} failed: {error_message}")
                
                # Do not retry on quota errors
                if "429" in error_message or "quota" in error_message.lower():
                    logger.error("Quota exceeded. Aborting retries.")
                    raise e
                    
                if attempt == 2:  # Last attempt
                    raise e
                time.sleep(1)  # Wait before retry
        
        return ""

def _get_fallback_response(model_type):
    """Provide fallback responses when AI fails."""
    if model_type in ["tts", "gtts", "edge_tts"]:
        return {"audio_base64": "", "mime": "", "audio_url": None, "method": "failed"}
    else:
        # Provide a basic fallback interview question
        fallback_questions = [
            "I apologize, but I'm experiencing technical difficulties. Could you please tell me about your background and experience?",
            "Let's continue with a basic question - what interests you most about this role?",
            "Can you share an example of a challenging project you've worked on recently?",
            "What do you consider your greatest professional strengths?"
        ]
        return random.choice(fallback_questions)

# -------------------------
# Enhanced Interview Logic with Better Question Flow
# -------------------------

SARAH_OPENING_LINES = [
    "Hello! I'm Sarah from the HR team at {company}. It's wonderful to meet you today! I'm really excited to learn more about your background and discuss this {role} opportunity with you.",
    "Hi there! I'm Sarah, and I'll be conducting your interview today. Thank you so much for taking the time to speak with us about the {role} position. I'm genuinely looking forward to our conversation!",
    "Good day! Sarah here from Human Resources. I hope you're having a great day so far! I'm thrilled to chat with you about the {role} role and get to know you better.",
    "Hello! I'm Sarah from the HR department. What a pleasure to meet you! I've been looking forward to this conversation about the {role} position all morning."
]

SARAH_CONVERSATION_STARTERS = [
    "Let's start with something I always find fascinating - could you walk me through what initially drew you to this field?",
    "I'd love to begin by understanding your journey better. What's been the most exciting part of your career path so far?",
    "To kick things off, I'm curious - what made you interested in this particular {role} opportunity with us?",
    "Let's dive right in! I always enjoy hearing about people's professional stories. Could you share what you're most passionate about in your work?"
]

def generate_enhanced_interview_prompt(session, turn_count=0, conversation_context="", user_response=""):
    """Generate enhanced interview prompts with better conversation flow and error handling."""
    
    company_name = getattr(settings, 'COMPANY_NAME', 'our innovative company')
    
    if turn_count == 0:
        # First interaction - warm opening
        opening_line = random.choice(SARAH_OPENING_LINES).format(
            company=company_name, 
            role=session.job_role
        )
        conversation_starter = random.choice(SARAH_CONVERSATION_STARTERS).format(
            role=session.job_role
        )
        
        return f"""
You are Sarah, a warm, enthusiastic, and highly professional HR interviewer at {company_name}. 
You have years of experience making candidates feel comfortable while conducting thorough assessments.

Today you're interviewing for: {session.job_role}
Key skills to evaluate: {session.key_skills}

Your personality traits:
- Genuinely interested in people's stories and experiences
- Encouraging but maintains professional standards
- Asks thoughtful follow-up questions
- Uses natural conversational flow
- Speaks at a comfortable, measured pace
- Shows authentic enthusiasm for good answers

IMPORTANT: You are the INTERVIEWER. You ask questions. You do NOT answer questions on behalf of the candidate.

Start the interview with this exact opening:
"{opening_line}"

Then immediately continue with:
"{conversation_starter}"

Keep your response concise and under 100 words, warm and engaging.
DO NOT include any simulated candidate responses.
"""
    
    # Progressive interview stages with better logic
    if turn_count <= 2:
        stage_guidance = f"""
        Focus: Building rapport and understanding their background (Questions 1-2)
        Sarah's approach: Show genuine interest in their journey and experiences
        
        The candidate just said: "{user_response}"
        
        Acknowledge their response briefly and naturally, then ask ONE clear follow-up question about:
        - Their career journey or key learning moments
        - What drives their interest in {session.job_role}
        - Their professional background and motivation
        
        Keep your response brief (under 60 words) and ask ONLY ONE question.
        DO NOT answer the question for them or simulate their response.
        """
    elif turn_count <= 5:
        stage_guidance = f"""
        Focus: Technical competencies for {session.job_role} (Questions 3-5)
        Sarah's approach: Explore their expertise while maintaining encouraging tone
        
        Skills to explore: {session.key_skills}
        
        The candidate just said: "{user_response}"
        
        Acknowledge their response briefly, then ask ONE clear question about their technical experience:
        - Their experience with relevant skills/technologies
        - Problem-solving approaches
        - Specific project examples
        
        Keep your response brief (under 60 words) and ask ONLY ONE question.
        DO NOT answer the question for them or simulate their response.
        """
    elif turn_count <= 8:
        stage_guidance = f"""
        Focus: Behavioral situations and teamwork (Questions 6-8)
        Sarah's approach: Explore workplace scenarios and collaboration
        
        The candidate just said: "{user_response}"
        
        Acknowledge their response briefly, then ask ONE behavioral question about:
        - Challenging situations they've navigated
        - Collaboration and teamwork experiences
        - How they handle priorities and deadlines
        - Leadership or initiative examples
        
        Keep your response brief (under 60 words) and ask ONLY ONE question.
        DO NOT answer the question for them or simulate their response.
        """
    elif turn_count <= 10:
        stage_guidance = f"""
        Focus: Cultural fit and future goals (Questions 9-10)
        Sarah's approach: Understand their values and aspirations
        
        The candidate just said: "{user_response}"
        
        Acknowledge their response briefly, then ask ONE question about:
        - What motivates them professionally
        - Their work style and preferences
        - Goals for the {session.job_role} role
        - Questions about the company/role
        
        Keep your response brief (under 60 words) and ask ONLY ONE question.
        DO NOT answer the question for them or simulate their response.
        """
    else:
        stage_guidance = f"""
        Focus: Graceful conclusion (Question 11+)
        Sarah's approach: Wrap up warmly and professionally
        
        The candidate just said: "{user_response}"
        
        Start your response with "INTERVIEW_COMPLETE" then provide a warm, encouraging closing that:
        - Thanks them for their time
        - Mentions something positive from the conversation
        - Explains next steps
        - Gives them a final opportunity to add anything
        
        Keep the closing under 150 words and very encouraging.
        DO NOT simulate their final response.
        """
    
    return f"""
You are Sarah, the warm and professional HR interviewer.
Position: {session.job_role}
Key skills to assess: {session.key_skills}
Current question number: {turn_count + 1}

{stage_guidance}

Recent conversation history:
{conversation_context[-1000:] if conversation_context else "This is the start of the conversation"}

CRITICAL INSTRUCTIONS:
- You are the INTERVIEWER asking questions
- Acknowledge the candidate's response naturally
- Ask ONE clear, thoughtful question
- DO NOT answer your own questions
- DO NOT simulate or imagine the candidate's responses
- Keep responses conversational and brief
- Show genuine professional interest
- Use encouraging but not excessive language

Generate ONLY Sarah's next response (brief and under 60 words unless closing):
"""

def analyze_interview_performance(session):
    """
    Enhanced performance analysis with STRICT JSON output.
    Returns a valid JSON string with structured feedback.
    """
    turns = session.turns.all().order_by('turn_number')
    conversation = []
    
    for turn in turns:
        if turn.ai_question:
            conversation.append(f"SARAH: {turn.ai_question}")
        if turn.user_answer:
            conversation.append(f"CANDIDATE: {turn.user_answer}")
    
    total_questions = len(turns)
    interview_duration = 0
    if session.start_time and session.end_time:
        interview_duration = (session.end_time - session.start_time).total_seconds() / 60
    
    # Enhanced prompt with STRICT JSON requirements
    analysis_prompt = f"""
You are an expert interview coach providing comprehensive analysis.

Interview Details:
- Position: {session.job_role}
- Key skills: {session.key_skills}
- Questions: {total_questions}
- Duration: {interview_duration:.1f} minutes

Conversation (last 20 exchanges):
{chr(10).join(conversation[-20:])}

CRITICAL: You MUST respond with ONLY valid JSON. No markdown, no code blocks, no explanations.
Start your response with {{ and end with }}.

Provide analysis in this EXACT JSON format:
{{
    "overall_score": 75,
    "strengths": [
        "First specific positive observation",
        "Second specific positive observation",
        "Third specific positive observation"
    ],
    "areas_for_improvement": [
        "First constructive suggestion",
        "Second constructive suggestion",
        "Third constructive suggestion"
    ],
    "technical_assessment": "Single paragraph evaluating technical competency for {session.job_role}",
    "communication_score": 75,
    "confidence_level": "Good",
    "recommendations": [
        "First actionable improvement step",
        "Second actionable improvement step",
        "Third actionable improvement step",
        "Fourth actionable improvement step"
    ],
    "encouragement_note": "Encouraging, personalized message in 2-3 sentences"
}}

Rules:
- overall_score: integer 60-95
- communication_score: integer 60-100
- confidence_level: one of ["Developing", "Good", "Strong", "Excellent"]
- All arrays must have at least 3 items
- All strings must be properly escaped
- No line breaks within string values
- Be encouraging yet constructive

Output ONLY the JSON, nothing else:
"""
    
    try:
        # Call AI with explicit JSON requirement
        ai_response = call_ai_model(
            analysis_prompt, 
            model_type="text", 
            max_tokens=1500,  # Increased for detailed feedback
            temperature=0.7
        )
        
        if not ai_response:
            logger.error("No response from AI model for performance analysis")
            raise Exception("No AI response received")
        
        # Log the raw response for debugging
        logger.info(f"Raw AI analysis response (first 200 chars): {ai_response[:200]}")
        
        # Try to extract JSON if wrapped in markdown or extra text
        cleaned_response = ai_response.strip()
        
        # Remove markdown code blocks if present
        if cleaned_response.startswith('```'):
            json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', cleaned_response, re.DOTALL)
            if json_match:
                cleaned_response = json_match.group(1)
                logger.info("Extracted JSON from markdown code block")
        
        # Find the JSON object (from first { to last })
        first_brace = cleaned_response.find('{')
        last_brace = cleaned_response.rfind('}')
        
        if first_brace != -1 and last_brace != -1:
            json_str = cleaned_response[first_brace:last_brace+1]
            
            # Validate it's proper JSON
            parsed_json = json.loads(json_str)
            
            # Validate structure
            required_keys = ['overall_score', 'strengths', 'areas_for_improvement', 
                           'technical_assessment', 'communication_score', 'confidence_level',
                           'recommendations', 'encouragement_note']
            
            for key in required_keys:
                if key not in parsed_json:
                    logger.warning(f"Missing key in AI response: {key}")
                    raise ValueError(f"Missing required key: {key}")
            
            # Return the cleaned, valid JSON string
            logger.info("Successfully generated and validated performance analysis JSON")
            return json_str
            
        else:
            logger.error("Could not find JSON object in AI response")
            raise ValueError("No valid JSON object found in response")
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error in performance analysis: {e}")
        logger.error(f"Problematic response: {ai_response[:500] if ai_response else 'None'}")
        
        # Return a valid fallback JSON string
        return json.dumps({
            "overall_score": 70,
            "strengths": [
                "Completed the full interview session",
                "Engaged with all questions presented",
                "Demonstrated interest in the position"
            ],
            "areas_for_improvement": [
                "Provide more detailed responses with specific examples",
                "Practice structuring answers using the STAR method",
                "Prepare concrete examples from past experience"
            ],
            "technical_assessment": f"The interview covered skills relevant to the {session.job_role} position. To strengthen technical proficiency, focus on building deeper expertise in {session.key_skills}. Practice explaining technical concepts clearly and prepare specific project examples.",
            "communication_score": 70,
            "confidence_level": "Good",
            "recommendations": [
                "Practice mock interviews regularly to build confidence",
                "Prepare 5-7 specific examples using the STAR method",
                "Research common questions for your target role",
                "Record yourself to improve delivery and pacing",
                "Focus on clear, concise communication"
            ],
            "encouragement_note": "You've taken an important step by completing this mock interview! With continued practice and preparation, your interview skills will improve significantly. Keep working on providing specific examples and you'll see great results."
        })
        
    except Exception as e:
        logger.error(f"Performance analysis failed with error: {e}")
        
        # Return valid fallback JSON string
        return json.dumps({
            "overall_score": 70,
            "strengths": [
                "Successfully completed the mock interview",
                "Showed engagement throughout the session",
                "Demonstrated interest in improvement"
            ],
            "areas_for_improvement": [
                "Continue practicing interview skills",
                "Focus on providing detailed responses",
                "Prepare specific examples from your experience"
            ],
            "technical_assessment": f"Technical skills for the {session.job_role} role were discussed. Continue building expertise in {session.key_skills}.",
            "communication_score": 70,
            "confidence_level": "Good",
            "recommendations": [
                "Practice regularly with mock interviews",
                "Prepare concrete examples using STAR method",
                "Research your target role thoroughly",
                "Focus on clear communication"
            ],
            "encouragement_note": "Great job completing this interview! Keep practicing and you'll continue to improve your interview skills."
        })

# -------------------------
# Resume Processing Functions
# -------------------------

def extract_text_from_pdf(file_obj):
    """Extract text from PDF with better error handling."""
    text_parts = []
    try:
        file_bytes = file_obj.read()
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
    except Exception as e:
        logger.exception("Failed to extract PDF text: %s", e)
    return "\n".join(text_parts).strip()

def extract_text_from_docx(file_obj):
    """Extract text from DOCX with better error handling."""
    try:
        file_bytes = file_obj.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tf:
            tf.write(file_bytes)
            temp_path = tf.name
        text = docx2txt.process(temp_path).strip()
        # Clean up temp file
        try:
            os.unlink(temp_path)
        except:
            pass
        return text
    except Exception as e:
        logger.exception("Failed to extract DOCX text: %s", e)
        return ""

def parse_resume_file(file_obj, filename=None):
    """Parse resume file with enhanced error handling."""
    if not file_obj:
        return ""
    
    fname = (filename or getattr(file_obj, 'name', '')).lower()
    
    try:
        if fname.endswith('.pdf'):
            return extract_text_from_pdf(file_obj)
        elif fname.endswith(('.docx', '.doc')):
            return extract_text_from_docx(file_obj)
        else:
            # Try to read as text file
            return file_obj.read().decode('utf-8', errors='ignore')
    except Exception as e:
        logger.exception(f"Failed to parse resume file: {e}")
        return ""

def extract_structured_from_resume_text(resume_text):
    """Extract structured data from resume with better error handling."""
    if not resume_text or len(resume_text.strip()) < 100:
        return {
            "job_role": "", "skills": [], "experience_years": 0, 
            "education": "", "summary": "", "key_achievements": [], 
            "industries": [], "raw": ""
        }
    
    prompt = (
        "You are an expert resume parsing assistant. Extract comprehensive information from this resume. "
        "Analyze the content thoroughly and return ONLY a valid JSON object with these exact keys:\n"
        "- job_role: Primary target job title/role\n"
        "- skills: Array of technical and soft skills (deduplicated)\n"
        "- experience_years: Estimated years of experience\n"
        "- education: Highest education level\n"
        "- summary: Professional summary (1-2 sentences)\n"
        "- key_achievements: Top 3 achievements/accomplishments\n"
        "- industries: Relevant industry experience\n\n"
        f"Resume text:\n{resume_text[:20000]}"
    )
    
    ai_output = "" # Initialize ai_output
    try:
        # --- MODIFICATION: ADDED LENIENT SAFETY SETTINGS ---
        lenient_safety_settings = [
            {'category': HarmCategory.HARM_CATEGORY_HARASSMENT, 'threshold': 'BLOCK_NONE'},
            {'category': HarmCategory.HARM_CATEGORY_HATE_SPEECH, 'threshold': 'BLOCK_NONE'},
            {'category': HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, 'threshold': 'BLOCK_NONE'},
            {'category': HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, 'threshold': 'BLOCK_NONE'},
        ]
        
        ai_output = call_ai_model(
            prompt, 
            model_type="text", 
            max_tokens=800, 
            safety_settings=lenient_safety_settings # <-- PASSED SETTINGS
        )
        
        if not ai_output:
            raise Exception("No AI response received")
        
        # Try to extract JSON from the response
        json_patterns = [
            r'\{[\s\S]*\}',
            r'```json\s*([\s\S]*?)\s*```',
            r'```\s*([\s\S]*?)\s*```'
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, ai_output)
            if match:
                json_str = match.group(1) if len(match.groups()) > 0 else match.group(0)
                try:
                    parsed = json.loads(json_str)
                    return {
                        "job_role": parsed.get("job_role", ""),
                        "skills": parsed.get("skills", []),
                        "experience_years": parsed.get("experience_years", 0),
                        "education": parsed.get("education", ""),
                        "summary": parsed.get("summary", ""),
                        "key_achievements": parsed.get("key_achievements", []),
                        "industries": parsed.get("industries", []),
                        "raw": ai_output
                    }
                except json.JSONDecodeError:
                    continue
        
        # If no JSON block is found, log a warning but still return a fallback
        logger.warning(f"Failed to parse JSON from AI resume analysis. Response: {ai_output}")
                    
    except Exception as e:
        logger.warning(f"Failed to parse AI resume analysis: {e}")
    
    # Return fallback structure
    return {
        "job_role": "", "skills": [], "experience_years": 0, 
        "education": "", "summary": "", "key_achievements": [], 
        "industries": [], "raw": ai_output
    }

# -------------------------
# Helper Functions for Interview Hints and Practice Questions
# -------------------------

def get_recent_conversation_context(recent_messages):
    """Extract recent conversation context for hint generation."""
    context_lines = []
    for msg in recent_messages:
        role = "SARAH" if msg.get('role') == 'model' else "CANDIDATE"
        text = msg.get('parts', [{}])[0].get('text', '')
        if text.strip():
            context_lines.append(f"{role}: {text[:200]}...")  # Truncate long messages
    
    return "\n".join(context_lines[-6:])  # Last 6 exchanges

def extract_json_from_response(response_text):
    """Extract JSON array from AI response, handling various formats."""
    if not response_text:
        return None
    
    # Try to find JSON array in the response
    json_patterns = [
        r'\[[\s\S]*\]',  # Direct array
        r'\{[\s\S]*\}',  # Direct object (for practice questions)
        r'```json\s*([\s\S]*?)\s*```',  # Code block
        r'```\s*([\s\S]*?)\s*```',  # Generic code block
    ]
    
    for pattern in json_patterns:
        match = re.search(pattern, response_text, re.DOTALL)
        if match:
            json_str = match.group(1) if len(match.groups()) > 0 else match.group(0)
            try:
                parsed_data = json.loads(json_str)
                
                # Validation for hints (list of dicts)
                if isinstance(parsed_data, list) and len(parsed_data) > 0:
                    if all('title' in hint and 'description' in hint for hint in parsed_data):
                        return parsed_data
                
                # Validation for practice questions (dict with 'questions' list)
                if isinstance(parsed_data, dict) and 'questions' in parsed_data and isinstance(parsed_data['questions'], list):
                     return parsed_data
                     
            except json.JSONDecodeError:
                continue
    
    return None

def get_interview_stage(question_number):
    """Determine interview stage based on question number."""
    if question_number <= 2:
        return "introduction"
    elif question_number <= 5:
        return "technical"
    elif question_number <= 8:
        return "behavioral"
    elif question_number <= 10:
        return "cultural_fit"
    else:
        return "closing"

def get_default_hints_for_stage(question_number):
    """Provide fallback hints based on interview stage."""
    stage = get_interview_stage(question_number)
    
    hint_sets = {
        "introduction": [
            {
                "title": "Start with a Strong Summary",
                "description": "Begin with a 30-60 second professional summary that highlights your key qualifications and enthusiasm for the role."
            },
            {
                "title": "Connect Your Background",
                "description": "Clearly link your past experiences to why you're interested in this specific position and company."
            },
            {
                "title": "Show Genuine Interest",
                "description": "Demonstrate that you've researched the company and role by mentioning specific aspects that appeal to you."
            },
            {
                "title": "Set a Positive Tone",
                "description": "Use confident language and maintain good eye contact to establish rapport from the start."
            }
        ],
        "technical": [
            {
                "title": "Use the STAR Method",
                "description": "Structure your response with Situation, Task, Action, and Result to provide comprehensive technical examples."
            },
            {
                "title": "Be Specific and Quantifiable",
                "description": "Include concrete details, metrics, and measurable outcomes that demonstrate your technical impact."
            },
            {
                "title": "Explain Your Thought Process",
                "description": "Walk through your problem-solving approach and decision-making logic to show your technical reasoning."
            },
            {
                "title": "Mention Tools and Technologies",
                "description": "Reference specific technologies, frameworks, or methodologies you used to solve the problem."
            },
            {
                "title": "Address Challenges Honestly",
                "description": "Discuss obstacles you faced and how you overcame them, showing resilience and learning ability."
            }
        ],
        "behavioral": [
            {
                "title": "Choose Relevant Examples",
                "description": "Select stories that directly relate to the skills and qualities needed for this specific role."
            },
            {
                "title": "Focus on Your Actions",
                "description": "Emphasize what YOU specifically did, not what your team did. Use 'I' statements to show your contribution."
            },
            {
                "title": "Highlight Learning and Growth",
                "description": "Show how challenges helped you develop professionally and what you learned from the experience."
            },
            {
                "title": "Demonstrate Leadership",
                "description": "Even if not in a management role, show times you took initiative, influenced others, or drove positive change."
            },
            {
                "title": "Show Emotional Intelligence",
                "description": "Discuss how you managed relationships, handled conflict, or adapted to different working styles."
            }
        ],
        "cultural_fit": [
            {
                "title": "Align with Company Values",
                "description": "Connect your personal values and work style with the company's culture and mission."
            },
            {
                "title": "Ask Thoughtful Questions",
                "description": "Prepare intelligent questions about the team, growth opportunities, and company direction."
            },
            {
                "title": "Show Long-term Interest",
                "description": "Explain how this role fits into your career goals and why you want to grow with this organization."
            },
            {
                "title": "Discuss Your Work Style",
                "description": "Be honest about how you prefer to work and collaborate, while showing flexibility."
            }
        ],
        "closing": [
            {
                "title": "Summarize Your Value",
                "description": "Briefly recap your key qualifications and why you're the ideal candidate for this role."
            },
            {
                "title": "Express Genuine Interest",
                "description": "Reaffirm your enthusiasm for the position and company with specific reasons."
            },
            {
                "title": "Ask About Next Steps",
                "description": "Inquire about the timeline and process for moving forward in the interview process."
            },
            {
                "title": "Leave a Lasting Impression",
                "description": "End with a confident statement about your readiness to contribute and make an impact."
            }
        ]
    }
    
    return hint_sets.get(stage, hint_sets["technical"])

def get_emergency_hints():
    """Emergency fallback hints when all else fails."""
    return [
        {
            "title": "Structure Your Response",
            "description": "Organize your answer with a clear beginning, middle, and end. Use the STAR method for behavioral questions."
        },
        {
            "title": "Provide Specific Examples",
            "description": "Support your claims with concrete examples from your experience. Include measurable results when possible."
        },
        {
            "title": "Show Your Thought Process",
            "description": "Explain how you approach problems and make decisions. Interviewers want to understand your reasoning."
        },
        {
            "title": "Connect to the Role",
            "description": "Relate your experiences directly to the position requirements and show how you can add value."
        },
        {
            "title": "Ask for Clarification",
            "description": "If a question is unclear, don't hesitate to ask for clarification to ensure you provide a relevant answer."
        }
    ]

def get_default_practice_questions(job_role, key_skills):
    """Generate default practice questions based on role and skills."""
    skills_list = [skill.strip() for skill in key_skills.split(',') if skill.strip()]
    
    questions = [
        {
            "id": 1,
            "question": f"Tell me about your experience with {skills_list[0] if skills_list else 'your key skills'} and how you've applied it in previous roles.",
            "type": "experience",
            "difficulty": "medium",
            "focus_skill": skills_list[0] if skills_list else "general",
            "tips": "Use the STAR method and provide specific examples with measurable results."
        },
        {
            "id": 2,
            "question": f"Describe a challenging project you worked on as a {job_role}. How did you overcome the obstacles?",
            "type": "behavioral",
            "difficulty": "medium",
            "focus_skill": "problem-solving",
            "tips": "Focus on your specific actions and the positive outcome you achieved."
        },
        {
            "id": 3,
            "question": "Where do you see yourself in 5 years, and how does this role fit into your career goals?",
            "type": "general",
            "difficulty": "easy",
            "focus_skill": "career planning",
            "tips": "Show ambition while demonstrating commitment to the company and role."
        },
        {
            "id": 4,
            "question": f"How would you handle a situation where you need to quickly learn a new technology or skill for a {job_role} project?",
            "type": "situational",
            "difficulty": "medium",
            "focus_skill": "adaptability",
            "tips": "Demonstrate your learning process and ability to adapt quickly."
        },
        {
            "id": 5,
            "question": f"What interests you most about working as a {job_role} at our company?",
            "type": "motivation",
            "difficulty": "easy",
            "focus_skill": "company fit",
            "tips": "Show that you've researched the company and connect it to your career goals."
        }
    ]
    
    return {
        "questions": questions,
        "total_count": len(questions)
    }

def get_emergency_practice_questions():
    """Emergency fallback practice questions."""
    return {
        "questions": [
            {
                "id": 1,
                "question": "Tell me about yourself and your professional background.",
                "type": "general",
                "difficulty": "easy",
                "focus_skill": "communication",
                "tips": "Keep it concise, professional, and relevant to the role."
            },
            {
                "id": 2,
                "question": "Describe a time when you faced a significant challenge at work. How did you handle it?",
                "type": "behavioral",
                "difficulty": "medium",
                "focus_skill": "problem-solving",
                "tips": "Use the STAR method: Situation, Task, Action, Result."
            },
            {
                "id": 3,
                "question": "What are your greatest strengths and how do they relate to this position?",
                "type": "general",
                "difficulty": "easy",
                "focus_skill": "self-awareness",
                "tips": "Choose strengths that are relevant to the job requirements."
            }
        ],
        "total_count": 3
    }

# -------------------------
# Enhanced Views
# -------------------------

@csrf_exempt
def start_mock_interview(request):
    """Start the mock interview session with better initialization."""
    return render(request, "mock_interview/start.html")

@login_required
@user_passes_test(is_student, login_url='/login/')
def interview_setup(request):
    """Enhanced interview setup with better error handling."""
    prefill = {}
    if request.method == 'POST':
        form = InterviewSetupForm(request.POST, request.FILES)
        resume_file = request.FILES.get('resume_file')
        
        # Clear any old analysis from the session
        if 'resume_analysis' in request.session:
            del request.session['resume_analysis']
        
        if resume_file:
            try:
                resume_text = parse_resume_file(resume_file, filename=resume_file.name)
                if resume_text:
                    parsed = extract_structured_from_resume_text(resume_text)
                    prefill.update({
                        'job_role': parsed.get('job_role', ''),
                        'key_skills': ", ".join(parsed.get('skills', [])),
                    })
                    # Store analysis in session to add to model AFTER form validation
                    request.session['resume_analysis'] = parsed 
                else:
                    messages.warning(request, "Could not extract text from resume.")
            except Exception as e:
                logger.exception("Error parsing resume: %s", e)
                messages.error(request, "Failed to parse resume.")
                
            # Update form with prefilled data
            post_data = request.POST.copy()
            for k, v in prefill.items():
                if not post_data.get(k):
                    post_data[k] = v
            form = InterviewSetupForm(post_data, request.FILES)

        if form.is_valid():
            try:
                session = form.save(commit=False)
                session.user = request.user
                session.status = 'STARTED'
                session.start_time = timezone.now()
                
                # Add resume analysis data from session
                resume_data = request.session.get('resume_analysis', {})
                if resume_data:
                    # Storing as JSONField (if model has it) or TextField
                    if hasattr(session, 'parsed_resume_data'):
                         session.parsed_resume_data = resume_data
                    if hasattr(session, 'additional_data'):
                         session.additional_data = json.dumps(resume_data)

                # Save the resume file if it exists
                if resume_file:
                    session.resume_file = resume_file
                
                session.save()
                # form.save_m2m() # No m2m fields in this form
                
                # Clean up session
                if 'resume_analysis' in request.session:
                    del request.session['resume_analysis']
                
                messages.success(request, "Interview session created successfully!")
                return redirect('mock_interview:main_interview', session_id=session.id)
                
            except Exception as e:
                logger.exception("Failed to create interview session: %s", e)
                messages.error(request, "Failed to create interview session. Please try again.")
                
    else:
        form = InterviewSetupForm()
        
    return render(request, 'mock_interview/interview_setup.html', {'form': form})

@login_required
@user_passes_test(is_student, login_url='/login/')
def main_interview(request, session_id):
    """Enhanced main interview view with better error handling."""
    session = get_object_or_404(MockInterviewSession, id=session_id, user=request.user)
    
    if request.method == 'POST':
        # This POST is triggered by the "Start Interview" button on the main_interview.html page
        # It's responsible for generating the *first* AI question.
        try:
            if session.status != 'STARTED':
                session.status = 'STARTED'
                session.start_time = timezone.now()
                session.save()

            turn_count = session.turns.count()
            ai_response_text = ""
            audio_data_url = None

            if turn_count == 0:
                prompt = generate_enhanced_interview_prompt(session, turn_count=0)
                ai_response_text = call_ai_model(prompt, max_tokens=300)

                if ai_response_text:
                    audio_result = call_ai_model(ai_response_text, model_type="edge_tts")
                    if audio_result and audio_result.get("audio_url"):
                        audio_data_url = audio_result["audio_url"]
                    else:
                        audio_result = call_ai_model(ai_response_text, model_type="gtts")
                        if audio_result and audio_result.get("audio_url"):
                            audio_data_url = audio_result["audio_url"]
                
                InterviewTurn.objects.create(session=session, turn_number=1, ai_question=ai_response_text)
                
                return JsonResponse({
                    "success": True,
                    "ai_response_text": ai_response_text,
                    "ai_audio_url": audio_data_url,
                    "current_question": 1
                })
            else:
                # This handles case where user refreshes page and clicks "Start" again
                last_turn = session.turns.order_by('-turn_number').first()
                return JsonResponse({
                    "success": True,
                    "ai_response_text": last_turn.ai_question,
                    "ai_audio_url": None, # Don't re-generate audio
                    "current_question": last_turn.turn_number
                })
        except Exception as e:
            logger.error(f"Error starting interview session {session_id}: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    # Handle GET request to render the page
    try:
        if session.status in ['COMPLETED', 'REVIEWED']:
            messages.info(request, "This interview has already been completed.")
            return redirect('mock_interview:review_interview', session_id=session.id)
            
        if session.status != 'STARTED':
            session.status = 'STARTED'
            session.save(update_fields=['status'])
        
        initial_chat_history = []
        turns = session.turns.all().order_by('turn_number')
        
        for turn in turns:
            if turn.ai_question:
                initial_chat_history.append({'role': 'model', 'parts': [{'text': turn.ai_question}]})
            if turn.user_answer:
                initial_chat_history.append({'role': 'user', 'parts': [{'text': turn.user_answer}]})
        
        total_turns = turns.count()
        
        context = {
            'session_id': session.id,
            'job_role': session.job_role,
            'key_skills': session.key_skills,
            'initial_chat_history_json': json.dumps(initial_chat_history),
            'interview_progress': json.dumps({
                'total_questions': total_turns,
                'in_progress': total_turns > 0,
                'current_question': total_turns + 1,
            }),
            'ai_initialized': AI_INITIALIZED,
            'edge_tts_available': EDGE_TTS_AVAILABLE
        }
        
        return render(request, 'mock_interview/main_interview.html', context)
        
    except Exception as e:
        logger.exception("Error loading main interview: %s", e)
        messages.error(request, "Failed to load interview session. Please try again.")
        return redirect('mock_interview:interview_setup')

@csrf_exempt
def interact_with_ai(request, interview_id):
    """
    Legacy AI interaction endpoint. 
    NOTE: This view is NOT session-aware and is likely deprecated. 
    The main logic is in ai_interaction_api.
    """
    logger.warning(f"Legacy interact_with_ai endpoint hit for interview_id {interview_id}. This may be deprecated.")
    
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST required"}, status=400)
    
    try:
        # Check if AI is initialized
        if not AI_INITIALIZED:
            return JsonResponse({
                "success": False, 
                "error": "AI service temporarily unavailable. Please check your API configuration.",
                "debug_info": {
                    "ai_provider": AI_PROVIDER,
                    "ai_initialized": AI_INITIALIZED
                }
            }, status=503)
        
        # Get user input
        user_input = request.POST.get("userResponse", "").strip()
        if not user_input:
            return JsonResponse({"success": False, "error": "No input provided"}, status=400)
        
        # Create interview context
        interview_prompt = f"""
        You are Sarah, a warm and friendly HR interviewer with a natural, conversational style. 
        
        The candidate just said: "{user_input}"
        
        Respond naturally and encouragingly as a professional interviewer would.
        Keep your response conversational, warm, and under 150 words.
        Ask a relevant follow-up question or move to the next interview topic.
        
        Be encouraging and show genuine interest in their responses.
        Speak at a comfortable pace with natural pauses and inflections.
        """
        
        # Generate AI text response
        ai_text = call_ai_model(interview_prompt, model_type="text", max_tokens=300, temperature=0.8)
        
        if not ai_text:
            return JsonResponse({
                "success": False,
                "error": "Failed to generate AI response. Please try again.",
                "debug_info": {"text_generated": False}
            }, status=500)
        
        # Generate audio using edge-tts first, then gTTS as fallback
        ai_audio_url = None
        tts_method = "none"
        
        try:
            # Try edge-tts first
            audio_result = call_ai_model(ai_text, model_type="edge_tts")
            if audio_result.get("audio_url"):
                ai_audio_url = audio_result["audio_url"]
                tts_method = "edge_tts"
            else:
                # Fallback to gTTS
                logger.info("edge-tts failed, trying gTTS fallback")
                audio_result = call_ai_model(ai_text, model_type="gtts")
                if audio_result.get("audio_url"):
                    ai_audio_url = audio_result["audio_url"]
                    tts_method = "gtts"
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            ai_audio_url = None
            tts_method = "failed"
        
        return JsonResponse({
            "success": True,
            "ai_response_text": ai_text,
            "ai_audio_url": ai_audio_url,
            "interview_complete": False,
            "debug_info": {
                "audio_generated": bool(ai_audio_url),
                "text_length": len(ai_text),
                "tts_method": tts_method, # <-- Corrected variable name
                "edge_tts_available": EDGE_TTS_AVAILABLE,
                "ai_initialized": AI_INITIALIZED
            }
        })
        
    except Exception as e:
        logger.exception("AI interaction failed")
        return JsonResponse({
            "success": False, 
            "error": "An error occurred during AI interaction. Please try again.",
            "debug_info": {"exception": str(e)}
        }, status=500)

@login_required
@user_passes_test(is_student, login_url='/login/')
@csrf_exempt
def ai_interaction_api(request, session_id):
    """Enhanced main AI interaction endpoint with better error handling."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method.'}, status=405)
    
    try:
        session = get_object_or_404(MockInterviewSession, id=session_id, user=request.user)
        
        # Check if AI is initialized
        if not AI_INITIALIZED:
            return JsonResponse({
                'error': 'AI service is currently unavailable. Please check the system configuration.',
                'debug_info': {
                    'ai_provider': AI_PROVIDER,
                    'ai_initialized': AI_INITIALIZED
                }
            }, status=503)
        
        # Parse request payload
        try:
            payload = json.loads(request.body)
            user_response_text = payload.get('user_response', '').strip()
            chat_history = payload.get('chat_history', [])
            request_type = payload.get('request_type', 'normal')
        except json.JSONDecodeError as e:
            return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

        # IMPORTANT: Only process if we have a user response
        if not user_response_text:
            return JsonResponse({'error': 'No user response provided.'}, status=400)

        current_turn_count = session.turns.count()
        interview_duration = 0
        if session.start_time:
            interview_duration = (timezone.now() - session.start_time).total_seconds() / 60
        
        # Save the user's response to the CURRENT (last) turn first
        if current_turn_count > 0:
            try:
                last_turn = session.turns.order_by('-turn_number').first()
                if last_turn and not last_turn.user_answer:  # Only update if empty
                    last_turn.user_answer = user_response_text
                    last_turn.save(update_fields=['user_answer'])
                    logger.info(f"Saved user response to turn {last_turn.turn_number}")
            except Exception as e:
                logger.error(f"Error saving user answer: {e}")
        
        # Build conversation context for better continuity
        conversation_context = []
        for msg in chat_history[-8:]:  # Last 8 messages for better context
            role = "SARAH" if msg.get('role') == 'model' else "CANDIDATE"
            text = msg.get('parts', [{}])[0].get('text', '')
            if text.strip():  # Only add non-empty messages
                conversation_context.append(f"{role}: {text}")
        
        context_str = "\n".join(conversation_context)
        
        # Generate enhanced interview prompt for Sarah's NEXT question
        ai_prompt = generate_enhanced_interview_prompt(
            session, 
            current_turn_count,  # This is the count of existing turns
            context_str, 
            user_response_text
        )
        
        # Add interview progress context
        ai_prompt += f"""
        
        Interview Flow Context:
        - This will be question {current_turn_count + 1}
        - Interview duration: {interview_duration:.1f} minutes
        - Target total duration: 18-22 minutes
        
        Decision points:
        - If question 11+ OR duration > 20 minutes: Start moving toward conclusion
        - If question 13+ OR duration > 25 minutes: Complete the interview warmly
        
        When ending, begin response with "INTERVIEW_COMPLETE" then provide a warm, personalized closing.
        
        CRITICAL: You are Sarah the interviewer. Your job is to ASK the next question, NOT to answer it yourself.
        Generate ONLY Sarah's next question or comment. Do not include any candidate responses.
        
        Remember: You're Sarah - genuinely interested, encouraging, and professionally warm.
        """

        # Call AI model for Sarah's response (next question)
        ai_response_text = call_ai_model(
            ai_prompt, 
            model_type="text", 
            max_tokens=400, 
            temperature=0.8
        )
        
        if not ai_response_text:
            return JsonResponse({
                'error': 'Failed to generate AI response. Please try again.',
                'debug_info': {'text_generated': False}
            }, status=500)
        
        # Check if interview should complete
        is_complete = False
        if (ai_response_text.startswith("INTERVIEW_COMPLETE") or 
            current_turn_count >= 12 or 
            interview_duration > 25):
            is_complete = True
            if ai_response_text.startswith("INTERVIEW_COMPLETE"):
                ai_response_text = ai_response_text.replace("INTERVIEW_COMPLETE", "").strip()
            
            if not ai_response_text or len(ai_response_text.strip()) < 50:
                ai_response_text = "Thank you so much for this wonderful conversation! You've shared some really insightful responses about your experience and approach to work. I can tell you've put a lot of thought into your career development. You should receive detailed feedback shortly. I really enjoyed getting to know you today, and I wish you the very best!"

        # Generate audio with better error handling
        audio_data_url = None
        tts_method = "none"
        
        if ai_response_text and len(ai_response_text.strip()) > 5:
            # Clean text for better TTS
            clean_text = re.sub(r'[^\w\s.,!?;:()\'-]', '', ai_response_text).strip()
            clean_text = re.sub(r'([.!?])\s+', r'\1... ', clean_text)  # Add pauses
            
            if len(clean_text) > 10:
                logger.info(f"Generating TTS for: {clean_text[:100]}...")
                
                # Try edge-tts first
                try:
                    if EDGE_TTS_AVAILABLE:
                        audio_result = call_ai_model(clean_text, model_type="edge_tts")
                        if audio_result.get("audio_url"):
                            audio_data_url = audio_result["audio_url"]
                            tts_method = "edge_tts"
                            logger.info("edge-tts successful")
                        else:
                            raise Exception("edge-tts returned no URL")
                    else:
                        raise ImportError("edge-tts not available")
                        
                except Exception as e:
                    logger.warning(f"edge-tts failed, trying gTTS fallback: {e}")
                    
                    # Fallback to gTTS
                    try:
                        audio_result = call_ai_model(clean_text, model_type="gtts")
                        if audio_result.get("audio_url"):
                            audio_data_url = audio_result["audio_url"]
                            tts_method = "gtts"
                            logger.info("gTTS fallback successful")
                        else:
                            raise Exception("gTTS returned no URL")
                            
                    except Exception as gtts_error:
                        logger.warning(f"gTTS fallback failed: {gtts_error}")
                        tts_method = "all_failed"

        # Create a NEW turn for Sarah's next question
        try:
            new_turn = InterviewTurn.objects.create(
                session=session,
                turn_number=current_turn_count + 1,
                ai_question=ai_response_text,
                user_answer=None,  # User hasn't answered this question yet
                ai_internal_analysis=json.dumps({
                    "turn": current_turn_count + 1,
                    "duration_minutes": round(interview_duration, 1),
                    "audio_generated": bool(audio_data_url),
                    "tts_method": tts_method,
                    "response_length": len(ai_response_text),
                    "user_response_length": len(user_response_text),
                    "edge_tts_available": EDGE_TTS_AVAILABLE,
                    "ai_initialized": AI_INITIALIZED,
                    "timestamp": timezone.now().isoformat()
                })
            )
            logger.info(f"Created new turn {new_turn.turn_number} with Sarah's question")
        except Exception as e:
            logger.error(f"Failed to create new interview turn: {e}")
            return JsonResponse({
                'error': 'Failed to save interview progress.',
                'debug_info': {'exception': str(e)}
            }, status=500)

        # Complete interview if needed
        if is_complete:
            session.status = 'COMPLETED'
            session.end_time = timezone.now()
            
            try:
                performance_analysis = analyze_interview_performance(session)
                # Check if model has ai_feedback field
                if hasattr(session, 'ai_feedback'):
                    session.ai_feedback = performance_analysis
                else:
                    # Fallback to saving in overall_feedback
                    session.overall_feedback = performance_analysis
                logger.info(f"Generated performance analysis for session {session.id}")
            except Exception as e:
                logger.warning(f"Failed to generate performance analysis: {e}")
            
            session.save()

        # Enhanced response data
        response_data = {
            "success": True,
            "ai_response_text": ai_response_text,
            "ai_audio_url": audio_data_url,
            "interview_complete": is_complete,
            "interview_progress": {
                "current_question": current_turn_count + 1,
                "duration_minutes": round(interview_duration, 1),
                "estimated_remaining": max(0, 22 - interview_duration),
                "questions_remaining": max(0, 12 - current_turn_count)
            },
            "debug_info": {
                "audio_generated": bool(audio_data_url),
                "tts_method": tts_method,
                "edge_tts_available": EDGE_TTS_AVAILABLE,
                "text_length": len(ai_response_text),
                "turn_count": current_turn_count + 1,
                "conversation_context_length": len(context_str),
                "ai_initialized": AI_INITIALIZED
            }
        }
        
        logger.info(f"AI response sent: audio={tts_method}, turn={current_turn_count + 1}, duration={interview_duration:.1f}min")
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.exception("AI interaction API failed")
        return JsonResponse({
            'error': 'An unexpected error occurred. Please try again.',
            'debug_info': {'exception': str(e)}
        }, status=500)

@login_required
@user_passes_test(is_student, login_url='/login/')
def my_mock_interviews(request):
    """Display user's interview sessions with enhanced error handling."""
    try:
        sessions = MockInterviewSession.objects.filter(user=request.user).order_by('-start_time')
        
        # Add performance metrics to each session
        for session in sessions:
            feedback_data = None
            feedback_source = None
            
            if hasattr(session, 'ai_feedback') and session.ai_feedback:
                feedback_source = session.ai_feedback
            elif hasattr(session, 'overall_feedback') and session.overall_feedback:
                feedback_source = session.overall_feedback

            if feedback_source:
                try:
                    feedback_data = json.loads(feedback_source)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Failed to parse feedback for session {session.id}: {e}")
            
            if feedback_data:
                session.performance_score = feedback_data.get('overall_score', 'N/A')
                session.confidence_level = feedback_data.get('confidence_level', 'N/A')
                session.communication_score = feedback_data.get('communication_score', 'N/A')
                session.authenticity_score = feedback_data.get('authenticity_score', 'N/A')
            else:
                session.performance_score = 'Pending'
                session.confidence_level = 'Pending'
                session.communication_score = 'Pending'
                session.authenticity_score = 'Pending'
            
            # Calculate interview duration
            if session.start_time and session.end_time:
                duration = session.end_time - session.start_time
                duration_minutes = duration.total_seconds() / 60
                
                # Format duration nicely
                if duration_minutes < 1:
                    session.duration_display = f"{int(duration.total_seconds())} seconds"
                elif duration_minutes < 60:
                    session.duration_display = f"{int(duration_minutes)} min"
                else:
                    hours = int(duration_minutes // 60)
                    minutes = int(duration_minutes % 60)
                    session.duration_display = f"{hours}h {minutes}min"
                    
                session.duration_minutes = round(duration_minutes, 1)
            else:
                # Try to calculate from last turn if end_time is missing
                last_turn = session.turns.order_by('-timestamp').first()
                if last_turn and session.start_time:
                    duration = last_turn.timestamp - session.start_time
                    duration_minutes = duration.total_seconds() / 60
                    
                    if duration_minutes < 1:
                        session.duration_display = f"{int(duration.total_seconds())} seconds"
                    elif duration_minutes < 60:
                        session.duration_display = f"{int(duration_minutes)} min"
                    else:
                        hours = int(duration_minutes // 60)
                        minutes = int(duration_minutes % 60)
                        session.duration_display = f"{hours}h {minutes}min"
                        
                    session.duration_minutes = round(duration_minutes, 1)
                else:
                    session.duration_display = None
                    session.duration_minutes = 'N/A'
                
            # Add turn count
            session.total_questions = session.turns.count()
            
            # Pre-process key_skills as a list
            if session.key_skills:
                session.skills_list = [skill.strip() for skill in session.key_skills.split(',')]
            else:
                session.skills_list = []
        
        return render(request, 'mock_interview/my_mock_interviews.html', {'sessions': sessions})
        
    except Exception as e:
        logger.exception("Error loading mock interviews: %s", e)
        messages.error(request, "Failed to load your interview sessions.")
        return redirect('mock_interview:interview_setup')

@login_required
@user_passes_test(is_student, login_url='/login/')
def review_interview(request, session_id):
    """Review completed interview with GUARANTEED proper feedback parsing."""
    try:
        session = get_object_or_404(MockInterviewSession, id=session_id, user=request.user)
        turns = session.turns.all().order_by('turn_number')
        
        # Allow viewing even if status is STARTED
        if turns.count() == 0:
            messages.info(request, "This interview hasn't been started yet.")
            return redirect('mock_interview:main_interview', session_id=session.id)
        
        # Auto-complete if needed
        if session.status == 'STARTED' and turns.count() > 0:
            completed_turns = turns.filter(user_answer__isnull=False).count()
            if completed_turns >= 3:
                logger.info(f"Auto-updating session {session.id} status from STARTED to COMPLETED")
                session.status = 'COMPLETED'
                if not session.end_time:
                    session.end_time = timezone.now()
                session.save()
        
        # ===== ROBUST FEEDBACK PARSING =====
        ai_feedback = None
        feedback_source = None
        
        # Try to get feedback from available fields
        if hasattr(session, 'ai_feedback') and session.ai_feedback:
            feedback_source = session.ai_feedback
            logger.info(f"Found ai_feedback field for session {session.id}")
        elif hasattr(session, 'overall_feedback') and session.overall_feedback:
            feedback_source = session.overall_feedback
            logger.info(f"Found overall_feedback field for session {session.id}")

        # Parse the feedback with robust error handling
        if feedback_source:
            # Check if it's already a string that looks like JSON
            if isinstance(feedback_source, str):
                try:
                    # Try to parse as JSON
                    ai_feedback = json.loads(feedback_source)
                    logger.info(f"Successfully parsed JSON feedback for session {session.id}")
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parsing failed for session {session.id}: {e}")
                    logger.warning(f"Feedback content starts with: {feedback_source[:200]}")
                    
                    # Check if the string starts with triple backticks (markdown code block)
                    if feedback_source.strip().startswith('```'):
                        # Extract JSON from markdown code block
                        try:
                            json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', feedback_source)
                            if json_match:
                                ai_feedback = json.loads(json_match.group(1))
                                logger.info("Extracted JSON from markdown code block")
                        except:
                            pass
                    
                    # If still no valid JSON, this is raw JSON text that needs regeneration
                    if not ai_feedback:
                        logger.error(f"Feedback is not valid JSON. Will regenerate.")
                        feedback_source = None  # Force regeneration
            elif isinstance(feedback_source, dict):
                # Already a dictionary
                ai_feedback = feedback_source
                logger.info(f"Feedback is already a dict for session {session.id}")
        
        # If no valid feedback, generate it now
        if not ai_feedback:
            logger.warning(f"No valid feedback found for session {session.id}, generating now...")
            try:
                performance_analysis_json = analyze_interview_performance(session)
                
                # Try to parse the generated analysis
                if performance_analysis_json:
                    try:
                        ai_feedback = json.loads(performance_analysis_json)
                        
                        # Save it back to the session
                        if hasattr(session, 'ai_feedback'):
                            session.ai_feedback = performance_analysis_json
                        else:
                            session.overall_feedback = performance_analysis_json
                        session.save()
                        logger.info(f"Generated and saved new feedback for session {session.id}")
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"Generated feedback is not valid JSON: {e}")
                        logger.error(f"Response was: {performance_analysis_json[:500]}")
                        # Will fall through to emergency fallback
                        
            except Exception as e:
                logger.error(f"Emergency feedback generation failed: {e}")
        
        # ABSOLUTE FALLBACK - Always ensure ai_feedback exists with proper structure
        if not ai_feedback or not isinstance(ai_feedback, dict):
            logger.warning(f"Using emergency fallback feedback for session {session.id}")
            ai_feedback = {
                'overall_score': 70,
                'strengths': [
                    'Successfully completed the mock interview session',
                    'Engaged with the AI interviewer throughout the session',
                    'Demonstrated willingness to practice and improve'
                ],
                'areas_for_improvement': [
                    'Continue practicing mock interviews regularly',
                    'Focus on providing detailed, structured responses',
                    'Prepare specific examples from your experience using the STAR method'
                ],
                'technical_assessment': f'You discussed skills relevant to the {session.job_role} position. To strengthen your technical profile, continue building expertise in: {session.key_skills}. Practice explaining technical concepts clearly and be ready to discuss specific projects where you applied these skills.',
                'communication_score': 70,
                'confidence_level': 'Developing',
                'recommendations': [
                    'Practice the STAR method (Situation, Task, Action, Result) for behavioral questions',
                    'Prepare 3-5 specific examples from your past work experience',
                    'Research common interview questions for your target role',
                    'Record yourself answering questions to improve delivery',
                    'Practice speaking at a measured, confident pace'
                ],
                'encouragement_note': 'You took an important step by completing this mock interview! Every practice session helps you improve. Keep working on your interview skills, prepare thoroughly, and you\'ll see great progress. Remember, confidence comes from preparation and practice!'
            }
        
        # Ensure all required keys exist with proper defaults
        ai_feedback = {
            'overall_score': ai_feedback.get('overall_score', 70),
            'strengths': ai_feedback.get('strengths', ['Completed the interview session']),
            'areas_for_improvement': ai_feedback.get('areas_for_improvement', ['Continue practicing interview skills']),
            'technical_assessment': ai_feedback.get('technical_assessment', f'Technical skills assessment for {session.job_role} position.'),
            'communication_score': ai_feedback.get('communication_score', 70),
            'confidence_level': ai_feedback.get('confidence_level', 'Good'),
            'recommendations': ai_feedback.get('recommendations', ['Keep practicing mock interviews']),
            'encouragement_note': ai_feedback.get('encouragement_note', 'Great job completing the interview! Keep practicing to improve.')
        }
        
        # Ensure all values are proper types (not nested JSON strings)
        for key in ['strengths', 'areas_for_improvement', 'recommendations']:
            if isinstance(ai_feedback[key], str):
                try:
                    ai_feedback[key] = json.loads(ai_feedback[key])
                except:
                    ai_feedback[key] = [ai_feedback[key]]  # Wrap single string in list
            elif not isinstance(ai_feedback[key], list):
                ai_feedback[key] = [str(ai_feedback[key])]
        
        # Calculate score for visual display
        score_deg = 0
        try:
            score = ai_feedback.get('overall_score', 70)
            if isinstance(score, (int, float)):
                session.score = score
                score_deg = score * 3.6
        except:
            score_deg = 70 * 3.6
        
        # Calculate interview metrics
        interview_duration = None
        total_words = 0
        confidence_indicators = []
        engagement_indicators = []
        
        if session.start_time and session.end_time:
            duration = session.end_time - session.start_time
            interview_duration = duration.total_seconds() / 60
        elif session.start_time:
            last_turn = turns.order_by('-timestamp').first()
            if last_turn:
                duration = last_turn.timestamp - session.start_time
                interview_duration = duration.total_seconds() / 60
        
        for turn in turns:
            if turn.user_answer:
                words = len(turn.user_answer.split())
                total_words += words
                
                # Confidence indicators
                if words > 50:
                    confidence_indicators.append('detailed_responses')
                if any(word in turn.user_answer.lower() for word in ['achieved', 'led', 'managed', 'created', 'developed', 'implemented']):
                    confidence_indicators.append('action_words')
                if any(phrase in turn.user_answer.lower() for phrase in ['i believe', 'i think', 'in my experience', 'i learned']):
                    confidence_indicators.append('personal_ownership')
                
                # Engagement indicators
                if any(word in turn.user_answer.lower() for word in ['excited', 'passionate', 'enjoy', 'love', 'motivated']):
                    engagement_indicators.append('enthusiasm')
                if '?' in turn.user_answer:
                    engagement_indicators.append('curious')
        
        avg_response_length = total_words / max(turns.count(), 1)
        confidence_score = min(100, len(set(confidence_indicators)) * 25)
        engagement_score = min(100, len(set(engagement_indicators)) * 30)
        
        context = {
            'session': session,
            'turns': turns,
            'ai_feedback': ai_feedback,  # GUARANTEED to be a proper dict
            'transcript': session.turns.all(),
            'score_deg': score_deg,
            'interview_metrics': {
                'duration_minutes': round(interview_duration, 1) if interview_duration else None,
                'total_questions': turns.count(),
                'total_words': total_words,
                'avg_response_length': round(avg_response_length, 1),
                'confidence_score': confidence_score,
                'engagement_score': engagement_score,
                'tts_enhanced': EDGE_TTS_AVAILABLE
            }
        }
        
        logger.info(f"Successfully loaded review for session {session.id} with feedback keys: {list(ai_feedback.keys())}")
        return render(request, 'mock_interview/review_interview.html', context)
        
    except Exception as e:
        logger.exception("Error loading interview review: %s", e)
        messages.error(request, "Failed to load interview review.")
        return redirect('mock_interview:my_mock_interviews')

@login_required
@user_passes_test(is_student, login_url='/login/')
def delete_session(request, session_id):
    """Delete a specific interview session."""
    try:
        session = get_object_or_404(MockInterviewSession, id=session_id, user=request.user)
        session_job_role = session.job_role
        session.delete()
        
        messages.success(request, f'Interview session for {session_job_role} has been deleted successfully.')
        logger.info(f"User {request.user.id} deleted interview session {session_id}")
        
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}")
        messages.error(request, 'Failed to delete the interview session. Please try again.')
    
    return redirect('mock_interview:my_mock_interviews')

@login_required
@user_passes_test(is_student, login_url='/login/')
def clear_all_sessions(request):
    """Clear all interview sessions for the current user."""
    if request.method == 'POST':
        try:
            sessions_count = MockInterviewSession.objects.filter(user=request.user).count()
            MockInterviewSession.objects.filter(user=request.user).delete()
            
            messages.success(request, f'All {sessions_count} interview sessions have been cleared successfully.')
            logger.info(f"User {request.user.id} cleared all {sessions_count} interview sessions")
            
        except Exception as e:
            logger.error(f"Error clearing all sessions for user {request.user.id}: {e}")
            messages.error(request, 'Failed to clear interview sessions. Please try again.')
    else:
        messages.warning(request, 'Invalid request method for clearing sessions.')
    
    return redirect('mock_interview:my_mock_interviews')

@login_required
@user_passes_test(is_student, login_url='/login/')
@csrf_exempt
def get_interview_hints_api(request, session_id):
    """
    Enhanced API endpoint to provide contextual interview hints based on current question and user progress.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required.'}, status=405)
    
    try:
        session = get_object_or_404(MockInterviewSession, id=session_id, user=request.user)
        
        # Parse request data
        try:
            payload = json.loads(request.body)
            current_question = payload.get('current_question', 1)
            chat_history = payload.get('chat_history', [])
            session_context = payload.get('session_context', {})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)
        
        # Get the latest AI question for context
        latest_turn = session.turns.filter(ai_question__isnull=False).order_by('-turn_number').first()
        current_ai_question = latest_turn.ai_question if latest_turn else ""
        
        # Build context for hint generation
        hint_context = f"""
        You are an expert interview coach providing strategic guidance.
        
        Interview Context:
        - Position: {session.job_role}
        - Key Skills: {session.key_skills}
        - Current Question Number: {current_question}
        - User's Progress: {session_context.get('total_responses', 0)} responses given
        
        Current AI Question: "{current_ai_question}"
        
        Recent Conversation Context:
        {get_recent_conversation_context(chat_history[-6:])}
        
        Provide 4-5 strategic, actionable hints that will help the candidate excel at this specific question.
        Focus on:
        1. Specific techniques for this type of question
        2. What interviewers are looking for
        3. Common mistakes to avoid
        4. How to structure the response
        5. Ways to make their answer stand out
        
        Return ONLY a JSON array of hints with this exact format:
        [
            {{
                "title": "Specific Technique Name",
                "description": "Detailed, actionable advice that directly helps with this question type."
            }},
            ...
        ]
        
        Make hints specific to the current question context, not generic interview advice.
        """
        
        hints_response = "" # Initialize
        try:
            # Generate contextual hints using AI
            hints_response = call_ai_model(
                hint_context, 
                model_type="text", 
                max_tokens=800, 
                temperature=0.7
            )
            
            if not hints_response:
                raise Exception("No response from AI model")
            
            # Try to parse the AI response as JSON
            hints_data = extract_json_from_response(hints_response)
            
            if not hints_data:
                # Fallback to default hints based on question number
                logger.warning("Failed to parse AI hints JSON, using fallback.")
                hints_data = get_default_hints_for_stage(current_question)
                
        except Exception as e:
            logger.warning(f"Failed to generate AI hints: {e}")
            hints_data = get_default_hints_for_stage(current_question)
        
        return JsonResponse({
            'success': True,
            'hints': hints_data,
            'context': {
                'question_number': current_question,
                'interview_stage': get_interview_stage(current_question),
                'generated_method': 'ai' if hints_response and hints_data else 'fallback'
            }
        })
        
    except Exception as e:
        logger.exception(f"Interview hints API error: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to generate interview hints. Please try again.',
            'hints': get_emergency_hints()
        }, status=500)

@login_required
@user_passes_test(is_student, login_url='/login/')
@csrf_exempt
def practice_question_api(request, session_id):
    """
    API endpoint to provide practice questions for interview preparation.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required.'}, status=405)
    
    try:
        session = get_object_or_404(MockInterviewSession, id=session_id, user=request.user)
        
        # Parse request data
        try:
            payload = json.loads(request.body)
            question_type = payload.get('question_type', 'general')
            difficulty = payload.get('difficulty', 'medium')
            focus_area = payload.get('focus_area', session.key_skills)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)
        
        # Build context for practice question generation
        practice_context = f"""
        You are an expert interview coach creating practice questions.
        
        Context:
        - Position: {session.job_role}
        - Key Skills: {session.key_skills}
        - Question Type: {question_type}
        - Difficulty Level: {difficulty}
        - Focus Area: {focus_area}
        
        Generate 3-5 high-quality practice questions that would help someone prepare for a {session.job_role} interview.
        
        Include a mix of:
        - Technical questions (if applicable)
        - Behavioral questions using STAR method
        - Situational questions
        - Role-specific questions
        
        Return ONLY a JSON object with this exact format:
        {{
            "questions": [
                {{
                    "id": 1,
                    "question": "The actual interview question",
                    "type": "behavioral|technical|situational|general",
                    "difficulty": "easy|medium|hard",
                    "focus_skill": "specific skill this tests",
                    "tips": "Brief tip on how to approach this question"
                }},
                ...
            ],
            "total_count": 5
        }}
        
        Make questions realistic and relevant to the specific role and skills.
        """
        
        questions_response = "" # Initialize
        try:
            # Generate practice questions using AI
            questions_response = call_ai_model(
                practice_context, 
                model_type="text", 
                max_tokens=1000, 
                temperature=0.8
            )
            
            if not questions_response:
                raise Exception("No response from AI model")
            
            # Try to parse the AI response as JSON
            questions_data = extract_json_from_response(questions_response)
            
            if not questions_data or 'questions' not in questions_data:
                # Fallback to default questions
                logger.warning("Failed to parse AI practice questions, using fallback.")
                questions_data = get_default_practice_questions(session.job_role, session.key_skills)
                
        except Exception as e:
            logger.warning(f"Failed to generate AI practice questions: {e}")
            questions_data = get_default_practice_questions(session.job_role, session.key_skills)
        
        return JsonResponse({
            'success': True,
            'practice_questions': questions_data,
            'metadata': {
                'session_id': session_id,
                'job_role': session.job_role,
                'generated_method': 'ai' if questions_response and questions_data else 'fallback'
            }
        })
        
    except Exception as e:
        logger.exception(f"Practice questions API error: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to generate practice questions. Please try again.',
            'practice_questions': get_emergency_practice_questions()
        }, status=500)

@csrf_exempt
def ai_health_check(request):
    """Enhanced health check with detailed diagnostics."""
    health_status = {
        'ai_provider': AI_PROVIDER,
        'ai_initialized': AI_INITIALIZED,
        'text_generation': False,
        'tts_generation': False,
        'edge_tts_available': EDGE_TTS_AVAILABLE,
        'edge_tts_functional': False,
        'gtts_available': True,
        'gtts_functional': False,
        'timestamp': timezone.now().isoformat(),
        'edge_tts_voice': SARAH_VOICE,
        'api_keys_configured': {
            'gemini': bool(GEMINI_API_KEY),
            'openai': bool(OPENAI_API_KEY)
        }
    }
    
    # Test text generation
    try:
        test_response = call_ai_model("Say 'Hello, this is a test!'", model_type="text", max_tokens=50)
        health_status['text_generation'] = bool(test_response and len(test_response.strip()) > 0)
        
        if health_status['text_generation']:
            test_text = "Testing audio generation."
            
            # Test edge-tts
            if EDGE_TTS_AVAILABLE:
                try:
                    edge_result = call_ai_model(test_text, model_type="edge_tts")
                    health_status['edge_tts_functional'] = bool(edge_result.get("audio_url"))
                except Exception as e:
                    logger.warning(f"edge-tts health check failed: {e}")
            
            # Test gTTS
            try:
                gtts_result = call_ai_model(test_text, model_type="gtts")
                health_status['gtts_functional'] = bool(gtts_result.get("audio_url"))
            except Exception as e:
                logger.warning(f"gTTS health check failed: {e}")
                
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        health_status['error'] = str(e)
    
    # Determine overall health
    primary_tts_working = health_status['edge_tts_functional'] if EDGE_TTS_AVAILABLE else health_status['gtts_functional']
    overall_healthy = health_status['text_generation'] and primary_tts_working
    
    status_code = 200 if overall_healthy else 503
    health_status['overall_status'] = 'healthy' if overall_healthy else 'degraded'
    health_status['recommendations'] = []
    
    if not health_status['text_generation']:
        health_status['recommendations'].append('Check AI provider API keys')
    if not primary_tts_working:
        health_status['recommendations'].append('Check TTS service configuration')
    if not AI_INITIALIZED:
        health_status['recommendations'].append('Verify API key validity and network connection')
    
    return JsonResponse(health_status, status=status_code)

