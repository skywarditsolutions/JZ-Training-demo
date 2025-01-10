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

from haystack.components.builders.prompt_builder import PromptBuilder

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
        
        Args: server_script_path (str): The path to the python server script (.py)"""
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

        response = await self.session.list_tools()
        self.tools = response.tools
        print(f"\nconnected to server with tools: {[tool.name for tool in response.tools]}")
    
    def tool_call(self, document_content: str, user_message: Optional[str] = None, messages: Optional[list[str]] = None):
        tool_call = self.session.tool_call(document_content, user_message, messages)
        return tool_call
    
    def send_message(self, document_content: str, user_message: Optional[str] = None, messages: Optional[list[dict[str,str]]] = None):
        if not messages:
            messages = []
            # claude SDK doesn't let you do system prompt?
            print(self.tools)
            system_prompt = "You are a helpful assistant, you have the following tools available: " + ", ".join([tool.name for tool in self.tools])
            messages.append({"role": "user", "content": system_prompt}) # passing in as user message

        content = ""
        if user_message:
            content = f"Document content: {document_content}\n\nUser message: {user_message}"
        else: 
            content = f"Document content: {document_content}"
        
        messages.append({"role": "user", "content": content})

        response = self.chat.messages.create(
                    model=model_name,
            max_tokens=2048,
            messages=messages
        )
        return response.content

    def parse_tool_call(self, response):
        print(response)
    
    def chat_loop(self):
        messages = []
        user_message = input("User: ")
        document_content = input("Document: ") # TODO make doc uploader + extractor
        while True:
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