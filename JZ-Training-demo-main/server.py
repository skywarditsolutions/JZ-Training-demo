from mcp.server.fastmcp import FastMCP
from typing import Optional
#import PyPDF2
import io
from typing import Any
#import asyncio
#import httpx
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio
from anthropic import AnthropicBedrock

from dotenv import load_dotenv

load_dotenv()

# Only (?) supported model
model_name="anthropic.claude-3-5-sonnet-20240620-v1:0"

chat = AnthropicBedrock()
# Create an MCP server
mcp = FastMCP("Summarizer")


@mcp.tool()
async def summarize_document(document_content: str) -> str:
    """Analyze Text content
    Args:
        document_content: The content of the document to analyze

    Returns:
        LLM response obj with summary of the document
    """

    messages = []
    # claude SDK doesn't let you do system prompt?
    user_prompt = "You are a helpful assistant that summarizes documents. You provide a thorough summary of the document and highlight anything surprising or interesting. Return the summary in <summary></summary> tags."
    user_prompt += f"\n\nDocument content: {document_content}"
    messages.append({"role": "user", "content": user_prompt}) # passing in as user message
    
    # send messages to the LLM
    response = chat.messages.create(
                model=model_name,
        max_tokens=2048,
        messages=messages
    )
    # originally wanted to use re.search(?<=<summary>)(.*?)(?=</summary>)
    # regex would cause the process to hang on the LLM call (too computationally expensive?), splitting the string is a quick fix
    # LLM returns a string with <summary> and </summary> tags, so we split the string twice to isolate the summary
    beginning_summary = response.content[0].text.split("<summary>")[1]
    summary = beginning_summary.split("</summary>")[0] # isolate the summary
    # TODO error handling
    return summary

@mcp.tool()
async def populate_database(data_input: int) -> str:
    """Populates a database with selected data from user
    
    Args:
        data from user to input into a database

    Returns: 
        a database consisting of the selected data from user
    """
    
    return f"Hello I am a tool that populates a database! This is the integer you gave me: {data_input}."

# modified from fastMCP example
# @mcp.list_tools() not necessary for fastMCP
async def list_tools() -> list[types.Tool]:
    """
    List the tools available to the LLM
    """
    return [
        types.Tool(
            name="summarize_document",
            description="Analyze text and provide a summary",
            inputSchema={
                "name": "summarize_document",
                "required": ["document_content"],
                "properties": {
                    "document_content": {
                        "type": "string",
                        "description": "The content of the document to analyze"
                    },
                    "user_message": {
                        "type": "string",
                        "description": "The user's message"
                    },
                    "messages": {
                        "type": "array",
                        "description": "The messages to send to the model"
                    }
                }
            }
        ),
    

        types.Tool(
            name="populate_database",
            description="Populates a database with selected data from user",
            inputSchema={
                "name": "populate_database",
                "required": [
                    "sql_server_url", 
                    "sql_username", 
                    "sql_password", 
                    "amt_of_data_to_mock"
                ],
                "properties": {
                    # "data_input": {
                    #     "type": "int", #Can eventually accept different data types beyond ints
                    #     "description": "The data to put into a database"
                    # },
                    "sql_server_url": {
                        "type": "string",
                        "description": "The SQL server connection url we would like to connect to."
                    },
                    "sql_username": {
                        "type": "string",
                        "description": "The username for the SQL database."
                    },
                    "sql_password": {
                        "type": "string",
                        "description": "The password for the user name that wants to sign into the SQL database"
                    },
                    "amt_of_data_to_mock": {
                        "type": "int",
                        "description": "The amount of SQL rows we would like to mock."
                    },
                    # "user_message": {
                    #     "type": "string", # in theory, the user is asking a question (string) to give our bot context
                    #     "description": "The user's data"
                    # },
                    "messages": {
                        "type": "string",
                        "description": "The messages to send to the model"
                    }
                }
            }
        )
    ]

if __name__ == "__main__":
    mcp.run(transport="stdio")