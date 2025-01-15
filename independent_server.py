
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

from data_pop.database_connection import DatabaseConnection
from data_pop.database_populator import DatabasePopulator
from data_pop.cursor_manager import CursorManager

import json
import requests

from dotenv import load_dotenv

load_dotenv()

# Only (?) supported model
model_name="anthropic.claude-3-5-sonnet-20240620-v1:0"

chat = AnthropicBedrock()
# Create an MCP server
# mcp = FastMCP("Summarizer")
mcp = FastMCP("Populator")

class LLMDatabaseManager:
    def __init__(self, server: str, username: str, password: str):
        """
        Initialize the manager with database connection parameters
        
        Args:
            server: SQL Server instance address
            username: Database username
            password: Database password
        """
        self.db_connection = DatabaseConnection(
            server=server,
            username=username,
            password=password
        )
        
    def get_sql_from_llm(self, prompt: str) -> str:
        """
        Get SQL query from Claude based on natural language prompt.
        """
        messages = [{
            "role": "user",
            "content": f"""Generate only the SQL query for: {prompt}
            Rules:
            - Generate only the SQL query without any explanation
            - The query should be safe and follow best practices
            - Do not use DROP, DELETE, or TRUNCATE commands
            """
        }]
        
        response = chat.messages.create(
            model=model_name,
            max_tokens=150,
            temperature=0,
            messages=messages
        )
        print('response', response)
        return response.content[0].text.strip()
    
    def validate_query(self, query: str) -> bool:
        """Validate if the query is safe to execute."""
        dangerous_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'UPDATE', 'INSERT']
        query_upper = query.upper()
        return not any(keyword in query_upper for keyword in dangerous_keywords)
    
    def execute_query(self, query: str) -> dict[str, Any]:
        """Execute SQL query and return results."""
        if not self.validate_query(query):
            return {"success": False, "error": "Query contains potentially dangerous operations"}
            
        try:
            # Use the execute_query method from DatabaseConnection
            results = []
            connection = self.db_connection.get_connection(None)
            
            try:
                cursor = connection.cursor()
                cursor.execute(query)
                
                # Get column names
                columns = [column[0] for column in cursor.description]
                
                # Fetch results
                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))
                
                return {"success": True, "results": results}
                
            finally:
                cursor.close()
                connection.close()
                
        except Exception as e:
            return {"success": False, "error": str(e)}

@mcp.tool()
async def query_database(sql_server_url: str, sql_username: str, sql_password: str, 
                        natural_language_query: str) -> str:
    """
    Query database using natural language that gets converted to SQL
    """
    try:
        # Initialize database manager
        db_manager = LLMDatabaseManager(
            server=sql_server_url,
            username=sql_username,
            password=sql_password
        )
        
        # Generate and execute query
        sql_query = db_manager.get_sql_from_llm(natural_language_query)
        print('sql query', sql_query)
        results = db_manager.execute_query(sql_query)
        print('results', results)
        return json.dumps({
            "success": True,
            "sql_query": sql_query,
            "results": results.get("results", []),
            "error": results.get("error")
        }, indent=2)
            
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)

if __name__ == "__main__":
    mcp.run(transport="sse")
    
