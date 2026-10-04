import re
import sys
import time
import subprocess
import requests
from pathlib import Path
from config import settings
from services.twilio_service import twilio_service

def find_cloudflared_url(process):
    """Monitors cloudflared stderr output to capture the public URL."""
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    start_time = time.time()
    
    print("[*] Waiting for Cloudflare Tunnel public URL...")
    while time.time() - start_time < 30:
        line = process.stdout.readline()
        if not line:
            time.sleep(0.1)
            continue
        line_str = line.strip()
        if "trycloudflare.com" in line_str or "Infra" in line_str:
            print(f"  [cloudflared] {line_str}")
        
        match = url_pattern.search(line_str)
        if match:
            return match.group(0)
    return None

def main():
    port = settings.PORT
    print("=" * 65)
    print("      ASTRA AI - TWILIO VOICE TUNNEL CONNECTOR")
    print("=" * 65)
    print(f"Local Server Target: http://localhost:{port}")
    print(f"Twilio Phone Number: {settings.TWILIO_PHONE_NUMBER}")
    print("-" * 65)

    # Launch cloudflared
    try:
        proc = subprocess.Popen(
            ["cloudflared.exe", "tunnel", "--url", f"http://localhost:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True
        )
    except FileNotFoundError:
        print("[!] cloudflared.exe not found, trying ngrok...")
        try:
            proc = subprocess.Popen(
                ["ngrok.exe", "http", str(port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            time.sleep(3)
            # Fetch URL from ngrok local API
            try:
                tunnels = requests.get("http://127.0.0.1:4040/api/tunnels").json()
                public_url = tunnels["tunnels"][0]["public_url"]
            except Exception as e:
                print(f"[!] Could not get ngrok URL: {e}")
                sys.exit(1)
        except FileNotFoundError:
            print("[X] Neither cloudflared nor ngrok was found in PATH.")
            sys.exit(1)
    else:
        public_url = find_cloudflared_url(proc)

    if not public_url:
        print("[X] Failed to obtain public tunnel URL.")
        sys.exit(1)

    print(f"\n[+] Public Tunnel Established: {public_url}")
    voice_webhook_url = f"{public_url}/voice/incoming"
    print(f"[+] Setting Twilio Phone Webhook to: {voice_webhook_url}")

    res = twilio_service.update_voice_webhook(voice_webhook_url)
    if res.get("success"):
        print("[SUCCESS] Twilio Phone Number +18023066611 is NOW CONNECTED to Astra AI Agent!")
        print(f"[+] Call +18023066611 from any mobile phone to test live!")
    else:
        print(f"[!] Warning: Could not update Twilio webhook automatically: {res.get('error')}")
        print(f"    Please set the Webhook in Twilio Console to: {voice_webhook_url}")

    print("\nTunnel is running. Press Ctrl+C to stop.")
    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\nStopping tunnel...")
        proc.terminate()

if __name__ == "__main__":
    main()
