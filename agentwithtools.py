import logging
from typing import Annotated

import aiohttp
from dotenv import load_dotenv
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import cartesia, deepgram, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

load_dotenv()
logger = logging.getLogger("voice-agent")

@llm.function_tool(
    name="get_weather",
    description="Get the current weather for a specific location."
)
async def get_weather(location: str) -> str:
    """Get the current weather for a specific location."""
    logger.info(f"Getting weather for {location}")
    try:
        async with aiohttp.ClientSession() as session:
            # First, get the latitude and longitude using Open-Meteo Geocoding API
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1&language=en&format=json"
            #geo_url = f"http://shayne.app/weather?location={location}"
            async with session.get(geo_url) as geo_resp:
                if geo_resp.status != 200:
                    return "Sorry, the geocoding service is currently unavailable."
                geo_data = await geo_resp.json()
                if not geo_data.get("results"):
                    return f"Sorry, I couldn't find the location {location}."
                
                lat = geo_data["results"][0]["latitude"]
                lon = geo_data["results"][0]["longitude"]
                resolved_name = geo_data["results"][0].get("name", location)

            # Next, get the weather for those coordinates
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m"
            async with session.get(weather_url) as weather_resp:
                if weather_resp.status == 200:
                    weather_data = await weather_resp.json()
                    temp = weather_data["current"]["temperature_2m"]
                    # Spell out units to ensure reliable Cartesia TTS synthesis
                    return f"The current temperature in {resolved_name} is {temp} degrees Celsius."
                else:
                    return "Sorry, the weather service is currently unavailable."
    except Exception as e:
        logger.error(f"Weather API error: {e}")
        return "There was an error fetching the weather. Please try again later."

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    # Connect to room, restricting to audio tracks only
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Wait for the first participant to connect
    participant = await ctx.wait_for_participant()

    # The actual Agent behavior
    agent = Agent(
        instructions="You are a helpful voice AI assistant. Your interface with users will be voice. You can provide weather information when asked.",
        tools=[get_weather],
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
    # Instruct the LLM to generate the greeting dynamically
    session.generate_reply(
        user_input="Introduce yourself to the user briefly."
    )

if __name__ == "__main__":
    # Setup standard logging
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )