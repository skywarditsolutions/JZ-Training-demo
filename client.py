import asyncio
import json
import os
import re
from typing import Optional
from contextlib import AsyncExitStack
import boto3

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from dotenv import load_dotenv
from anthropic import AnthropicBedrock


load_dotenv()

# Only (?) supported model
model_name="anthropic.claude-3-5-sonnet-20240620-v1:0"

class MCPClient:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.chat = AnthropicBedrock()
    
    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP Server
        
        Args: server_script_path (str): The path to the python server script (.py)"""
        is_python = server_script_path.endswith(".py")
        if not is_python:
            raise ValueError("Server script must be a Python script (.py)")
        
        # hardcoded python for now
        server_params = StdioServerParameters(
            command="python", args=[server_script_path], env=None
        )
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))

        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        response = await self.session.list_tools()
        print(f"response: {response}")
        tools = response.tools
        print(f"\nconnected to server with tools: {[tool.name for tool in tools]}")
    
    def tool_call(self, document_content: str, user_message: Optional[str] = None, messages: Optional[list[str]] = None):
        if not messages:
            messages = []
            system_prompt = "You are a helpful assistant that summarizes documents. You provide a thorough summary of the document and highlight anything surprising or interesting. Return the summary in <summary></summary> tags."
            messages.append({"role": "system", "content": system_prompt})
            user_prompt = f"Document content: {document_content}\n\nUser message: {user_message}"
            messages.append({"role": "user", "content": user_prompt})
        else:
            messages.append({"role": "user", "content": user_message})

        response = self.chat.messages.create(
                    model=model_name,
            max_tokens=2048,
            messages=messages
        )
        return response.content
    
    def send_message(self, document_content: str,user_message: Optional[str] = None, messages: Optional[list[str]] = None):
        return self.tool_call(document_content, user_message, messages)
    
    def chat_loop(self):
        messages = []
        while True:
            user_message = input("User: ")
            document_content = input("Document: ") # TODO make doc uploader + extractor
            response = self.send_message(user_message, document_content, messages)
            print(response)
            messages.append({"role": "assistant", "content": response})
    
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