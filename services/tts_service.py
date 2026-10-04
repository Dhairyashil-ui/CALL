import os
import hashlib
import logging
from pathlib import Path
from typing import Optional
import edge_tts

logger = logging.getLogger(__name__)

AUDIO_DIR = Path(__file__).resolve().parent.parent / "static" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_VOICE = os.getenv("EDGE_VOICE", "en-US-JennyNeural")

class TTSService:
    def __init__(self, voice: str = DEFAULT_VOICE):
        self.voice = voice
        self.audio_dir = AUDIO_DIR
        self.welcome_filename = "welcome.mp3"

    async def generate_audio_async(self, text: str) -> Optional[str]:
        """
        Synthesizes text using Microsoft Edge Neural TTS.
        Returns the filename (e.g. 'abc123.mp3') stored in static/audio.
        """
        cleaned = text.strip()
        if not cleaned:
            return None

        # Check for welcome text match
        if "welcome to astra ai" in cleaned.lower() and "how can i help" in cleaned.lower():
            welcome_path = self.audio_dir / self.welcome_filename
            if welcome_path.exists() and welcome_path.stat().st_size > 500:
                return self.welcome_filename

        # Hash text + voice to avoid re-generating identical audio
        text_hash = hashlib.md5(f"{self.voice}:{cleaned}".encode("utf-8")).hexdigest()
        filename = f"{text_hash}.mp3"
        filepath = self.audio_dir / filename

        if filepath.exists() and filepath.stat().st_size > 500:
            return filename

        try:
            communicate = edge_tts.Communicate(cleaned, voice=self.voice)
            await communicate.save(str(filepath))
            if filepath.exists() and filepath.stat().st_size > 500:
                return filename
        except Exception as e:
            logger.error(f"Edge-TTS synthesis error for '{cleaned[:40]}...': {e}")

        return None

tts_service = TTSService()
