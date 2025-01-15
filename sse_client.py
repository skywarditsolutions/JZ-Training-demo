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

import mcp.types as types


load_dotenv()


class SSE_MCP_Client:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.session = None

    async def connect_to_server(self, server_url: str):
        """Connect to an MCP Server
        """
        # connect to the server
        sse_transport = await self.exit_stack.enter_async_context(sse_client(server_url))
        sse_recv, sse_sent = sse_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(sse_recv, sse_sent))
        if self.session:
            await self.session.initialize()
            print("Connected to server")

    async def get_tools(self):
        """Retrieve available tools from server and reformat for Anthropic compatibility"""
        # MCP library changes the tool name to camelCase, so we need to reformat it so anthropic can use it
        response = await self.session.list_tools()
        print(f"\nAvailable Tools from MCP Server: {[tool.name for tool in response.tools]}\n")
        return response.tools
    
    async def cleanup(self):
        await self.exit_stack.aclose()


def reformat_tools_description_for_anthropic_bedrock(tools: list[types.Tool]):
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


def check_tool_call(response):
    """
    Check if the response contains a tool call and extract the relevant information.
    Args:
        response: The full object response from the LLM

    Returns:
        tool_call: The tool call response from the LLM
    """
    try:
        if response.stop_reason == "tool_use":
            print("type is tool_use")
            return response.content[1] # response.content format is [chat_message, tool_call]
    
        # return false if no tool call is found
        return False
        
    except Exception as e:
        print(f"Error checking tool call: {e}")
        return None

def get_user_input():
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


fake_news_story = """
Gas Flare Bitcoin Miners Cut Methane Emissions in Permian Basin
MIDLAND, TX - A consortium of Bitcoin mining operations in West Texas reported today that their gas reclamation efforts have prevented over 180,000 metric tons of methane from entering the atmosphere in the past year. By capturing and utilizing natural gas that would otherwise be flared at oil well sites, these mining operations are turning what was once waste into both cryptocurrency and environmental benefits.
"We're essentially monetizing waste gas while reducing greenhouse gas emissions," explained Sarah Chen, CEO of GreenHash Solutions, one of the leading companies in the initiative. "The same energy that would have been burned off into the atmosphere is now powering our mining rigs, and we're seeing real environmental impact."
Independent environmental assessments confirm that these operations have reduced methane emissions equivalent to removing 40,000 cars from the road. The success has drawn attention from other oil-producing regions looking to replicate the model.
Local officials report that the program has also created 75 new technical jobs in the region, with plans to expand operations to additional well sites in the coming months.
"""


async def main():
    client = SSE_MCP_Client()
    chat = AnthropicBedrock()
    model_name=os.getenv("BEDROCK_MODEL_NAME")
    print(f"Using model: {model_name}")
    try:
        await client.connect_to_server("http://localhost:5553/sse")
        tools = await client.get_tools()
        formatted_tools = reformat_tools_description_for_anthropic_bedrock(tools)

        messages = []
        user_message = input("User: ")
        # have hardcoded news story for now
        document_content = input("Document to summarize (leave blank for hardcoded news story): ")

        if document_content == "":
            document_content = fake_news_story # have a hardcoded news story for testing

        # create initial message
        chat_prompt = "You are a helpful assistant, you have the ability to call tools to achieve user requests.\n\n"
        chat_prompt += "User request: " + user_message + "\n\n"
        chat_prompt += "Document content: " + document_content
        messages.append({"role": "user", "content": chat_prompt}) # passing in as user message

        while True:
            # LLM call
            if user_message == "": # if user presses enter without typing anything, continue
                continue
            # send inputs to the LLM and get response
            # send messages to the LLM
            llm_response = chat.messages.create(
                model=model_name,
                max_tokens=2048,
                messages=messages,
                tools=formatted_tools
            )
            llm_text_response = llm_response.content[0].text.strip() # final assistant content cannot end with trailing whitespace
            print("LLM: ", llm_text_response)
            messages.append({"role": "assistant", "content": llm_text_response}) 
            # tool call loop, continue until no tool call is found
            while True:
                tool_call = check_tool_call(llm_response)
                if not tool_call:
                    break
                    
                print("tool call: ", tool_call)
                tool_response = await client.session.call_tool(tool_call.name, tool_call.input)
                tool_result_text = tool_response.content[0].text
                print("tool response: ", tool_result_text)
                messages.append({"role": "user", "content": f"Here is the tool result: {tool_result_text.strip()}"}) # final assistant content cannot end with trailing whitespace
                
                llm_response = chat.messages.create(
                    model=model_name,
                    max_tokens=2048,
                    messages=messages,
                    tools=formatted_tools,
                    temperature=0.1
                )
                llm_text_response = llm_response.content[0].text.strip()
                print("LLM: ", llm_text_response)
                messages.append({"role": "assistant", "content": llm_text_response})

            user_message = input("User: ")
            messages.append({"role": "user", "content": user_message})

    finally:
        await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main())