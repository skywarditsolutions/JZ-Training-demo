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
    return response.content

# modified from fastMCP example
#  @mcp.list_tools() not necessary for fastMCP
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="comparison_documents",
            description="Analyze texts and identify and show differences",
            inputSchema={
                "name": "comparison_documents",
                "required": ["document_content"],
                "properties": {
                    "truthdoc_content": {
                        "type": "string",
                        "description": "The verified document that the document_content will be compared to"
                    },
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
        )
    ]

if __name__ == "__main__":
    mcp.run(transport="stdio")