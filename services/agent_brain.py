import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from services.groq_service import groq_service

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "candidates.json"

class AgentBrain:
    def __init__(self):
        self.data = self._load_data()
        self.company = self.data.get("company", {})
        self.candidates = self.data.get("candidates", [])
        self.sessions: Dict[str, List[Dict[str, str]]] = {}

    def _load_data(self) -> Dict[str, Any]:
        try:
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load candidate database: {e}")
            return {"company": {}, "candidates": []}

    def get_all_candidates(self) -> List[Dict[str, Any]]:
        return self.candidates

    def find_candidate(self, query: str) -> Optional[Dict[str, Any]]:
        q = query.lower().strip()
        for cand in self.candidates:
            if cand["id"].lower() == q or q in cand["id"].lower():
                return cand
            if cand["name"].lower() in q or q in cand["name"].lower():
                return cand
            for alias in cand.get("aliases", []):
                if alias.lower() in q:
                    return cand
        return None

    def build_system_prompt(self, relevant_candidate: Optional[Dict[str, Any]] = None) -> str:
        prompt = """You are the phone verification agent for Astra AI, an AI education platform.
You are speaking live to an HR or background verifier on a telephone call.
Speak naturally, warmly, politely, and concisely like a real human.

RULES:
1. INITIAL INQUIRY ABOUT DHAIRYASHIL SHINDE (Candidate ID: AST-AI-091):
   - State ONLY: "Candidate ID is AST-AI-091. Dhairyashil Shinde completed his internship at Astra AI starting from 1st September to 1st October 2026."
   - DO NOT state working hours, DO NOT state night meetings, and DO NOT state benchmarking in this first response!
   - ONLY IF the caller asks follow-up questions (such as "What were his hours?", "What did he work on?", "Tell me more about his role"):
     Then answer with:
     "His working hours were 10:00 AM to 3:00 PM Indian Standard Time, and he actively attended night sync meetings with global teams. He worked on AI internal concepts, specifically model benchmarking and evaluation pipelines."

2. OTHER CANDIDATES:
   - State Candidate ID first, then the basic verified internship dates. Only share further details if asked.

3. UNKNOWN PERSON:
   - If someone asks about a name not in our registry: "I don't have a record for that name in our verification database. Could you provide their Candidate ID?"

4. ABOUT ASTRA AI:
   - "Astra AI is an AI study platform helping students prepare for exams using notes, PDFs, and past papers through AI tutoring, quizzes, flashcards, podcasts, and mock exams."

5. STYLE:
   - Keep answers strictly to 1 or 2 conversational sentences.
   - Do NOT say "Welcome to Astra AI" if the caller has already asked a question.
   - Speak like a friendly human representative. Never use bullet points, asterisks, or robotic formatting.
"""
        if relevant_candidate:
            prompt += f"\nMATCHED CANDIDATE FILE:\nName: {relevant_candidate['name']}\nID: {relevant_candidate['id']}\nPeriod: {relevant_candidate.get('period', '')}\nHours: {relevant_candidate.get('working_hours', '')}\nNight Meetings: {relevant_candidate.get('night_meetings', '')}\nDomain: {relevant_candidate.get('technical_domain', '')}\n"
        return prompt

    def clean_text_for_speech(self, text: str) -> str:
        """Strips markdown and formats text for natural speech."""
        cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
        cleaned = re.sub(r"^#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^\s*[-*•]\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.replace("`", "")
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
        cleaned = re.sub(r"\n+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def process_turn(self, session_id: str, user_speech: str) -> str:
        """Processes a single conversational turn."""
        speech = user_speech.strip()
        if not speech:
            return "Welcome to Astra AI. How can I help you today?"

        if session_id not in self.sessions:
            self.sessions[session_id] = []

        history = self.sessions[session_id]
        matched_cand = self.find_candidate(speech)
        system_prompt = self.build_system_prompt(matched_cand)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-8:])
        messages.append({"role": "user", "content": speech})

        try:
            raw_response = groq_service.get_completion(messages, temperature=0.3, max_tokens=150)
            cleaned = self.clean_text_for_speech(raw_response)
        except Exception as e:
            logger.error(f"Groq completion error: {e}")
            cleaned = "I'm sorry, I missed that. Could you please repeat the candidate's name or Candidate ID?"

        history.append({"role": "user", "content": speech})
        history.append({"role": "assistant", "content": cleaned})
        self.sessions[session_id] = history

        return cleaned

    def reset_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]

agent_brain = AgentBrain()
