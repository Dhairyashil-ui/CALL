import logging
from typing import Optional, Dict, Any
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather
from config import settings

logger = logging.getLogger(__name__)

class TwilioService:
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.phone_number = settings.TWILIO_PHONE_NUMBER
        self.voice = settings.TWILIO_VOICE

        self.client: Optional[Client] = None
        if self.account_sid and self.auth_token:
            try:
                self.client = Client(self.account_sid, self.auth_token)
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}")

    def get_account_status(self) -> Dict[str, Any]:
        if not self.client:
            return {"connected": False, "error": "Twilio client not initialized"}
        try:
            account = self.client.api.v2010.accounts(self.account_sid).fetch()
            numbers = self.client.incoming_phone_numbers.list(phone_number=self.phone_number)
            current_webhook = numbers[0].voice_url if numbers else "None"
            return {
                "connected": True,
                "account_name": account.friendly_name,
                "status": account.status,
                "phone_number": self.phone_number,
                "voice_webhook_url": current_webhook
            }
        except Exception as e:
            return {"connected": False, "error": str(e)}

    def update_voice_webhook(self, webhook_url: str) -> Dict[str, Any]:
        """Sets the Twilio incoming phone number's Voice Webhook URL automatically."""
        if not self.client:
            return {"success": False, "error": "Twilio client not initialized"}
        try:
            numbers = self.client.incoming_phone_numbers.list(phone_number=self.phone_number)
            if not numbers:
                return {"success": False, "error": f"Phone number {self.phone_number} not found in account"}

            target_sid = numbers[0].sid
            updated_number = self.client.incoming_phone_numbers(target_sid).update(
                voice_url=webhook_url,
                voice_method="POST"
            )
            logger.info(f"Updated Twilio Voice URL to: {webhook_url}")
            return {
                "success": True,
                "phone_number": updated_number.phone_number,
                "new_voice_url": updated_number.voice_url
            }
        except Exception as e:
            logger.error(f"Failed to update Twilio webhook: {e}")
            return {"success": False, "error": str(e)}

    def make_outbound_call(self, to_phone_number: str, base_url: str) -> Dict[str, Any]:
        """Initiates an outbound phone call connecting the recipient to the Astra AI verification agent."""
        if not self.client:
            return {"success": False, "error": "Twilio client not initialized"}

        webhook_url = f"{base_url.rstrip('/')}/voice/incoming"
        try:
            call = self.client.calls.create(
                to=to_phone_number,
                from_=self.phone_number,
                url=webhook_url,
                record=False
            )
            return {
                "success": True,
                "call_sid": call.sid,
                "status": call.status,
                "to": to_phone_number,
                "from": self.phone_number
            }
        except Exception as e:
            logger.error(f"Failed to make outbound call to {to_phone_number}: {e}")
            return {"success": False, "error": str(e)}

    def build_initial_greeting_twiml(self, action_url: str, audio_url: Optional[str] = None) -> str:
        """Constructs initial TwiML greeting using Microsoft Edge Neural Voice or Say fallback."""
        response = VoiceResponse()
        gather = Gather(
            input="speech",
            action=action_url,
            method="POST",
            speech_timeout="auto",
            language="en-US"
        )
        if audio_url:
            gather.play(audio_url)
        else:
            gather.say("Welcome to Astra AI. How can I help you today?", voice=self.voice)
        response.append(gather)

        # Fallback if caller is silent
        response.say("We did not detect any speech. Please call back whenever you are ready. Goodbye.", voice=self.voice)
        response.hangup()
        return str(response)

    def build_conversation_turn_twiml(
        self,
        agent_speech: str,
        action_url: str,
        audio_url: Optional[str] = None,
        is_goodbye: bool = False
    ) -> str:
        """Constructs ongoing TwiML speech response + next Gather using Edge TTS audio."""
        response = VoiceResponse()
        if is_goodbye:
            if audio_url:
                response.play(audio_url)
            else:
                response.say(agent_speech, voice=self.voice)
            response.hangup()
            return str(response)

        gather = Gather(
            input="speech",
            action=action_url,
            method="POST",
            speech_timeout="auto",
            language="en-US"
        )
        if audio_url:
            gather.play(audio_url)
        else:
            gather.say(agent_speech, voice=self.voice)
        response.append(gather)

        # Reprompt if no speech
        gather_retry = Gather(
            input="speech",
            action=action_url,
            method="POST",
            speech_timeout="auto",
            language="en-US"
        )
        gather_retry.say("Is there any other candidate or detail you would like to verify?", voice=self.voice)
        response.append(gather_retry)

        response.say("Thank you for contacting Astra AI Verification. Goodbye.", voice=self.voice)
        response.hangup()
        return str(response)

twilio_service = TwilioService()
