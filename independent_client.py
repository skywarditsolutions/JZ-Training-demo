import asyncio
import json
import os
import re
from typing import Optional
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from anthropic import AnthropicBedrock
from dotenv import load_dotenv

import mcp.types as types


load_dotenv()

# Only (?) supported model
model_name="anthropic.claude-3-5-sonnet-20240620-v1:0"

class MCPClient:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.chat = AnthropicBedrock()
        self.tools = []
    
    async def connect_to_server(self, server_url: str):
        """Connect to an MCP Server
        """
        print('Connecting to MCP server... :)')
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

    # async def call_summarize_document_tool(self, tool_call):
    #     """
    #     This method handles the tool call from the LLM and passes it to the server
    #     Args:
    #         LLM_tool_call: The tool call from the LLM
            
    #     Returns:
    #         tool_call: The tool call response from the MCP server
    #     """
    #     # call tool over the MCP connection established in connect_to_server, takes in tool name and args
    #     tool_result = await self.session.call_tool(tool_call.name, tool_call.input)
    #     return tool_result
    
    async def call_database_tool(self, tool_call):
        """Handle database-related tool calls"""
        tool_result = await self.session.call_tool(tool_call.name, tool_call.input)
        return tool_result
    
    async def call_populate_database_tool(self, tool_call):
        """"
        This method sends a tool call to populate a database(given data from user input) to the server and returns the response.
        Args:
                LLM_tool_call: The tool call from the LLM
                
            Returns:
                tool_call: The tool call response from the MCP server
        """
        tool_result = await self.session.call_tool(tool_call.name, tool_call.input)
        return tool_result
        
    def send_message(self, query_details: dict, user_message: Optional[str] = None, messages: Optional[list[dict[str,str]]] = None):        
        """
        This method sends a message to the LLM and returns the response

        Args:
            data_input: The data to be inserted and processed
            (optional) user_message: The user's message to the LLM
            (optional) messages: The list of messages of the chat history

        Returns:
            response: The response from the LLM
        """
        # if no messages, create a new list and inital chat message
        if not messages:
            messages = []
            chat_prompt = (
                "You are a database assistant that can help users query and interact with databases. "
                "You can understand natural language queries and convert them to SQL, then execute them safely.\n\n"
            )

            if user_message:
                chat_prompt += f"User request: {user_message}\n\n"

                # Format query details for the prompt
                details_str = "\n".join(f"{k}: {v}" for k, v in query_details.items())
                chat_prompt += f"Database connection details:\n{details_str}\n\n"
                
                messages.append({"role": "user", "content": chat_prompt})
            # chat_prompt += "User request: " + user_message + "\n\n"
            # chat_prompt += "Data Input: " + data_input + "\n\n"
            # messages.append({"role": "user", "content": chat_prompt}) # passing in as user message
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
        data_input = {}
        user_message = input("User: ")
        # # Get database connection details
        sql_server_url = input("SQL server URL: ")
        sql_username = input("SQL username: ")
        sql_password = input("SQL password: ")

        query_details = {
            "sql_server_url": sql_server_url,
            "sql_username": sql_username,
            "sql_password": sql_password
        }
        
        print("\nYou can now ask questions about your database in natural language.")
        print("Type 'exit' to quit.\n")
        
        while True:
            user_message = input("Query: ")
            if user_message.lower() == 'exit':
                break
                
            if not user_message:
                continue
                
            # Send message to LLM
            response = self.send_message(
                query_details=query_details,
                user_message=user_message,
                messages=messages
            )
            
            # Print initial LLM response
            llm_text_response = response.content[0].text.strip()
            print(llm_text_response)
            print("\nProcessing query...")
            
            # Check for and handle tool calls
            tool_call = self.check_tool_call(response)
            if tool_call:
                print("Executing query...")
                tool_response = await self.call_database_tool(tool_call)
                
                # Parse and format the tool response
                try:
                    result = json.loads(tool_response.content[0].text)
                    if result.get("success"):
                        print("\nQuery results:")
                        print(json.dumps(result["results"], indent=2))
                    else:
                        print(f"\nError executing query: {result.get('error', 'Unknown error')}")
                except json.JSONDecodeError:
                    print("\nRaw response:", tool_response.content[0].text)
                    
                messages.append({"role": "assistant", "content": f"Query executed. {tool_response.content[0].text.strip()}"})
            else:
                print("\nLLM Response:", llm_text_response)
                messages.append({"role": "assistant", "content": llm_text_response})
            
            print("\n" + "-"*50 + "\n")

        # while True:
        #     # LLM call
        #     if data_input == "":
        #         # This is a fallback for if the data input is empty.
        #         data_input = "Please tell us the current state of the band Celtic Frost, or if not available, of its frontman Tom G. Warrior or his other band Triptykon."
        #         print('data input about best band in the world, Celtic Frost:', data_input)
        #         # data_input = fake_news_story # have a hardcoded news story for testing
        #     if user_message == "": # if user presses enter without typing anything, continue
        #         continue
        #     # send inputs to the LLM and get response
        #     response = self.send_message(user_message=user_message, data_input=data_input, messages=messages)
        #     llm_text_response = response.content[0].text.strip() # final assistant content cannot end with trailing whitespace
        #     print("LLM: ", llm_text_response)
        #     messages.append({"role": "assistant", "content": llm_text_response}) 
        #     # check if the response contains a tool call
        #     tool_call = self.check_tool_call(response)
        #     if tool_call:
        #         tool_response = await self.call_populate_database_tool(tool_call)
        #         tool_result_text = tool_response.content[0].text
        #         print("tool response: ", tool_result_text)
        #         messages.append({"role": "assistant", "content": f"Tool summary: {tool_result_text.strip()}"})# final assistant content cannot end with trailing whitespace
        #     else:
        #         messages.append({"role": "assistant", "content": llm_text_response})
        #     user_message = input("User: ")
    
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


# fake_news_story = """
# Gas Flare Bitcoin Miners Cut Methane Emissions in Permian Basin
# MIDLAND, TX - A consortium of Bitcoin mining operations in West Texas reported today that their gas reclamation efforts have prevented over 180,000 metric tons of methane from entering the atmosphere in the past year. By capturing and utilizing natural gas that would otherwise be flared at oil well sites, these mining operations are turning what was once waste into both cryptocurrency and environmental benefits.
# "We're essentially monetizing waste gas while reducing greenhouse gas emissions," explained Sarah Chen, CEO of GreenHash Solutions, one of the leading companies in the initiative. "The same energy that would have been burned off into the atmosphere is now powering our mining rigs, and we're seeing real environmental impact."
# Independent environmental assessments confirm that these operations have reduced methane emissions equivalent to removing 40,000 cars from the road. The success has drawn attention from other oil-producing regions looking to replicate the model.
# Local officials report that the program has also created 75 new technical jobs in the region, with plans to expand operations to additional well sites in the coming months.
# """


async def main():
    client = MCPClient()
    print('CLIENT HERE', client)
    try:
        await client.connect_to_server("http://localhost:5553/sse")
        response = await client.chat_loop()
        print('response', response)
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())