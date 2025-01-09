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

#model_name="anthropic.claude-3-5-sonnet-20240620-v1:0"


class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.bedrock = boto3.client(
            service_name="bedrock-runtime",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=os.getenv("AWS_REGION"),
        )

    def to_camel_case(self, kebab_str: str) -> str:
      return "".join(x.capitalize() for x in kebab_str.lower().split("-"))
    
    def to_kebab_case(self, camel_str: str) -> str:
      return re.sub(r'(?<!^)(?=[A-Z])', '-', camel_str).lower()

    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP server

        Args:
            server_script_path: Path to the server script (.py or .js)
        """
        is_python = server_script_path.endswith(".py")
        is_js = server_script_path.endswith(".js")
        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js file")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command, args=[server_script_path], env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        await self.session.initialize()

        # List available tools
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> None:
        """Process a query using Claude and available tools"""
        messages = [{"role": "user", "content": [{"text": query}]}]

        response = await self.session.list_tools()
        available_tools = [
            {
                "toolSpec": {
                    "name": self.to_camel_case(tool.name),
                    "description": tool.description,
                    "inputSchema": {
                        "json": tool.inputSchema
                    },
                }
            }
            for tool in response.tools
        ]

        response = self.bedrock.converse(
            modelId=os.getenv("BEDROCK_MODEL_NAME"),
            messages=messages,
            toolConfig={"tools": available_tools},
        )

        output_message = response['output']['message']
        messages.append(output_message)
        stop_reason = response['stopReason']

        final_text = []

        if stop_reason == 'tool_use':
          tool_requests = response['output']['message']['content']
          for tool_request in tool_requests:
            if 'toolUse' in tool_request:
              tool = tool_request['toolUse']

              tool_name = self.to_kebab_case(tool["name"])
              tool_args = tool["input"]

              final_text.append(f"[Calling tool {tool_name} with args {tool_args}]")
              tool_result = await self.session.call_tool(tool_name, tool_args)

              tool_result_message = {
                  "role": "user",
                  "content": [
                      {
                          "toolResult": {
                             "toolUseId": tool["toolUseId"],
                             "content": [
                                {
                                   "text": tool_result.content[0].text
                                }
                             ],
                             "status": "error" if tool_result.isError else "success"
                          }

                      }
                  ]
              }
              messages.append(tool_result_message)

              response = self.bedrock.converse(
                modelId=os.getenv("BEDROCK_MODEL_NAME"),
                messages=messages,
                toolConfig={"tools": available_tools},
              )
              output_message = response['output']['message']

        for content in output_message['content']:
          print(content["text"])

    async def chat_loop(self):
      """Run an interactive chat loop"""
      print("\nMCP Client Started!")
      print("Type your queries or 'quit' to exit.")
      
      while True:
          try:
              query = input("\nQuery: ").strip()
              
              if query.lower() == 'quit':
                  break
                  
              await self.process_query(query)
                  
          except Exception as e:
              print(f"\nError: {str(e)}")

    async def cleanup(self):
      """Clean up resources"""
      await self.exit_stack.aclose()

async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

            
    client = AnthropicBedrock()
    message = client.messages.create(
        model=os.getenv("BEDROCK_MODEL_NAME"),
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": "Hey, how are you?"
            }
        ]
    )
    print(message.content)
        
    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()

if __name__ == "__main__":
    import sys
    asyncio.run(main())