import aiohttp
from mcp.server.fastmcp import FastMCP

# Create a FastMCP server
mcp = FastMCP("weather")

@mcp.tool()
async def get_weather(location: str) -> str:
    """Get the current weather and temperature for a specific location using Open-Meteo."""
    try:
        async with aiohttp.ClientSession() as session:
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1&language=en&format=json"
            async with session.get(geo_url) as geo_resp:
                if geo_resp.status != 200:
                    return "Sorry, the geocoding service is currently unavailable."
                geo_data = await geo_resp.json()
                if not geo_data.get("results"):
                    return f"Sorry, I couldn't find the location {location}."
                
                lat = geo_data["results"][0]["latitude"]
                lon = geo_data["results"][0]["longitude"]
                resolved_name = geo_data["results"][0].get("name", location)

            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m"
            async with session.get(weather_url) as weather_resp:
                if weather_resp.status == 200:
                    weather_data = await weather_resp.json()
                    temp = weather_data["current"]["temperature_2m"]
                    return f"The current temperature in {resolved_name} is {temp} degrees Celsius."
                else:
                    return "Sorry, the weather service is currently unavailable."
    except Exception as e:
        return f"There was an error fetching the weather: {str(e)}"

if __name__ == "__main__":
    # Start the server using standard I/O for MCP communication
    mcp.run()
