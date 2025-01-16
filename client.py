import asyncio
import json
import os
import re
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from dotenv import load_dotenv
from anthropic import AnthropicBedrock
from datetime import datetime
import pytz

import mcp.types as types

#from haystack.components.builders.prompt_builder import PromptBuilder

load_dotenv()

# Only (?) supported model
model_name="anthropic.claude-3-5-sonnet-20240620-v1:0"

class MCPClient:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.chat = AnthropicBedrock()
        self.tools = []
        self.time_format_24hr = True
    
    # Mapping from common city names to timezones (expand this as needed)

    city_to_timezone = {
        "new york": "America/New_York",
        "tokyo": "Asia/Tokyo",
        "london": "Europe/London",
        "paris": "Europe/Paris",
        "berlin": "Europe/Berlin",
        "sydney": "Australia/Sydney",
        "dubai": "Asia/Dubai",
        "los angeles": "America/Los_Angeles",
        "mumbai": "Asia/Kolkata",
        "singapore": "Asia/Singapore",
    }

    # List of all available time zones
    def list_all_timezones(self):
        return pytz.all_timezones

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP Server
            This method sets up a connection to a Python-based MCP server by:
        1. Validating the server script file extension
        2. Creating a stdio transport connection
        3. Initializing a client session
        4. Retrieving and reformatting available tools

        Args:
            server_script_path: Path to the Python server script file (.py extension)

        Raises:
            ValueError: If the provided script path doesn't end with .py extension
            
        Returns:
            None: Updates instance attributes (stdio, write, session, tools) as side effects
            
        """
        
        # validate the server script is a python script
        is_python = server_script_path.endswith(".py")
        if not is_python:
            raise ValueError("Server script must be a Python script (.py)")
        
        # only python for now
        # Configure and establish stdio transport connection
        # StdioServerParameters specifies how to spawn and communicate with the server process
        server_params = StdioServerParameters(
            command="python", args=[server_script_path], env=None
        )

        # Create transport layer using context manager to ensure proper cleanup
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))

        # Unpack transport handles for reading and writing
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # Retrieve available tools from server and reformat for Anthropic compatibility
        response = await self.session.list_tools()
        formatted_tools = reformat_tools_description_for_anthropic(response.tools)
        self.tools = formatted_tools

        print(f"\nconnected to server with tools: {[tool.name for tool in response.tools]}")

    async def call_summarize_document_tool(self, LLM_tool_call):
        print("LLM tool call: ")
        print(LLM_tool_call)
        tool_name = to_kebab_case(LLM_tool_call["name"])
        tool_call = await self.session.call_tool(tool_name, LLM_tool_call["input"])
        return tool_call
    
    def get_current_datetime(self, request_type="both", timezone=None):
        """Get current date and time (system time or server time)."""
        
        format_date = "%B %d, %Y"
        format_time_24hr = "%H:%M:%S"
        format_time_12hr = "%I:%M:%S %p"

        time_format = "%H:%M:%S" if self.time_format_24hr else "%I:%M:%S %p"

        local_time = datetime.now()
        utc_time = datetime.now(pytz.utc)

        if timezone:
            if timezone in pytz.all_timezones:
                timezone_obj = pytz.timezone(timezone)
                local_time = datetime.now(timezone_obj)
                utc_time = datetime.now(pytz.utc)
            else:
                return f"❌ Invalid timezone: {timezone}. Please provide a valid timezone."
        else:
            # Return default (UTC) time if no timezone is specified
            return f"❌ No timezone specified. Please provide a city for timezone detection."

        if request_type == "time":
            return f"🕒 Local Time: {local_time.strftime(time_format)}, UTC Time: {utc_time.strftime(time_format)}"
        elif request_type == "date":
            return f"📅 Local Date: {local_time.strftime('%B %d, %Y')}, UTC Date: {utc_time.strftime('%B %d, %Y')}"
        else:  
            return (f"📅 Local Date: {local_time.strftime('%B %d, %Y')}, UTC Date: {utc_time.strftime('%B %d, %Y')}\n"
                    f"🕒 Local Time: {local_time.strftime(time_format)}, UTC Time: {utc_time.strftime(time_format)}")
    
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

    def toggle_time_format(self):
        """Toggle between 12-hour and 24-hour time formats."""
        self.time_format_24hr = not self.time_format_24hr
        mode = "24-hour" if self.time_format_24hr else "12-hour"
        print(f"✅ Time format switched to {mode} mode.")

    def send_message(self, document_content: str, user_message: Optional[str] = None, messages: Optional[list[dict[str,str]]] = None):
        if not messages:
            messages = []

        if self.is_time_or_date_request(user_message):
            # Detect timezone based on user message
            timezone = None
            for city, tz in self.city_to_timezone.items():
                if city in user_message.lower():
                    timezone = tz
                    break
            
            if timezone:
                print(f"User requested time in timezone: {timezone}")
                datetime_response = self.get_current_datetime(request_type="both", timezone=timezone)
            
            else:
                print(f"No recognized timezone found in the message.")
                # Provide feedback for missing timezone or default to UTC
                datetime_response = "❌ Could not detect a timezone from your query. Please provide a valid city for timezone information."
            
            print(f"\n {datetime_response}\n")
            return {"content": datetime_response}  # Return a JSON-like dict to avoid parsing errors
        
        else:
            chat_prompt = "You are a helpful API, you have the ability to call tools to achieve user requests.\n\n"
            chat_prompt += "User request: " + user_message + "\n\n"
            chat_prompt += "Document content: " + document_content + "\n\n"
            messages.append({"role": "user", "content": chat_prompt})
            
        response = self.chat.messages.create(
            model=model_name,
            max_tokens=2048,
            messages=messages,
            tools=self.tools
        )
        return response.content
    
    def process_LLM_response(self, response):
        pass


    def check_tool_call(self, response):
        """
        Check if the response contains a tool call and extract the relevant information.
        """
        try:
            # Skip parsing if response is already in dict format (time/date)
            if isinstance(response, dict) and "content" in response:
                 return None  # No tool call, response was handled directly
            # Handle string response by parsing JSON
            if isinstance(response, str):
                try:
                    response = json.loads(response)
                except json.JSONDecodeError:
                    print("Failed to parse response as JSON")
                    return None
                    # If response is a list/array, look for tool_use block
            if isinstance(response, list):
                for block in response:
                    # Check if block is a dictionary with a 'type' key
                    if isinstance(block, dict) and block.get('type') == 'tool_use':
                        return block
                    # Handle custom objects that might have a type attribute/property
                    elif hasattr(block, 'type') and block.type == 'tool_use':
                        return block.__dict__ if hasattr(block, '__dict__') else block
            
            elif isinstance(response, dict) and response.get("type") == "tool_use":
                return response
        
            print("check tool call: ")
            print(response)
            # Check for tool use stop reason
            if response[0]["type"]!= "tool_use":
                return None
                
            # Check for tool calls array
            return response[0]
            
        except Exception as e:
            print(f"Error checking tool call: {e}")
            return None

    def get_user_input(self):
        """todo, parse multiline input"""
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
        while True:
            user_message = input("User: ").strip()

            if user_message.lower() in ["switch to 12-hour", "switch to 24-hour", "switch time format",
                                        "change time format", "12 hour" "24 hour", "switch format"]:
                self.toggle_time_format()
                continue

            #  If the user asks for time/date, skip document prompt
            datetime_request = self.detect_datetime_request(user_message)
            if datetime_request != "none":
                timezone = None
                for city, tz in self.city_to_timezone.items():
                    if city in user_message.lower():
                        timezone = tz
                        break

                datetime_response = self.get_current_datetime(request_type=datetime_request)
                print(f"\n {datetime_response}\n")
                continue  # Skip asking for a document

            # For all other inputs, prompt for document content
            document_content = input("Document: ")

            #  Send the message to the model
            response = self.send_message(user_message=user_message, document_content=document_content, messages=messages)
            print(response)

            # Check if a tool was called
            tool_call = self.check_tool_call(response)
            if tool_call:
                tool_response = await self.call_summarize_document_tool(tool_call)
                print(tool_response)
                summary = tool_response.content[0].text
                print(summary)   
    
    async def cleanup(self):
        await self.exit_stack.aclose()

def reformat_tools_description_for_anthropic(tools: list[types.Tool]):
    # MCP library changes the tool name to camelCase, so we need to reformat it so anthropic can use it
    reformatted_tools = []
    for tool in tools:
        current_tool = {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema,
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

def to_kebab_case(camel_str: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '-', camel_str).lower()

async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
        
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    import sys
    asyncio.run(main())