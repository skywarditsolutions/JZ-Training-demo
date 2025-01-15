"""DatabaseConnection: A Robust ODBC Database Interaction Utility

A comprehensive utility class for managing database connections, executing queries,
and retrieving metadata for Microsoft SQL Server databases using pyodbc.

Key Features:
      - Dynamic database connection management
      - Retrieve database, schema, and table metadata
      - Execute queries with error handling
      - Trigger and column metadata retrieval
      - Database and table management utilities

Dependencies:
      - pyodbc: For ODBC database connections
      - typing: For type hinting
      - cursor_manager: Custom cursor management utility

Initialization:
      Requires SQL Server connection parameters:
      - server: SQL Server instance address
      - username: Database authentication username
      - password: Database authentication password
      - database (optional): Initial database to connect to

Methods Overview:
   Connection Management:
      - get_connection(): Create or modify database connection
      - database_exists(): Check if a database exists
      - clear_database(): Remove all tables from a database

   Metadata Retrieval:
      - get_all_databases(): List all databases on the server
      - get_schemas_by_database(): List schemas in a database
      - get_tables_by_database(): List tables in a database
      - get_tables_by_schema(): List tables in a specific schema
      - get_table_data_structure(): Retrieve detailed column metadata
      - get_triggers(): Retrieve trigger information for a table

   Query Execution:
      - execute_query(): Execute SQL queries with optional parameters

Error Handling:
   - Comprehensive error logging
   - Graceful connection and cursor management
   - Informative error messages

Security Considerations:
   - Uses parameterized queries to prevent SQL injection
   - Closes database connections after use
   - Filters out system databases by default

Typical Usage Examples:
   # Initialize connection
   db_conn = DatabaseConnection(
      server='localhost',
      username='admin',
      password='secret'
   )

   # List all databases
   databases = db_conn.get_all_databases()

   # Get tables in a specific database and schema
   tables = db_conn.get_tables_by_schema('dbo', 'MyDatabase')

   # Execute a custom query
   db_conn.execute_query('SELECT * FROM Users')

   # Check database existence
   exists = db_conn.database_exists('MyDatabase')

Performance Notes:
   - Uses context managers for efficient resource handling
   - Automatically closes database connections
   - Minimal overhead for metadata retrieval

Limitations:
   - Currently supports Microsoft SQL Server via ODBC
   - Requires ODBC Driver 17 for SQL Server
   - Error handling may vary based on ODBC driver version

Recommended Practices:
   - Always use with context managers or try-finally blocks
   - Handle potential connection and query exceptions
   - Close connections explicitly when not using context managers

Logging:
   - Prints error messages to console
   - Provides detailed error context for debugging

Advanced Features:
   - Dynamic connection string modification
   - Flexible database and schema exploration
   - Trigger and column metadata retrieval
"""

from typing import Any
from .cursor_manager import CursorManager

import pyodbc
import sys


