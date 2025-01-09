from mcp.server.fastmcp import FastMCP
from typing import Optional
import PyPDF2
import io

# Create an MCP server
mcp = FastMCP("sever")


@mcp.tool()
def analyze_content(text: str) -> str:
    """Analyze text and optional PDF content"""
    
    combined_content = text
    
    return f"Analysis of: {combined_content}"

if __name__ == "__main__":
    mcp.run()