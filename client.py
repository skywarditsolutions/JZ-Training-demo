import asyncio
import json
import os
import re
from typing import Optional
from contextlib import AsyncExitStack
# get_close_matches allows 
from difflib import get_close_matches
import sys
#allows you to input the file path that you downloaded onto computer
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from dotenv import load_dotenv

load_dotenv()

from anthropic import AnthropicBedrock

import mcp.types as types

#from haystack.components.builders.prompt_builder import PromptBuilder



# Only (?) supported model
model_name="anthropic.claude-3-5-sonnet-20240620-v1:0"

class MCPClient:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.chat = AnthropicBedrock()
        self.tools = []
        #words that could indicate comparing
        self.comparison_words = [
            "compare", "comparison", "difference", "differences", "diff",
            "contrast", "versus", "vs", "distinction", "distinguish",
            "analyze", "check", "review", "examine", "look at"
        ]
        self.summary_words = [
            "summarize", "summary", "outline", "overview", "recap",
            "digest", "brief", "gist", "roundup", "synopsis",
            "sum up", "wrap up", "highlight", "breakdown", "abstract"
        ]
    def get_multiline_input(self, prompt: str) -> str:
        """
        Gets single line input from user
        """
        try:
            return input(f"{prompt}: ")
        except EOFError:
            return ""
    def read_file_content(self, file_path: str) -> str:
        """
        Reads content from a file, handling different file types (File i/o)
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                print(f"Error: File {file_path} does not exist")
                return ""
                
            # reads file content based on extension
            content = file_path.read_text(encoding='utf-8')
            return content
            
        except Exception as e:
            print(f"Error reading file: {e}")
            return ""

    def get_document_input(self, prompt: str) -> str:
        """
        Gets document content either from file or direct input
        """
        input_type = input(f"{prompt}\nEnter 'file' to provide a file path, or 'text' to enter text directly: ").lower()
        
        if input_type == 'file':
            file_path = input("Enter file path: ")
            return self.read_file_content(file_path)
        else:
            return self.get_multiline_input("Enter your text")
            
    async def connect_to_server(self, server_script_path: str):
        """Connect to an MCP Server
           Args: server_script_path (str): The path to the python server script (.py)
        """
        #checks for python only
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
        formatted_tools = reformat_tools_description(response.tools)
        self.tools = formatted_tools
        #self.tools = test_dummy_tools()
        #self.tools = test_dummy_tools()
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
    
    async def call_compare_documents_tool(self, tool_call):
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
    
    
    def is_comparison_request(self, user_message: str) -> bool:
        """
        Check if the user's message is requesting a comparison,
        using fuzzy matching to catch typos and variations
        """
        # Convert message to lowercase and split into words
        user_words = user_message.lower().split()
        
        # Check each word in the user's message
        for word in user_words:
            # Use get_close_matches to find similar words
            matches = get_close_matches(word, self.comparison_words, n=1, cutoff=0.8)
            if matches:
                return True
                
        # Check for common two-word phrases
        message = user_message.lower()
        two_word_phrases = ["look at", "side by"]
        if any(phrase in message for phrase in two_word_phrases):
            return True
            
        return False
    def is_summarize_request(self, user_message: str) -> bool:
        """
        Check if the user's message is requesting a comparison,
        using fuzzy matching to catch typos and variations
        """
        # Convert message to lowercase and split into words
        user_words = user_message.lower().split()
        
        # Check each word in the user's message
        for word in user_words:
            # Use get_close_matches to find similar words
            matches = get_close_matches(word, self.summary_words, n=1, cutoff=0.8)
            if matches:
                return True
                
        # Check for common two-word phrases
        message = user_message.lower()
        two_word_phrases = ["main point", "overal idea"]
        if any(phrase in message for phrase in two_word_phrases):
            return True
            
        return False

    def send_message(self, document_content: str, truthdoc_content: Optional[str] = None, user_message: Optional[str] = None, messages: Optional[list[dict[str,str]]] = None):
        """
        This method sends a message to the LLM and returns the response
        """
        if not messages:
            messages = []
            system_prompt = "You are a helpful assistant, you have the ability to call tools to achieve user requests."
            messages.append({"role": "user", "content": system_prompt})
        
        # Construct the full message with all components
        full_message = ""
        if user_message:
            full_message += f"User request: {user_message}\n\n"
        if document_content:
            full_message += f"Document content: {document_content}\n\n"
        if truthdoc_content:
            full_message += f"Truth Document content: {truthdoc_content}"
        
        # Add the constructed message to conversation history
        messages.append({"role": "user", "content": full_message})
        
        # Send messages to the LLM
        response = self.chat.messages.create(
            model=model_name,
            model=model_name,
            max_tokens=2048,
            messages=messages,
            tools=self.tools
        )
        return response
    
        return response
    
    def check_tool_call(self, response):
        """
        Check if the response contains a tool call and extract the relevant information.
        Args:
            response: The full object response from the LLM

        Returns:
            tool_call: The tool call response from the server
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
            if response.stop_reason == "tool_use":
                print("type is tool_use")
                return response.content[1] # response format is [chat_message, tool_call]
        
            # return false if no tool call is found
            return False
            
        except Exception as e:
            print(f"Error checking tool call: {e}")
            return None

    def get_user_input(self):
        # """parse multiline input"""
        # # TODO: finish this function
        # """parse multiline input"""
        # # TODO: finish this function
        lines = []
        print("User: ")

        while True:
            try: 
                return input("User: ")
                # line = input()
                # lines.append(line)
            except EOFError:
                break
        return lines
    
    def chat_loop(self):
        messages = []
        while True:
            user_message = input("User: ")
            
            if self.is_comparison_request(user_message):
                # Get document contents using new input methods
                document_content = self.get_document_input("Document")
                if not document_content:
                    print("No content provided for first document. Please try again.")
                    continue
                    
                truthdoc_content = self.get_document_input("Truth Document")
                if not truthdoc_content:
                    print("No content provided for second document. Please try again.")
                    continue
                
                # Send the message without duplicating content
                response = self.send_message(
                    document_content=document_content,
                    truthdoc_content=truthdoc_content,
                    user_message=user_message,  # Just send original user message
                    messages=messages
                )
                
                llm_text_response = response.content[0].text.strip()
                print("LLM: ", llm_text_response)
                messages.append({"role": "assistant", "content": llm_text_response})
                
                # Check for tool call
                tool_call = self.check_tool_call(response)
                if tool_call:
                    tool_response = await self.call_compare_documents_tool(tool_call)
                    summary = tool_response.content[0].text
                    print("Tool summary: ", summary)
                    # Add tool response to chat history
                    messages.append({"role": "assistant", "content": f"Tool summary: {summary.strip()}"})
                    
            elif self.is_summarize_request(user_message):
                document_content = self.get_document_input("Document")
                if not document_content:
                    print("No content provided for first document. Please try again.")
                    continue

                summary_message = f"""
                    User request: {user_message}
                    Document content: {document_content}"""
                
                response = self.send_message(
                    document_content=document_content,
                    user_message=summary_message,
                    messages=messages
                )
                
                llm_text_response = response.content[0].text.strip()
                print("LLM: ", llm_text_response)
                messages.append({"role": "assistant", "content": llm_text_response})
                
                # Check for tool call
                tool_call = self.check_tool_call(response)
                if tool_call:
                    tool_response = await self.call_summarize_document_tool(tool_call)
                    summary = tool_response.content[0].text
                    print("Tool summary: ", summary)
                    # Add tool response to chat history
                    messages.append({"role": "assistant", "content": f"Tool summary: {summary.strip()}"})

            else:
                # Handle regular conversation
                response = self.send_message(
                    document_content="",
                    truthdoc_content="",
                    user_message=user_message,
                    messages=messages
                )
                llm_text_response = response.content[0].text.strip()
                print("LLM: ", llm_text_response)
                messages.append({"role": "assistant", "content": llm_text_response})
    
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
            "input_schema": tool.inputSchema, # changing camelCase to snake_case so anthropic can use it
        }
        reformatted_tools.append(current_tool)

    return reformatted_tools

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