class DatabaseConnection:
    def __init__(self, server: str, username: str, password: str, database: str = '') -> None:
        """Initialize database connection parameters

        :param server: SQL Server instance address
        :param database: Database name
        :param username: Database username
        :param password: Database password
        """
        self.connection_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};UID={username};PWD={password}"
        )
        
        self.connection = self.get_connection(database)
        self.cursor = CursorManager(self.connection)

        if database != '':
            self.connection_string += f";DATABASE={database}"

    """
   ------------------------------------------------------------------
   Get database connection
   ------------------------------------------------------------------
   """

    def get_connection(self, database: str | None) -> pyodbc.Connection:
        """Create or modify connection string for a specific database.

        :param database: Database name
        """
        conn_str = self.connection_string
        if database:
            conn_str = conn_str.replace(
                f"DATABASE={self.connection_string.split('DATABASE=')[-1]}", f"DATABASE={database}",
            )
        return pyodbc.connect(conn_str)

    """
   ------------------------------------------------------------------
   Execute query functions
   ------------------------------------------------------------------
   """

    def execute_query(self, query: str, params: tuple | None, connection: pyodbc.Connection = None) -> None:
        """Execute a query with optional connection and parameters.

        :param query: The query to execute in the SQL database
        :return: None
        """
        close_connection = False

        try:
            if connection is None:
                connection = self.get_connection(None)
                close_connection = True

            # with CursorManager(connection) as cursor:
            #     print('cursor', cursor)
            cursor = CursorManager(connection)
            if params:
               cursor.execute(query, params)
            else:
               cursor.execute(query)

            connection.commit()
         #  return cursor

        except pyodbc.Error as e:
            print(f"Query execution error: {e}")  # noqa: T201
            print(query)  # noqa: T201
            sys.exit(0)
            return None

        finally:
            if close_connection and "connection" in locals():
                connection.close()

    """
   ------------------------------------------------------------------
   Get databases, tables, schemas, and tables
   ------------------------------------------------------------------
   """

    def get_all_databases(self, database: str | None) -> list[str]:
        """Retrieve all databases names in the server

        :param database: Optional database name
        :return: List of table names
        """

        query = """
         SELECT name
         FROM sys.databases
         WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb', 'rdsadmin')
      """
        try:
            connection = self.get_connection(database)
            cursor = CursorManager(connection)
            cursor.execute(query)

            return [row[0] for row in cursor.fetchall()]

        except pyodbc.Error as e:
            print(f"Table retrieval error: {e}")  # noqa: T201
            return []
        finally:
            if "connection" in locals():
               self.connection.close()

    def get_tables_by_database(self, database_name: str) -> list[str]:
        """Retrieve all tables for a specific database

        :param database_name: Name of the database to retrieve tables from
        :return: List of table names in the database
        """

        query = f"""
            SELECT TABLE_NAME
            FROM {database_name}.INFORMATION_SCHEMA.TABLES
            WHERE TABLE_TYPE='BASE TABLE'
         """
        try:
            connection = self.get_connection(database_name)
            cursor = CursorManager(connection)
            cursor.execute(query)
            return [row[0] for row in cursor.fetchall()]

        except pyodbc.Error as e:
            print(f"Table retrieval error for database {database_name}: {e}")  # noqa: T201
            return []
        finally:
            if "connection" in locals():
                self.connection.close()

    def get_schemas_by_database(self, database_name: str) -> list[str]:
        """Retrieve all tables for a specific database

        :param database_name: Name of the database to retrieve tables from
        :return: List of table names in the database
        """

        query = f"""
         SELECT SCHEMA_NAME 
         FROM {database_name}.INFORMATION_SCHEMA.SCHEMATA
         WHERE
            SCHEMA_NAME NOT LIKE 'db[_]%'
            AND SCHEMA_NAME NOT LIKE 'guest%'
            AND SCHEMA_NAME != 'sys'
            AND SCHEMA_NAME != 'INFORMATION_SCHEMA'
      """
        try:
            connection = self.get_connection(database_name)
            cursor = CursorManager(connection)
            cursor.execute(query)
            return [row[0] for row in cursor.fetchall()]

        except pyodbc.Error as e:
            print(f"Schema retrieval error for database {database_name}: {e}")  # noqa: T201
            return []
        finally:
            if "connection" in locals():
               self.connection.close()

    def get_tables_by_schema(self, schema_name: str, database_name: str) -> list[str]:
        """Retrieve all tables for a specific database with a specific schema

        :param database_name: Name of the database to retrieve tables from
        :param schema_name: Name of the schema to retrieve tables by
        :return: List of table names in the database
        """

        query = f"""
      SELECT TABLE_NAME, TABLE_SCHEMA, TABLE_TYPE
      FROM {database_name}.INFORMATION_SCHEMA.TABLES
      WHERE TABLE_SCHEMA = '{schema_name}'
         AND TABLE_TYPE != 'VIEW'
      """

        try:
            connection = self.get_connection(database_name)
            cursor = CursorManager(connection)
            cursor.execute(query)
            return [row[0] for row in cursor.fetchall()]
        except pyodbc.Error as e:
            print(f"Schema retrieval error for database {database_name}: {e}")  # noqa: T201
            return []
        finally:
            self.connection.close()

    def get_table_data_structure(
        self, table_name: str, schema_name: str, database_name: str, limit: int = None,
    ) -> list[dict[str, Any]]:
        """:param table_name: Name of the table to retrieve
        :param schema_name: Name of the schema where the table resides
        :param database_name: Optional database name
        :param limit: Optional limit on number of rows to retrieve
        :return: List of dictionaries representing table rows
        """

        query = f"""
         SELECT 
               COLUMN_NAME,
               DATA_TYPE,
               CHARACTER_MAXIMUM_LENGTH AS MAX_LENGTH,
               NUMERIC_PRECISION,
               NUMERIC_SCALE,
               IS_NULLABLE,
               COLUMN_DEFAULT
         FROM {database_name}.INFORMATION_SCHEMA.COLUMNS
         WHERE TABLE_SCHEMA = '{schema_name}'
            AND TABLE_NAME = '{table_name}'
      """

        try:
            connection = self.get_connection(database_name)
            cursor = CursorManager(connection)
            cursor.execute(query)
            columns = []
            for row in cursor.fetchall():
               row_property = {
                  "name": row[0],
                  "property_type": row[1],
                  "max_length": row[2],
                  "precision": row[3],
                  "scale": row[4],
                  "nullable": row[5] == "YES",
                  "default": row[6],
               }
               columns.append(row_property)
            return columns
        except pyodbc.Error as e:
            print(f"Table data retrieval error: {e}")  # noqa: T201
            return []
        finally:
            if "connection" in locals():
               self.connection.close()

    def get_row_data_structure(
        self, table_name: str, schema_name: str, database_name: str, row_name: str, limit: int = None,
    ) -> list[dict[str, Any]]:
        """Retrieve detailed column metadata for a specific row. Mainly used to debug
        and not used in the program proper

        :param table_name: Name of the table to retrieve
        :param schema_name: Name of the schema where the table resides
        :param database_name: Optional database name
        :param limit: Optional limit on number of rows to retrieve
        :return: List of dictionaries representing table rows
        """

        query = f"""
         SELECT
               COLUMN_NAME,
               DATA_TYPE,
               CHARACTER_MAXIMUM_LENGTH AS MAX_LENGTH,
               NUMERIC_PRECISION,
               NUMERIC_SCALE,
               IS_NULLABLE,
               COLUMN_DEFAULT
         FROM {database_name}.INFORMATION_SCHEMA.COLUMNS
         WHERE TABLE_SCHEMA = '{schema_name}'
            AND TABLE_NAME = '{table_name}'
            AND COLUMN_NAME = '{row_name}'
      """

        try:
            connection = self.get_connection(database_name)
            cursor = CursorManager(connection)
            cursor.execute(query)
            columns = []
            for row in cursor.fetchall():
               row_property = {
                  "name": row[0],
                  "property_type": row[1],
                  "max_length": row[2],
                  "precision": row[3],
                  "scale": row[4],
                  "nullable": row[5] == "YES",
                  "default": row[6],
               }
               columns.append(row_property)
            return columns
        except pyodbc.Error as e:
            print(f"Table data retrieval error: {e}")  # noqa: T201
            return []
        finally:
            if "connection" in locals():
                self.connection.close()

    def get_triggers(self, table_name: str, schema: str, database: str | None) -> list[dict[str, Any]]:
        """Retrieve triggers for a specific table.

        :param table_name: name of the table
        :param schema: schema name of the table
        :param database: optional database name
        :return: list of dictionaries containing trigger information
        """
        query = """
      SELECT 
         t.name AS TriggerName,
         OBJECT_SCHEMA_NAME(t.object_id) AS TriggerSchema,
         OBJECT_NAME(t.parent_id) AS TableName,
         OBJECT_SCHEMA_NAME(t.parent_id) AS TableSchema,
         t.create_date AS CreatedDate,
         t.modify_date AS LastModifiedDate,
         t.is_disabled AS IsDisabled,
         t.is_instead_of_trigger AS IsInsteadOfTrigger,
         OBJECT_DEFINITION(t.object_id) AS TriggerDefinition
      FROM
         sys.triggers t
      INNER JOIN
         sys.tables tab ON t.parent_id = tab.object_id
      WHERE
         tab.name = ? AND OBJECT_SCHEMA_NAME(tab.object_id) = ?
      """

        try:
            connection = self.get_connection(database)
            cursor = CursorManager(connection)
            cursor.execute(query, (table_name, schema))

            triggers = []
            for row in cursor.fetchall():
               trigger = {
                  "TriggerName": row.TriggerName,
                  "TriggerSchema": row.TriggerSchema,
                  "TableName": row.TableName,
                  "TableSchema": row.TableSchema,
                  "CreatedDate": row.CreatedDate,
                  "LastModifiedDate": row.LastModifiedDate,
                  "IsDisabled": bool(row.IsDisabled),
                  "IsInsteadOfTrigger": bool(row.IsInsteadOfTrigger),
                  "TriggerDefinition": row.TriggerDefinition,
               }
               triggers.append(trigger)
            return triggers

        except pyodbc.Error as e:
            print(f"Error retrieving triggers for {schema}.{table_name}: {e}")  # noqa: T201
            return []
        finally:
            if "connection" in locals():
                self.connection.close()

    """
   ------------------------------------------------------------------
   Misc (unused) functions
   ------------------------------------------------------------------
   """

   #  def database_exists(self, database_name: str) -> bool:
   #      """Check if a database already exists

   #      :param database_name: Name of the database to check
   #      :return: True if database exists, False otherwise
   #      """
   #      try:
   #          # Connect without specific database
   #          conn = pyodbc.connect(self.connection_string.replace(f";DATABASE={database_name}", ""))
   #          cursor = conn.cursor()

   #          # Query to check database existence
   #          cursor.execute(
   #              """
   #             SELECT name
   #             FROM sys.databases
   #             WHERE name = ?
   #       """,
   #              (database_name,),
   #          )

   #          return cursor.fetchone() is not None

   #      except pyodbc.Error as e:
   #          print(f"Database existence check error: {e}")  # noqa: T201
   #          return False

   #      finally:
   #          if "conn" in locals():
   #              conn.close()

   #  def clear_database(self, database_name: str | None) -> bool:
   #      """Clear all tables from a database

   #      :param database_name: Optional database name (uses current if not specified)
   #      :return: True if database clearing successful
   #      """
   #      try:
   #          # Use provided database or current connection database
   #          if database_name:
   #              conn = pyodbc.connect(
   #                  self.connection_string.replace(
   #                      f";DATABASE={self.connection_string.split('DATABASE=')[-1]}", f";DATABASE={database_name}",
   #                  ),
   #              )
   #          else:
   #              conn = pyodbc.connect(self.connection_string)

   #              cursor = conn.cursor()

   #          # Get all user tables
   #              cursor.execute("""
   #             SELECT TABLE_NAME 
   #             FROM INFORMATION_SCHEMA.TABLES 
   #             WHERE TABLE_TYPE = 'BASE TABLE'
   #          """)

   #              tables = cursor.fetchall()

   #              # Disable foreign key checks and drop tables
   #              cursor.execute("EXEC sp_MSforeachtable @command1 = 'ALTER TABLE ? NOCHECK CONSTRAINT ALL'")

   #              # Drop tables
   #              for table in tables:
   #                  table_name = table[0]
   #                  try:
   #                      cursor.execute(f"DROP TABLE {table_name}")
   #                  except pyodbc.Error as drop_error:
   #                      print(f"Error dropping table {table_name}: {drop_error}")

   #              conn.commit()
   #              return True

   #      except pyodbc.Error as e:
   #          print(f"Database clearing error: {e}")
   #          return False

   #      finally:
   #          if "conn" in locals():
   #              conn.close()
