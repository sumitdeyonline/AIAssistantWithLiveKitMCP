# Voice AI Assistant Documentation

This standard documentation encompasses the technical architecture, component breakdown, scaling strategies, and deployment mechanisms for the LiveKit Voice AI project.

## 1. System Architecture

The application operates as a distributed WebRTC-based architecture involving a streaming persistent backend worker (AI Agent) and a dynamic frontend web client (Streamlit wrapper).

### 1.1 LiveKit Cloud Signaling
- **Purpose**: Acts as the central WebRTC SFU (Selective Forwarding Unit).
- **Function**: The frontend and backend do not communicate directly. Both parties connect independently to a specific LiveKit "Room". LiveKit handles NAT traversal, dynamic bitrates (Dynacast), and ultra-fast sub-50ms audio streaming.

### 1.2 The AI Backend Pipeline (`agent_mcp.py`)
- **VAD (Voice Activity Detection)**: Real-time detection of user speech endpoints using the local `Silero` plug-in (`VAD.load()`), aggressively tuned for interrupting generation.
- **STT (Speech to Text)**: Captures user speech via the `Deepgram` API, transcribing it in roughly 300ms.
- **LLM/Orchestration**: `AgentSession` passes the text into an `openai.LLM(model="gpt-4o-mini")`. The LLM checks its authorized Tools (`Model Context Protocol` functions), executes them when triggered, and starts streaming generated text.
- **TTS (Text to Speech)**: Converts the AI's response simultaneously as the text streams in via `Cartesia`'s advanced ultra-low-latency Websocket APIs.
- **Turn Detector**: Utilizes `MultilingualModel` (ONNX Weights) to understand exactly when a user has finished their conversational turn natively preventing overlapping interruptions.

### 1.3 The Frontend UI (`app.py`)
- Built in Streamlit. Since typical Python dashboards cannot handle WebRTC native microphone hooks, the Python layer securely mints a dynamic JWT `LiveKitAccessToken`.
- Injects a standard `<iframe src="...livekit-client">` that bypasses Streamlit bottlenecks and links the local browser hardware straight to the LiveKit signaling router.

---

## 2. Advanced Tool Discovery via Model Context Protocol (MCP)

Rather than hard-coding functions directly into the main `agent_mcp.py` script, the application leverages the **Model Context Protocol** introduced by Anthropic to maintain true Separation of Concerns.

### `weather_mcp.py` (The FastMCP Server)
- **Role**: This is an independent Python sub-process.
- **Tech**: Utilizes the official `mcp.server.fastmcp` SDK to register endpoints (e.g., `get_weather`) like an API. 
- **Operation**: It securely calls `aiohttp` directly to Open-Meteo, grabbing real-time geocoded data, and parsing it cleanly without any emoji or symbol collision before handing the raw string back over standard I/O sockets.

### Dynamic Agent Association
When `agent_mcp.py` boots up, it executes `MCPServerStdio` (with command: `python weather_mcp.py`). LiveKit's MCP Toolset hooks into this stdout socket, recursively reading the internal schema exposed by `weather_mcp.py`, and seamlessly wraps those tools into a format the LLM natively understands. 
**Benefit**: You can add 50 new tools to `weather_mcp.py` without writing a single line of plugin code or modifying the main LiveKit agent worker.

---

## 3. Deployment Environments & Practices

To run a LiveKit Agent in a production-ready system, the worker (`agent_mcp.py`) needs to be active permanently (listening for new clients) without shutting down after a timeout.

### 3.1 Fly.io Backend Deployment (The App Worker)
The agent process is containerized and managed via `fly.toml` on **Fly.io**.
- **Run Command**: Rather than using `dev` (which spins up custom test beds), production workers always use the `start` argument.
- **Configuration**: Uses a generic `Dockerfile` mapping `uv run agent_mcp.py start`.
- **Scaling**: A 1GB memory shared-cpu instance is typically optimal for LiveKit Python pipelines under standard workloads, dynamically scaling outward horizontally across Fly.io edge clouds when concurrent sessions increase.

### 3.2 Streamlit Community Cloud (The Frontend UI)
The web interface (`app.py`) is deployed on **share.streamlit.io**.
- **Reasoning**: It's entirely serverless. Because `app.py` has zero heavy ongoing computing needs and merely proxies a JWT token before offloading networking onto the browser client, free serverless Streamlit hosting handles scale effortlessly.
- **Permissions**: Streamlit effectively sandboxes Python processes; therefore, it's critical to isolate backend heavy processing onto Fly.io, utilizing Streamlit purely as a User-Interface layer.

---

## 4. Development Commands Reference

| Operation | Command | Description |
|-----------|---------|-------------|
| **Refresh Env** | `uv pip install -r requirements.txt` | Automatically verifies and installs plugins and missing SDKs. |
| **Sandbox Mod** | `uv run agent_mcp.py dev` | Bypasses permanent connection loops and spawns a temporary Sandbox debug room. |
| **Run Front-End** | `uv run streamlit run app.py` | Spawns a `localhost` web server to visualize the client-facing UI. |
| **Verify Syntax** | `python -m py_compile agent_mcp.py` | A quick CLI trick to guarantee you haven't broken the pipeline. |
