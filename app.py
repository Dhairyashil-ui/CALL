import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from fastapi import FastAPI, Request, Form, Response, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

from config import settings
from services.agent_brain import agent_brain
from services.twilio_service import twilio_service
from services.tts_service import tts_service
from services.groq_service import groq_service

# Setup production logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("astra_production_app")

app = FastAPI(
    title="Astra AI — Job Verification Voice Agent",
    description="Production voice calling agent powered by Twilio, Groq, and Microsoft Edge Neural TTS",
    version="2.0.0"
)

AUDIO_DIR = Path(__file__).resolve().parent / "static" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

class OutboundCallRequest(BaseModel):
    to_phone: str

class WebhookUpdateRequest(BaseModel):
    public_url: str

def get_base_url(request: Request) -> str:
    """Detects public base URL automatically, supporting Render and local tunnels."""
    # 1. Render environment variable
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        return render_url.rstrip("/")

    # 2. X-Forwarded headers (behind reverse proxy)
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_proto and forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}".rstrip("/")

    # 3. Configured base URL or request base URL
    if settings.BASE_URL and "localhost" not in settings.BASE_URL:
        return settings.BASE_URL.rstrip("/")

    return str(request.base_url).rstrip("/")

# ----------------- PRODUCTION API ENDPOINTS -----------------

@app.get("/")
@app.get("/health")
async def health_check(request: Request):
    """Production health check endpoint for Render and monitoring."""
    base_url = get_base_url(request)
    return {
        "service": "Astra AI Job & Talent Verification Agent",
        "status": "healthy",
        "company": agent_brain.company.get("name", "Astra AI"),
        "voice_engine": f"Microsoft Edge Neural TTS ({tts_service.voice})",
        "llm_model": groq_service._active_model or settings.GROQ_MODEL,
        "twilio_phone_number": settings.TWILIO_PHONE_NUMBER,
        "base_url": base_url,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/audio/{filename}")
async def serve_audio(filename: str):
    """Serves synthesized Microsoft Edge Neural TTS MP3 audio to Twilio."""
    file_path = AUDIO_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(file_path, media_type="audio/mpeg")

@app.get("/api/candidates")
async def get_candidates():
    """Returns candidate records."""
    return {
        "company": agent_brain.company,
        "candidates": agent_brain.get_all_candidates()
    }

@app.post("/api/make-call")
async def trigger_outbound_call(payload: OutboundCallRequest, request: Request):
    """Places an outbound verification call to any phone number."""
    to_phone = payload.to_phone.strip()
    if not to_phone:
        return JSONResponse(status_code=400, content={"error": "to_phone is required"})

    base_url = get_base_url(request)
    result = twilio_service.make_outbound_call(to_phone, base_url)
    if not result.get("success"):
        return JSONResponse(status_code=500, content=result)
    return result

@app.post("/api/set-webhook")
async def update_webhook_endpoint(payload: WebhookUpdateRequest):
    """Updates Twilio incoming phone number voice webhook automatically."""
    public_url = payload.public_url.strip().rstrip("/")
    if not public_url:
        return JSONResponse(status_code=400, content={"error": "public_url is required"})

    full_webhook_url = f"{public_url}/voice/incoming"
    return twilio_service.update_voice_webhook(full_webhook_url)

# ----------------- TWILIO VOICE WEBHOOKS -----------------

@app.post("/voice/incoming")
async def twilio_incoming_call(request: Request):
    """
    Called when a call is connected.
    First greeting: 'Welcome to Astra AI. How can I help you today?'
    Spoken in human-like Microsoft Edge Neural voice.
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "default-call")
    from_number = form_data.get("From", "Unknown")
    
    logger.info(f"Call connected: CallSid={call_sid}, From={from_number}")
    agent_brain.reset_session(call_sid)

    base_url = get_base_url(request)
    audio_url = f"{base_url}/audio/{tts_service.welcome_filename}"
    process_url = f"{base_url}/voice/process?call_sid={call_sid}"

    twiml_xml = twilio_service.build_initial_greeting_twiml(
        action_url=process_url,
        audio_url=audio_url
    )
    return Response(content=twiml_xml, media_type="application/xml")

@app.post("/voice/process")
async def twilio_process_speech(request: Request):
    """
    Called when caller finishes speaking.
    Processes user speech with Groq LLM and plays back Microsoft Edge Neural TTS audio.
    """
    form_data = await request.form()
    speech_result = form_data.get("SpeechResult", "").strip()
    call_sid = request.query_params.get("call_sid") or form_data.get("CallSid", "default-call")
    base_url = get_base_url(request)

    logger.info(f"Speech received for {call_sid}: '{speech_result}'")

    if not speech_result:
        fallback_msg = "I didn't catch that. Could you please state the candidate name or Candidate ID you would like to verify?"
        audio_filename = await tts_service.generate_audio_async(fallback_msg)
        audio_url = f"{base_url}/audio/{audio_filename}" if audio_filename else None
        
        twiml_xml = twilio_service.build_conversation_turn_twiml(
            agent_speech=fallback_msg,
            action_url=f"{base_url}/voice/process?call_sid={call_sid}",
            audio_url=audio_url
        )
        return Response(content=twiml_xml, media_type="application/xml")

    # Check for exit intent
    exit_phrases = ["goodbye", "bye", "that is all", "that's all", "nothing else", "hang up", "thank you bye"]
    is_exit = any(p in speech_result.lower() for p in exit_phrases)

    if is_exit:
        goodbye_msg = "You are welcome. Have a wonderful day. Goodbye."
        audio_filename = await tts_service.generate_audio_async(goodbye_msg)
        audio_url = f"{base_url}/audio/{audio_filename}" if audio_filename else None
        
        twiml_xml = twilio_service.build_conversation_turn_twiml(
            agent_speech=goodbye_msg,
            action_url="",
            audio_url=audio_url,
            is_goodbye=True
        )
        return Response(content=twiml_xml, media_type="application/xml")

    # Generate answer with Groq
    agent_reply = agent_brain.process_turn(call_sid, speech_result)
    logger.info(f"Agent response: '{agent_reply}'")

    # Synthesize with Microsoft Edge Neural TTS
    audio_filename = await tts_service.generate_audio_async(agent_reply)
    audio_url = f"{base_url}/audio/{audio_filename}" if audio_filename else None

    twiml_xml = twilio_service.build_conversation_turn_twiml(
        agent_speech=agent_reply,
        action_url=f"{base_url}/voice/process?call_sid={call_sid}",
        audio_url=audio_url
    )
    return Response(content=twiml_xml, media_type="application/xml")

@app.post("/voice/status")
async def twilio_call_status(request: Request):
    """Twilio call completion webhook."""
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")
    duration = form_data.get("CallDuration")
    logger.info(f"Call {call_sid} ended with status: {call_status} (duration: {duration}s)")
    return Response(content="<Response/>", media_type="application/xml")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", settings.PORT))
    logger.info(f"Starting Astra AI Voice Agent on port {port}...")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
