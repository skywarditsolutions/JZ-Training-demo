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
    
    def get_current_datetime(self):
        """Get current date and time (system time or server time)."""
        
        local_time = datetime.now()



        utc_time = datetime.now(pytz.utc)

        return f"Local Time: {local_time.strftime('%Y-%m-%d %H:%M:%S')}, UTC Time: {utc_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    def send_message(self, document_content: str, user_message: Optional[str] = None, messages: Optional[list[dict[str,str]]] = None):
        if not messages:
            messages = []


        if "current date and time" in user_message.lower():
        # Respond with current date and time
            datetime_response = self.get_current_datetime()
            chat_prompt = f"User asked for the current date and time.\n\nResponse: {datetime_response}\n\n"
            messages.append({"role": "user", "content": chat_prompt})
        else:
            chat_prompt = "You are a helpful API, you have the ability to call tools to achieve user requests.\n\n"
            chat_prompt += "User request: " + user_message + "\n\n"
            chat_prompt += "Document content: " + document_content + "\n\n"
            messages.append({"role": "user", "content": chat_prompt}) # passing in as user message


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
        user_message = input("User: ")
        document_content = input("Document: ") # TODO make doc uploader + extractor
        while True:
            # LLM call
            response = self.send_message(user_message=user_message, document_content=document_content, messages=messages)
            print(response)

            # Check if the user has asked for time info

            if "current date and time" in user_message.lower():
                print(f"LLM Response: {response}")


            tool_call = self.check_tool_call(response)
            if tool_call:
                # hardcoded tool call for now, TODO: parse tool call, match tool call to tool name
                tool_response = await self.call_summarize_document_tool(tool_call)
                print(tool_response)

                # summary is a string right now
                summary = tool_response.content[0].text
                print(summary)



            user_message = input("User: ")
    
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