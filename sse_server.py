from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP
from typing import Optional
#import PyPDF2
import re
import io
from typing import Any
#import asyncio
#import httpx
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio
from anthropic import AnthropicBedrock

import requests

from dotenv import load_dotenv

load_dotenv()

model_name="anthropic.claude-3-5-sonnet-20240620-v1:0"

chat = AnthropicBedrock()
# Create an MCP server
mcp = FastMCP("Summarizer")

@mcp.tool()
async def test_regex(regex_pattern: str, text_to_search: str)->str:
    """Test regex pattern on text to search and return the captured groups"""
    try:
        print(f"regex_pattern: {regex_pattern}, text_to_search: {text_to_search}")
        pattern = re.compile(regex_pattern)
        matches = pattern.findall(text_to_search)    
        print(f"matches: {matches}")
        if matches:
            match_text = ', '.join(str(match) for match in matches)
            result_text = f"The regex pattern captured the following groups: {match_text}"
            return result_text
        else:
            return "Regex pattern not found in text"
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
async def fetch_bitcoin_price()->str:
    """Fetches the current Bitcoin price from Coingecko"""
    try:
        # CoinGecko API endpoint for Bitcoin price in USD
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        
        # Send GET request to the API
        response = requests.get(url)
        
        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()
            
            # Extract the Bitcoin price in USD
            bitcoin_price = data['bitcoin']['usd']
            
            return f"The current Bitcoin price is {bitcoin_price} USD."
        else:
            print(f"Error: Unable to fetch data. Status code: {response.status_code}")
            return None
    
    except requests.RequestException as e:
        print(f"Error: {e}")
        return None

class CompareFiles(BaseModel):
    files: list[str] = Field(description="A list of document names")
    file_contents: Optional[list[str]] = Field(None, description="A list of file contents to compare, will be fetched from the file names if not provided")

@mcp.tool()
async def compare_documents(compare_files: CompareFiles) -> str:
    """
    Args:
        compare_files: A list of documents to compare

    Returns:
        LLM response obj with summary of the document
    """

    messages = []
    # claude SDK doesn't let you do system prompt?
    user_prompt = "You are a helpful assistant that compares documents. You provide a thorough comparison of the documents and highlight anything surprising or interesting. Return the comparison in <comparison></comparison> tags."
    user_prompt += f"\n\nDocuments: {"\n\n".join(compare_files.file_contents)}"
    messages.append({"role": "user", "content": user_prompt}) # passing in as user message
    
    # send messages to the LLM
    response = chat.messages.create(
                model=model_name,
        max_tokens=2048,
        messages=messages
    )
    beginning_comparison = response.content[0].text.split("<comparison>")[1]
    comparison = beginning_comparison.split("</comparison>")[0] # isolate the comparison
    # TODO error handling
    return comparison

@mcp.tool()
async def summarize_text(text_content: str) -> str:
    """Analyze Text content
    Args:
        text_content: The content of the text to analyze

    Returns:
        LLM response obj with summary of the document
    """

    messages = []
    # claude SDK doesn't let you do system prompt?
    user_prompt = "You are a helpful assistant that summarizes documents. You provide a thorough summary of the document and highlight anything surprising or interesting. Return the summary in <summary></summary> tags."
    user_prompt += f"\n\nText content: {text_content}"
    messages.append({"role": "user", "content": user_prompt}) # passing in as user message
    
    # send messages to the LLM
    response = chat.messages.create(
                model=model_name,
        max_tokens=2048,
        messages=messages
    )
    beginning_summary = response.content[0].text.split("<summary>")[1]
    summary = beginning_summary.split("</summary>")[0] # isolate the summary
    # TODO error handling
    return summary

# modified from fastMCP example
#  @mcp.list_tools() not necessary for fastMCP
async def list_tools() -> list[types.Tool]:
    """
    List the tools available to the LLM
    """
    return [
        types.Tool(
            name="test_regex",
            description="Test regex pattern on text to search and return the captured groups",
            inputSchema={
                "name": "test_regex",
                "required": ["regex_pattern", "text_to_search", "answer_text"],
                "properties": {
                    "regex_pattern": {
                        "type": "string",
                        "description": "The regex pattern to test, this will be compiled with python's re.compile()"
                    },
                    "text_to_search": {
                        "type": "string",
                        "description": "The text to search"
                    }
                }
            }
        ),
        types.Tool(
            name="fetch_bitcoin_price",
            description="Fetches the current Bitcoin price from Coingecko",
            inputSchema={
                "name": "fetch_bitcoin_price",
            }
        ),
        types.Tool(
            name="compare_files",
            description="Compare files and provide a comparison",
            inputSchema=CompareFiles.model_json_schema()
        ),
        types.Tool(
            name="summarize_text",
            description="Analyze text and provide a summary",
            inputSchema={
                "name": "summarize_text",
                "required": ["text_content"],
                "properties": {
                    "text_content": {
                        "type": "string",
                        "description": "The content of the document to analyze"
                    }
                }
            }
        )
    ]

if __name__ == "__main__":
    mcp.run(transport="sse")