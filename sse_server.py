"""MCP server for summarizing and comparing documents."""

import re
from typing import Any, List, Optional

import requests
from anthropic import AnthropicBedrock
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.types import Tool
from pydantic import BaseModel, Field

load_dotenv()

MODEL_NAME = "anthropic.claude-3-5-sonnet-20240620-v1:0"

chat = AnthropicBedrock()
mcp = FastMCP("Summarizer")


@mcp.tool()
async def test_regex(regex_pattern: str, text_to_search: str) -> str:
    """Test regex pattern on text to search and return the captured groups."""
    try:
        print(f"regex_pattern: {regex_pattern}, text_to_search: {text_to_search}")
        pattern = re.compile(regex_pattern)
        matches = pattern.findall(text_to_search)
        print(f"matches: {matches}")
        if matches:
            match_text = ", ".join(str(match) for match in matches)
            return f"The regex pattern captured the following groups: {match_text}"
        return "Regex pattern not found in text"
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
async def fetch_bitcoin_price() -> str:
    """Fetch the current Bitcoin price from Coingecko."""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            bitcoin_price = data['bitcoin']['usd']
            return f"The current Bitcoin price is {bitcoin_price} USD."
        print(f"Error: Unable to fetch data. Status code: {response.status_code}")
        return None
    except requests.RequestException as e:
        print(f"Error: {e}")
        return None


class SummarizeFile(BaseModel):
    """Model for file summarization input."""

    file_name: str = Field(description="The name of the file to summarize")
    file_content: Optional[str] = Field(
        None,
        description="The contents of the file to summarize, "
        "will be fetched from the file name if not provided",
    )


class DbFiles(BaseModel):
    """Model for database file input."""

    name: str = Field(description="The document file name")
    content: Optional[str] = Field(
        None,
        description="The text content of the file to compare, "
        "will be fetched from the database if not provided",
    )


class CompareFiles(BaseModel):
    """Model for file comparison input."""

    files: List[DbFiles]


@mcp.tool()
async def compare_documents(compare_files: List[DbFiles]) -> str:
    """
    Compare documents and provide a summary.

    Args:
        compare_files: A list of documents to compare

    Returns:
        LLM response obj with summary of the document comparison
    """
    user_prompt = (
        "You are a helpful assistant that compares documents. "
        "You provide a thorough comparison of the documents and highlight "
        "anything surprising or interesting. Return the comparison in "
        "<comparison></comparison> tags."
    )
    user_prompt += "\n\nDocuments: " + "\n\n".join(
        doc.content for doc in compare_files if doc.content
    )
    messages = [{"role": "user", "content": user_prompt}]

    response = chat.messages.create(
        model=MODEL_NAME,
        max_tokens=2048,
        messages=messages,
    )
    beginning_comparison = response.content[0].text.split("<comparison>")[1]
    comparison = beginning_comparison.split("</comparison>")[0]
    return comparison


@mcp.tool()
async def summarize_file(uploaded_file: SummarizeFile) -> str:
    """
    Analyze text content and provide a summary.

    Args:
        uploaded_file: The file to summarize

    Returns:
        LLM response obj with summary of the document
    """
    print("uploaded_file: ", uploaded_file)
    user_prompt = (
        "You are a helpful assistant that summarizes documents. "
        "You provide a thorough summary of the document and highlight "
        "anything surprising or interesting. Return the summary in "
        "<summary></summary> tags."
    )
    user_prompt += f"\n\nText content: {uploaded_file.file_content}"
    messages = [{"role": "user", "content": user_prompt}]

    response = chat.messages.create(
        model=MODEL_NAME,
        max_tokens=2048,
        messages=messages,
    )
    beginning_summary = response.content[0].text.split("<summary>")[1]
    summary = beginning_summary.split("</summary>")[0].strip()

    print("summary: ", summary)
    print("summary completed")
    return summary


async def list_tools() -> List[Tool]:
    """List the tools available to the LLM."""
    return [
        Tool(
            name="test_regex",
            description="Test regex pattern on text to search and return the captured groups",
            inputSchema={
                "name": "test_regex",
                "required": ["regex_pattern", "text_to_search", "answer_text"],
                "properties": {
                    "regex_pattern": {
                        "type": "string",
                        "description": "The regex pattern to test, this will be compiled with python's re.compile()",
                    },
                    "text_to_search": {
                        "type": "string",
                        "description": "The text to search",
                    },
                },
            },
        ),
        Tool(
            name="fetch_bitcoin_price",
            description="Fetches the current Bitcoin price from Coingecko",
            inputSchema={
                "name": "fetch_bitcoin_price",
            },
        ),
        Tool(
            name="compare_files",
            description="Compare files and provide a comparison",
            inputSchema=CompareFiles.model_json_schema(),
        ),
        Tool(
            name="summarize_file",
            description="Summarize a file's content and return a summary",
            inputSchema=SummarizeFile.model_json_schema(),
        ),
    ]


if __name__ == "__main__":
    mcp.run(transport="sse")
