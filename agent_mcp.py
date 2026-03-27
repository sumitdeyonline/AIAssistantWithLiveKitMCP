import logging

from dotenv import load_dotenv
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
)
from livekit.agents.llm.mcp import MCPServerStdio, MCPToolset
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import cartesia, deepgram, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv()
logger = logging.getLogger("voice-agent")

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    # Connect to room, restricting to audio tracks only
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Wait for the first participant to connect
    participant = await ctx.wait_for_participant()

    # Configure the MCP server to run via standard I/O utilizing our local server script
    mcp_server = MCPServerStdio(
        command="python",
        args=["weather_mcp.py"]
    )
    # Create the Toolset and link it to the MCP Server
    mcp_toolset = MCPToolset(id="weather", mcp_server=mcp_server)
    
    # Initialize the toolset to fetch available functions from the MCP Server
    await mcp_toolset.setup()

    # Ensure the MCP server shuts down properly when the agent session ends
    # We use a lambda to call the async aclose method, which LiveKit gracefully handles.
    # Note: add_shutdown_callback supports sync or async callables.
    ctx.add_shutdown_callback(lambda: mcp_toolset.aclose())

    # The actual Agent behavior
    agent = Agent(
        instructions="You are a helpful voice AI assistant. Your interface with users will be voice. You use MCP tools to provide weather forecasts.",
        tools=[mcp_toolset],
    )

    # Build the AgentSession
    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=cartesia.TTS(),
        turn_detection=MultilingualModel(),
    )

    # Start the session
    await session.start(
        agent=agent,
        room=ctx.room,
    )

    # Generate an initial greeting
    logger.info("Agent started, saying initial greeting...")
    session.generate_reply(
        user_input="Introduce yourself to the user briefly and let them know you can check the weather using your new MCP tools."
    )

if __name__ == "__main__":
    # Setup standard logging
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
