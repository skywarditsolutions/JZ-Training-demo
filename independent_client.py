import asyncio
import json
import os
import re
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client

from dotenv import load_dotenv
from anthropic import AnthropicBedrock

#this is the date time stuff
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from tzlocal import get_localzone_name
import pytz
import arrow

import mcp.types as types


load_dotenv()

# Only (?) supported model
model_name="anthropic.claude-3-5-sonnet-20240620-v1:0"

class MCPClient:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.chat = AnthropicBedrock()
        self.tools = []


        #date time stuff
        self.time_format_24hr = True
        self.geolocator = Nominatim(user_agent="timezone_detector")
        self.tz_finder = TimezoneFinder()
    
    # List of all available time zones
    def list_all_timezones(self):
        return pytz.all_timezones
    


    async def connect_to_server(self, server_url: str):
        """Connect to an MCP Server
        """
        # connect to the server
        sse_transport = await self.exit_stack.enter_async_context(sse_client(server_url))
        sse_recv, sse_sent = sse_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(sse_recv, sse_sent))
        if self.session:
            await self.session.initialize()
        
            # Retrieve available tools from server and reformat for Anthropic compatibility
            # MCP library changes the tool name to camelCase, so we need to reformat it so anthropic can use it
            response = await self.session.list_tools()
            formatted_tools = reformat_tools_description_for_anthropic(response.tools)
            self.tools = formatted_tools

            print(f"\nconnected to server with tools: {[tool.name for tool in response.tools]}")

    async def call_summarize_document_tool(self, tool_call):
        """
        This method handles the tool call from the LLM and passes it to the server
        Args:
            LLM_tool_call: The tool call from the LLM
            
        Returns:
            tool_call: The tool call response from the MCP server
        """
        # call tool over the MCP connection established in connect_to_server, takes in tool name and args
        tool_result = await self.session.call_tool(tool_call.name, tool_call.input)
        return tool_result
    

    def get_current_datetime(self, request_type="both", timezone=None):
        """
        Get the current date and/or time in the specified timezone.
        Defaults to system's local timezone if no timezone is provided.
        """
        time_format = "HH:mm:ss" if self.time_format_24hr else "hh:mm:ss A"
        date_format = "MMMM DD, YYYY"

        try:
            # 🌍 Use detected timezone or system timezone
            if timezone:
                current_time = arrow.now(timezone)
            else:
                current_time = arrow.now()

            # 🕒 Format the response
            if request_type == "time":
                return f"🕒 Local Time: {current_time.format(time_format)}"
            elif request_type == "date":
                return f"📅 Local Date: {current_time.format(date_format)}"
            else:
                return (f"📅 Local Date: {current_time.format(date_format)}\n"
                        f"🕒 Local Time: {current_time.format(time_format)}")

        except Exception as e:
            return f"❌ Error fetching time: {e}"

    def is_time_or_date_request(self, user_message: str) -> bool:
        """Detect if the user is asking for the current date and/or time."""

        # Define common time/date request phrases
        time_date_phrases = [
            "what time is it",
            "what is the time",
            "give me the time",
            "tell me the time",
            "current time",
            "want the date",
            "want the time",
            "want the time and date ",
            "what is the date",
            "give me the date",
            "tell me the date",
            "give me time",
            "give me date",
            "give me time and date",
            "current date",
            "what is the date and time",
            "give me the date and time",
            "can you tell me the time",
            "can you tell me the date",
            "date and time",
            "can i get the date",
            "can i get the time",
            "can i get the date and time",
            "can i get the time and date"
        ]

        # Lowercase the input for consistent comparison
        user_message = user_message.lower().strip()

        # Return True if any of the phrases match
        return any(phrase in user_message for phrase in time_date_phrases)
    
    def detect_datetime_request(self, user_message: str) -> str:
        """
        Detect if the user is asking for the date, time, or both.
        Returns: 'time', 'date', 'both', or 'none'
        """
        message = user_message.lower()
        
        time_keywords = ["time", "current time", "what time", "tell me the time"]
        date_keywords = ["date", "current date", "what date", "tell me the date"]
        both_keywords = ["date and time", "time and date", "current date and time"]
        
        if any(phrase in user_message for phrase in both_keywords):
            return "both"
        elif any(phrase in user_message for phrase in time_keywords):
            return "time"
        elif any(phrase in user_message for phrase in date_keywords):
            return "date"
        else:
            return "none"
        
    def detect_timezone(self, user_message: str) -> Optional[str]:
        """
        Detect the timezone from the user's input using geolocation.
        """
        try:
            # Clean the user input for better detection
            location_query = re.sub(r'[^a-zA-Z\s]', '', user_message).strip().lower()

            # Extract the likely city name (assumes 'in <city>' structure)
            city_match = re.search(r'in (.+)', location_query)
            city_name = city_match.group(1) if city_match else location_query

            print(f"🔎 Searching for location: {city_name}")

            # Attempt to geocode the extracted city name
            location = self.geolocator.geocode(city_name, timeout=10)  # Increase timeout

            if location:
                # Convert the detected location into a timezone
                timezone = self.tz_finder.timezone_at(lng=location.longitude, lat=location.latitude)
                if timezone:
                    print(f"🛰️ Detected Timezone: {timezone}")
                    return timezone
                else:
                    print("⚠️ Could not determine timezone from coordinates.")
            else:
                print("⚠️ Geolocation failed. No result found.")

        except Exception as e:
            print(f"⚠️ Error detecting timezone: {e}")

        # Fallback to system timezone if detection fails
        return None


    def toggle_time_format(self):
        """Toggle between 12-hour and 24-hour time formats."""
        self.time_format_24hr = not self.time_format_24hr
        mode = "24-hour" if self.time_format_24hr else "12-hour"
        print(f"✅ Time format switched to {mode} mode.")


    def send_message(self, document_content: str, user_message: Optional[str] = None, messages: Optional[list[dict[str,str]]] = None):
        """
        This method sends a message to the LLM and returns the response

        Args:
            document_content: The content of the document to be summarized
            (optional) user_message: The user's message to the LLM
            (optional) messages: The list of messages of the chat history

        Returns:
            response: The response from the LLM
        """
        # if no messages, create a new list and inital chat message
        if not messages:
            messages = []
            chat_prompt = "You are a helpful assistant, you have the ability to call tools to achieve user requests.\n\n"
            chat_prompt += "User request: " + user_message + "\n\n"
            chat_prompt += "Document content: " + document_content + "\n\n"
            messages.append({"role": "user", "content": chat_prompt}) # passing in as user message
        else:
            messages.append({"role": "user", "content": user_message})

        # send messages to the LLM
        response = self.chat.messages.create(
                    model=model_name,
            max_tokens=2048,
            messages=messages,
            tools=self.tools
        )
        return response
    
    def check_tool_call(self, response):
        """
        Check if the response contains a tool call and extract the relevant information.
        Args:
            response: The full object response from the LLM

        Returns:
            tool_call: The tool call response from the server
        """
        try:
            if response.stop_reason == "tool_use":
                print("type is tool_use")
                return response.content[1] # response format is [chat_message, tool_call]
        
            # return false if no tool call is found
            return False
            
        except Exception as e:
            print(f"Error checking tool call: {e}")
            return None

    def get_user_input(self):
        """parse multiline input"""
        # TODO: finish this function
        lines = []
        print("User: ")

        while True:
            try: 
                line = input()
                lines.append(line)
            except EOFError:
                break
        return lines
    
    async def chat_loop(self):
        messages = []
        user_message = input("User: ")
        # have hardcoded news story for now
        document_content = input("Document to summarize (leave blank for hardcoded news story OR time/date requests): ")

        while True:

            if user_message.lower() in ["switch to 12-hour", "switch to 24-hour", "switch time format",
                                     "change time format", "12 hour", "24 hour", "switch format", "change format"
                                     , "other format", "twelve hour format", "twenty-four hour format"]:
                self.toggle_time_format()
                user_message = input("User: ")
                continue

            # Check for date/time requests
            datetime_request = self.detect_datetime_request(user_message)
            if datetime_request != "none":
                timezone = self.detect_timezone(user_message)
                datetime_response = self.get_current_datetime(request_type=datetime_request, timezone=timezone)
                print(f"\n{datetime_response}\n")
                user_message = input("User: ")
                continue

            # LLM call
            if document_content == "":
                document_content = fake_news_story # have a hardcoded news story for testing
            if user_message == "": # if user presses enter without typing anything, continue
                continue
            # send inputs to the LLM and get response
            response = self.send_message(user_message=user_message, document_content=document_content, messages=messages)
            llm_text_response = response.content[0].text.strip() # final assistant content cannot end with trailing whitespace
            print("LLM: ", llm_text_response)
            messages.append({"role": "assistant", "content": llm_text_response}) 
            # check if the response contains a tool call
            tool_call = self.check_tool_call(response)
            if tool_call:
                tool_response = await self.call_summarize_document_tool(tool_call)
                tool_result_text = tool_response.content[0].text
                print("tool response: ", tool_result_text)
                messages.append({"role": "assistant", "content": f"Tool summary: {tool_result_text.strip()}"})# final assistant content cannot end with trailing whitespace
            else:
                messages.append({"role": "assistant", "content": llm_text_response})
            user_message = input("User: ")
    
    async def cleanup(self):
        await self.exit_stack.aclose()

