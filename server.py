from mcp.server.fastmcp import FastMCP
from typing import Optional
import PyPDF2
import io
from typing import Any
import asyncio
import httpx
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
async def analyze_content(document_content: str, user_message: Optional[str] = None, messages: Optional[list[str]] = None) -> str:
    """Analyze text and optional PDF content"""
    if not messages:
        messages = []
        system_prompt = "You are a helpful assistant that summarizes documents. You provide a thorough summary of the document and highlight anything surprising or interesting. Return the summary in <summary></summary> tags."
        messages.append({"role": "system", "content": system_prompt})
        user_prompt = f"Document content: {document_content}\n\nUser message: {user_message}"
        messages.append({"role": "user", "content": user_prompt})
    else:
        messages.append({"role": "user", "content": user_message})

    response = chat.messages.create(
                model=model_name,
        max_tokens=2048,
        messages=messages
    )

    return response.content

#  @mcp.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="analyze_content",
            description="Analyze text and optional PDF content",
            inputSchema={
                "name": "analyze_content",
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
        )
    ]


if __name__ == "__main__":
    mcp.run(transport="stdio")