import streamlit as st
from livekit import api
import os
import secrets
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Voice Agent UI", layout="centered")

st.title("🎙️ Talk to the AI Weather Agent")
st.markdown("This Streamlit app connects your browser directly to the LiveKit Voice Agent running securely on your backend.")

if "room_name" not in st.session_state:
    st.session_state.room_name = f"voice-room-{secrets.token_hex(4)}"
if "participant_name" not in st.session_state:
    st.session_state.participant_name = f"user-{secrets.token_hex(4)}"

# Get environment variables
url = os.getenv("LIVEKIT_URL")
api_key = os.getenv("LIVEKIT_API_KEY")
api_secret = os.getenv("LIVEKIT_API_SECRET")

if not url or not api_key or not api_secret:
    st.error("Missing LiveKit Environment Variables (LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET). Please check your .env file.")
    st.stop()

# Support wss:// or https:// conversion for token fetching if needed, but url is just passed to web
def generate_token(room_name: str, participant_name: str) -> str:
    token = api.AccessToken(api_key, api_secret)
    token.with_identity(participant_name)
    token.with_name("Human User")
    token.with_grants(api.VideoGrants(
        room_join=True,
        room=room_name,
    ))
    return token.to_jwt()

token = generate_token(st.session_state.room_name, st.session_state.participant_name)

st.info(f"Connecting to dynamically generated room: **{st.session_state.room_name}**")

html_code = f"""
<!DOCTYPE html>
<html>
<head>
    <!-- Use official LiveKit JS Client SDK from CDN -->
    <script src="https://cdn.jsdelivr.net/npm/livekit-client/dist/livekit-client.umd.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            text-align: center;
            padding: 20px;
            color: #ffffff;
            background-color: #0E1117;
            margin: 0;
        }}
        .button {{
            background-color: #FF4B4B;
            color: white;
            padding: 15px 32px;
            text-align: center;
            font-size: 16px;
            font-weight: 600;
            margin: 4px 2px;
            cursor: pointer;
            border: none;
            border-radius: 8px;
            transition: 0.3s;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .button:hover {{ background-color: #ff3333; transform: translateY(-1px); }}
        .button:disabled {{ background-color: #555; cursor: not-allowed; transform: none; box-shadow: none; }}
        #status {{ margin-top: 25px; font-weight: 500; font-size: 1.1em; padding: 10px; border-radius: 4px; background: rgba(255,255,255,0.05); }}
    </style>
</head>
<body>
    <button id="connectBtn" class="button">🎤 Click to Connect & Speak</button>
    <button id="disconnectBtn" class="button" style="display:none; background-color: #333333;">⏹️ Disconnect</button>
    <div id="status">Status: ⚪ Disconnected</div>

    <script>
        const url = "{url}";
        const token = "{token}";
        
        let room;

        const connectBtn = document.getElementById('connectBtn');
        const disconnectBtn = document.getElementById('disconnectBtn');
        const statusDiv = document.getElementById('status');
        
        async function setupRoom() {{
            room = new LivekitClient.Room({{
                adaptiveStream: true,
                dynacast: true,
            }});

            room.on(LivekitClient.RoomEvent.Connected, () => {{
                statusDiv.innerHTML = "Status: 🟢 Connected! You can speak now.";
                connectBtn.style.display = 'none';
                disconnectBtn.style.display = 'inline-block';
            }});

            room.on(LivekitClient.RoomEvent.Disconnected, () => {{
                statusDiv.innerHTML = "Status: ⚪ Disconnected";
                connectBtn.style.display = 'inline-block';
                disconnectBtn.style.display = 'none';
            }});

            room.on(LivekitClient.RoomEvent.TrackSubscribed, (track, publication, participant) => {{
                if (track.kind === 'audio' || track.kind === 'video') {{
                    const element = track.attach();
                    document.body.appendChild(element); // Important to actually hear the agent!
                }}
            }});
            
            room.on(LivekitClient.RoomEvent.TrackUnsubscribed, (track, publication, participant) => {{
                track.detach();
            }});
        }}

        connectBtn.onclick = async () => {{
            connectBtn.disabled = true;
            statusDiv.innerHTML = "Status: 🟡 Accessing Microphone...";
            
            try {{
                // Note: If this fails in Streamlit iframe due to missing allow="microphone",
                // you may have to open the app outside of an iframe or use a different frontend architecture.
                const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
                
                statusDiv.innerHTML = "Status: 🟡 Connecting to Agent...";
                
                await setupRoom();
                await room.connect(url, token);
                
                // Publish microphone using explicit tracks
                const tracks = await LivekitClient.createLocalTracks({{ audio: true, video: false }});
                await room.localParticipant.publishTrack(tracks[0]);
                
                statusDiv.innerHTML = "Status: 🟢 Connected! Speak to the agent.";
                connectBtn.disabled = false;
            }} catch (e) {{
                console.error(e);
                statusDiv.innerHTML = "Status: ❌ Error: " + e.message;
                connectBtn.disabled = false;
            }}
        }};
        
        disconnectBtn.onclick = async () => {{
            if (room) {{
                await room.disconnect();
            }}
        }};
    </script>
</body>
</html>
"""

st.components.v1.html(html_code, height=400)

st.markdown("---")
st.markdown("### How to test:")
st.markdown("1. Make sure `uv run agent_mcp.py dev` is running in your terminal.")
st.markdown("2. Ensure that terminal shows the agent joining the playground room.")
st.markdown("3. Click the red record button above to connect your microphone directly.")
