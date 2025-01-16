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
mcp = FastMCP("Comparison")


@mcp.tool()
async def comparison_documents(document_content: str, truthdoc_content: str) -> str:
    """Analyze Text content"""

    messages = []
    # claude SDK doesn't let you do system prompt?
    user_prompt = """You are a helpful assistant that compares documents. You identify differences in the numerical values the user provides
                    while comparing it to a 'truth' document. You also are able to note minor variations but knowing that the documents
                    are overall the same. 
                    Return the feedback in <summary></summary> tags.
                """
    user_prompt += f"\n\nDocument content: {document_content}, Truthdoc content : {truthdoc_content}"
    messages.append({"role": "user", "content": user_prompt}) # passing in as user message
    

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

# modified from fastMCP example
#  @mcp.list_tools() not necessary for fastMCP
# For comparison tool
types.Tool(
    name="comparison_documents",
    description="Analyze texts and identify and show differences",
    inputSchema={
        "name": "comparison_documents",
        "required": ["document_content", "truthdoc_content"],  # Both required
        "properties": {
            "truthdoc_content": {
                "type": "string",
                "description": "The verified document that the document_content will be compared to"
            },
            "document_content": {
                "type": "string",
                "description": "The content of the document to analyze"
            }
        }
    }
),
# For summarize tool
types.Tool(
    name="summarize_document",  # Fix name to match function
    description="Analyze and summarize document content",
    inputSchema={
        "name": "summarize_document",
        "required": ["document_content"],
        "properties": {
            "document_content": {
                "type": "string",
                "description": "The content of the document to analyze"
            }
        }
    }
)

if __name__ == "__main__":
    mcp.run(transport="stdio")