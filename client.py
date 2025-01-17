import asyncio
import json
import os
import re
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from dotenv import load_dotenv

load_dotenv()

from anthropic import AnthropicBedrock

from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from tzlocal import get_localzone_name

#from datetime import datetime
import pytz
import arrow


import mcp.types as types

#from haystack.components.builders.prompt_builder import PromptBuilder



# Only (?) supported model
model_name="anthropic.claude-3-5-sonnet-20240620-v1:0"

class MCPClient:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.chat = AnthropicBedrock()
        self.tools = []
        self.time_format_24hr = True
        self.geolocator = Nominatim(user_agent="timezone_detector")
        self.tz_finder = TimezoneFinder()
    

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
        server_params = StdioServerParameters(
            command="python", args=[server_script_path], env=None
        )
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))

        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # Retrieve available tools from server and reformat for Anthropic compatibility
        # MCP library changes the tool name to camelCase, so we need to reformat it so anthropic can use it
        response = await self.session.list_tools()
        formatted_tools = reformat_tools_description(response.tools)
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
        # MCP library changes the tool name to kebab case, so we need to reformat it so the server can use it
        tool_name = to_camel_case(tool_call.name)
        
        # call tool over the MCP connection established in connect_to_server, takes in tool name and args
        tool_result = await self.session.call_tool(tool_call.name, tool_call.input)
        return tool_result
    
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

        if self.is_time_or_date_request(user_message):
            # Detect timezone based on user message
            timezone = self.detect_timezone(user_message)  # Detect timezone or None

            # Always provide a response (default to local time if no timezone detected)
            datetime_response = self.get_current_datetime(request_type="both", timezone=timezone)

            print(f"\n {datetime_response}\n")
            return {"content": datetime_response}  # Return a JSON-like dict to avoid parsing errors
        else:
            chat_prompt = "You are a helpful API, you have the ability to call tools to achieve user requests.\n\n"
            chat_prompt += "User request: " + user_message + "\n\n"
            chat_prompt += "Document content: " + document_content + "\n\n"
            messages.append({"role": "user", "content": chat_prompt})
            system_prompt = "We are testing a tool calling model, reply with a choice of available tools."
            messages.append({"role": "user", "content": system_prompt}) # passing in as user message
        else:
            messages.append({"role": "user", "content": user_message})

        # TODO handle repeated chat messages
        content = ""
        if user_message:
            content = f"Document content: {document_content}\n\nUser message: {user_message}"
        else: 
            content = f"Document content: {document_content}"
        
        messages.append({"role": "user", "content": content})

        # send messages to the LLM
        response = self.chat.messages.create(
            model=model_name,
            max_tokens=2048,
            messages=messages,
            tools=self.tools
        )
        return response

    def parse_tool_call(self, response):
        print(response)

    def process_LLM_response(self, response):
        pass


    def check_tool_call(self, response):
        """
        Check if the response contains a tool call and extract the relevant information.
        Args:
            response: The full object response from the LLM

        Returns:
            tool_call: The tool call response from the server
        """
        try:
            # Skip parsing if response is already in dict format (time/date)
            if isinstance(response, dict) and "content" in response:
                 return None  # No tool call, response was handled directly
            content = response.content
            # if response is a string, try to parse it as JSON
            if isinstance(content, str):
                try:
                    response = json.loads(content)
                except json.JSONDecodeError:
                    print("Failed to parse response as JSON")
                    return None

            # if response is a list/array, look for tool_use block
            if isinstance(content, list):
                for block in content:
                    # Handle custom objects and check for a tool use attribute/property
                    if hasattr(block, 'type') and block.type == 'tool_use':
                        return block.__dict__ if hasattr(block, '__dict__') else block
            
            # Check if block is a dictionary with a 'type' key that matches tool_use
            elif isinstance(content, dict) and content.get("type") == "tool_use":
                return content
        
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
    
    def chat_loop(self):
        messages = []
        user_message = input("User: ")
        # have hardcoded news story for now
        document_content = input("Document to summarize (leave blank for hardcoded news story): ")

        while True:
            user_message = input("User: ").strip()

            if user_message.lower() in ["switch to 12-hour", "switch to 24-hour", "switch time format",
                                        "change time format", "12 hour" "24 hour", "switch format"]:
                self.toggle_time_format()
                continue

            #  If the user asks for time/date, skip document prompt
            datetime_request = self.detect_datetime_request(user_message)
            if datetime_request != "none":
                timezone = self.detect_timezone(user_message)

                # Call the updated datetime method with the detected timezone
                datetime_response = self.get_current_datetime(request_type=datetime_request, timezone=timezone)
                print(f"\n{datetime_response}\n")
                continue  # Skip asking for a document

            # For all other inputs, prompt for document content
            document_content = input("Document: ")

            #  Send the message to the model
            response = self.send_message(user_message=user_message, document_content=document_content, messages=messages)
            llm_text_response = response.content[0].text.strip() # final assistant content cannot end with trailing whitespace
            print("LLM: ", llm_text_response)
            messages.append({"role": "assistant", "content": llm_text_response}) 
            # check if the response contains a tool call
            tool_call = self.check_tool_call(response)
            if tool_call:
                tool_response = await self.call_summarize_document_tool(tool_call)
                summary = tool_response.content[0].text
                print("summary: ", summary)
                messages.append({"role": "assistant", "content": f"Tool summary: {summary.strip()}"})# final assistant content cannot end with trailing whitespace
            else:
                messages.append({"role": "assistant", "content": llm_text_response})=======
            # initial LLM call
            response = self.send_message(user_message, document_content, messages)
            print(response)
            tool_call = self.parse_tool_call(response)
            if tool_call:
                tool_response = self.tool_call(tool_call)
                print(tool_response)
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