def reformat_tools_description_for_anthropic(tools: list[types.Tool]):
    """
    Reformat the tools description for anthropic
    Args:
        tools: The list of tools to be reformatted

    Returns:
        reformatted_tools: The list of reformatted tools with snake_case input_schema
    """
    # MCP library changes the tool name to camelCase, so we need to reformat it so anthropic can use it
    reformatted_tools = []
    for tool in tools:
        current_tool = {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema, # changing camelCase to snake_case so anthropic can use it
        }
        reformatted_tools.append(current_tool)

    return reformatted_tools


fake_news_story = """
Gas Flare Bitcoin Miners Cut Methane Emissions in Permian Basin
MIDLAND, TX - A consortium of Bitcoin mining operations in West Texas reported today that their gas reclamation efforts have prevented over 180,000 metric tons of methane from entering the atmosphere in the past year. By capturing and utilizing natural gas that would otherwise be flared at oil well sites, these mining operations are turning what was once waste into both cryptocurrency and environmental benefits.
"We're essentially monetizing waste gas while reducing greenhouse gas emissions," explained Sarah Chen, CEO of GreenHash Solutions, one of the leading companies in the initiative. "The same energy that would have been burned off into the atmosphere is now powering our mining rigs, and we're seeing real environmental impact."
Independent environmental assessments confirm that these operations have reduced methane emissions equivalent to removing 40,000 cars from the road. The success has drawn attention from other oil-producing regions looking to replicate the model.
Local officials report that the program has also created 75 new technical jobs in the region, with plans to expand operations to additional well sites in the coming months.
"""


async def main():
    client = MCPClient()
        
    try:
        await client.connect_to_server("http://localhost:5553/sse")
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())