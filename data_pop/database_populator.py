"""DatabasePopulator: A Utility Class for Automated Database Population with Fake Data

This class provides a robust mechanism for generating and inserting fake data into database tables
across multiple databases, schemas, and tables. It integrates with a database connection utility
to retrieve table structures and execute insert queries with comprehensive error handling.

Key Features:
      - Retrieve databases, schemas, and tables dynamically
      - Generate fake data for entire tables or specific rows
      - Supports various data types with intelligent type conversion
      - Comprehensive logging and error handling
      - Flexible data generation with configurable nullability and length constraints

   Dependencies:
      - typing: For type hinting
      - datetime: For date/time manipulations
      - fake_data_generator: For generating fake property values
      - database_connection: For database interaction
      - logging: For detailed logging and debugging

Methods:
      __init__(db_connection: DatabaseConnection):
         Initialize the populator with a specific database connection.

      get_databases() -> list[str]:
         Retrieve all available databases from the connection.

      get_schemas(database_name: str) -> list[str]:
         Retrieve all schemas for a specific database.

      get_tables(schema: str, database_name: str) -> list[str]:
         Retrieve all tables within a specific schema and database.

      populate_table(num_rows: int, database_name: str, schema: str, table: str) -> list[list]:
         Populate an entire table with fake data rows.
         - Generates specified number of rows
         - Retrieves table structure dynamically
         - Executes bulk insert query
         - Returns generated rows for verification

      populate_row(database_name: str, schema: str, table: str, row_name: str) -> list:
         Generate and insert a single row of fake data for a specific table.
         - Retrieves row structure dynamically
         - Generates single row data
         - Executes single row insert query

      _generate_row(cols: list[dict], col_headers: list[str], database_name: str, schema_name: str, table_name: str) -> list:
         Internal method to generate a single row of fake data.
         - Processes column properties
         - Generates fake values based on column constraints
         - Logs detailed column information

      _log_column_info(database_name: str, schema_name: str, table_name: str, col_property: dict):
         Debugging method to log detailed information about each column.
         - Logs database, schema, table, and column details
         - Attempts to retrieve table triggers

      create_query(database: str, schema: str, table_name: str, col_headers: list[str], values: list[list]) -> str:
         Create a SQL INSERT query with advanced error handling.
         - Supports complex type conversions
         - Handles special cases like binary data and datetime
         - Implements SQL Server TRY-CATCH error handling
         - Escapes and formats values safely

      create_query_for_row(database: str, schema: str, table_name: str, col_header: str, values: list) -> str:
         Create a SQL INSERT query for a single row with similar error handling to create_query.

Logging:
      - Uses Python's logging module to provide informative debug messages
      - Configures log level to INFO with timestamp and severity

Error Handling:
      - Comprehensive SQL Server TRY-CATCH blocks in query generation
      - Detailed error message printing
      - Safe value formatting and conversion

Example Usage:
      db_conn = DatabaseConnection(connection_params)
      populator = DatabasePopulator(db_conn)

      # Populate an entire table
      populator.populate_table(
         num_rows=100,
         database_name='MyDatabase',
         schema='dbo',
         table='Users'
      )

      # Populate a single row
      populator.populate_row(
         database_name='MyDatabase',
         schema='dbo',
         table='Users',
         row_name='UserDetail'
      )
"""

import logging
from datetime import datetime

from .database_connection import DatabaseConnection
from .fake_data_generator import generate_fake_property

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class DatabasePopulator:
   def __init__(self, db_connection: DatabaseConnection) -> None:
      """Initialize the DatabasePopulator with a database connection.

      :param db_connection: DatabaseConnection instance
      """
      self.db = db_connection

   def get_databases(self) -> list[str]:
      """Retrieve all databases from the connection.

      :return: list of database names
      """
      return self.db.get_all_databases(None)

   def get_schemas(self, database_name: str) -> list[str]:
      """Retrieve schemas for a specific database.

      :param database_name: Name of the database
      :return: list of schema names
      """
      return self.db.get_schemas_by_database(database_name)

   def get_tables(self, schema: str, database_name: str) -> list[str]:
      """Retrieve tables for a specific schema and database.

      :param schema: Schema name
      :param database_name: Database name
      :return: list of table names
      """
      return self.db.get_tables_by_schema(schema, database_name)

   def populate_table(self, num_rows: int, database_name: str, schema: str, table: str) -> list[list]:
      """Populate a table with fake data.

      :param num_rows: Number of rows to generate
      :param database_name: Name of the database
      :param schema: Schema name
      :param table: Table name
      :return: Generated rows of data
      """
      # Get table structure
      cols = self.db.get_table_data_structure(table, schema, database_name)

      rows = []
      col_headers = []

      for _ in range(num_rows):
         row = self._generate_row(cols, col_headers, database_name, schema, table)
         rows.append(row)

      # Create and execute insert query
      query = self.create_query(database_name, schema, table, col_headers, rows)
      self.db.execute_query(query, None)

      return rows

   def populate_row(self, database_name: str, schema: str, table: str, row_name: str) -> list:
      """Generate a single row of fake data for a specified table.

      :param database_name: Name of the database
      :param schema: Schema name
      :param table: Table name
      :return: A single row of generated data
      """
      # Get table structure
      cols = self.db.get_row_data_structure(table, schema, database_name, row_name)

      # Placeholder for column headers (used internally)
      col_headers = []

      # Generate a single row of data
      row = self._generate_row(cols, col_headers, database_name, schema, table)
      query = self.create_query_for_row(database_name, schema, table, row_name, row)
      self.db.execute_query(query)

      return row

   def _generate_row(self, cols: list[dict], col_headers: list[str], database_name: str, schema_name: str, table_name: str) -> list:
      """Generate a single row of fake data.

      :param cols: Column properties
      :param col_headers: list of column headers
      :return: A row of generated data
      """
      row = []
      for col_property in cols:
         # Extract column properties
         col_property_name = col_property["name"]
         col_property_type = col_property["property_type"]
         col_property_max_length = col_property.get("max_length", 7)
         col_property_nullable = col_property["nullable"]
         if col_property_max_length is None:
            col_property_max_length = 7

         # Logging/debugging information
         self._log_column_info(database_name, schema_name, table_name, col_property)

         # Generate fake property
         fake_property = generate_fake_property(
            col_property_type,
            col_property_nullable,
            col_property_max_length,
         )

         # Manage column headers
         if col_property_name not in col_headers:
            col_headers.append(col_property_name)

         row.append(fake_property)

      return row

   def _log_column_info(self, database_name: str, schema_name: str, table_name: str, col_property: dict) -> None:
      """Log column information for debugging.

      :param col_property: Column property dictionary
      """
      print("---------------------------------")  # noqa: T201
      col_property_max_length = col_property.get("max_length", 10)
      if col_property_max_length is None:
         col_property_max_length = 10
      logger.info(f"DATABASE_NAME: {database_name}")  # noqa: G004
      logger.info(f"SCHEMA_TYPE: {schema_name}")  # noqa: G004
      logger.info(f"TABLE_NAME: {table_name}")  # noqa: G004
      logger.info(f"COL_NAME: {col_property['name']}")  # noqa: G004
      logger.info(f"COL_TYPE: {col_property['property_type']}")  # noqa: G004
      logger.info(f"COL_MAX_LENGTH: {col_property_max_length}")  # noqa: G004

      # Optional: Log triggers if needed
      try:
         triggers = self.db.get_triggers(
               col_property.get("database_name", ""),
               col_property.get("schema", ""),
               col_property.get("table", ""),
         )
         if len(triggers) > 0:
            print("triggers:", triggers)  # noqa: T201
      except Exception as e:  # noqa: BLE001
         print(f"Error retrieving triggers: {e}")  # noqa: T201

   def create_query(self, database: str, schema: str, table_name: str, col_headers: list[str], values: list[str]) -> str:  # noqa: C901
      """Create an SQL INSERT query with optimized string formatting and error handling.

      :param database: Database name
      :param schema: Schema name
      :param table_name: Name of the table
      :param col_headers: list of column names
      :param values: list of value rows to be inserted
      :return: Completed SQL INSERT query string with error handling
      """
      def format_value(raw_value: str | bytes , col_name: str) -> str:  # noqa: C901, PLR0911, PLR0912
         # Handle different types of values with explicit conversions
         if raw_value is None or raw_value == "NULL":
            return "NULL"
         if col_name == "ATTACHMENT_BODY":
            # For binary data, use explicit hex conversion
            if raw_value is None:
                  return "NULL"
            if isinstance(raw_value, str):
                  # Remove b'' prefix if present and clean up
                  if raw_value.startswith("b'") and raw_value.endswith("'"):
                     raw_value = raw_value[2:-1]
                  # Convert to hex
                  try:
                     hex_val = raw_value.encode("latin1").hex()
                     return f"CONVERT(varbinary(max), 0x{hex_val})"  # noqa: TRY300
                  except Exception:  # noqa: BLE001
                     return f"CONVERT(varbinary(max), '{raw_value}')"
            elif isinstance(raw_value, bytes):
                  # Direct hex conversion for bytes
                  hex_val = raw_value.hex()
                  return f"CONVERT(varbinary(max), 0x{hex_val})"
            else:
                  return f"CONVERT(varbinary(max), '{raw_value!s}')"
         elif col_name in ["CREATED_DATE", "LAST_UPDATED_DATE"]:
            # Handle date formatting explicitly
            if isinstance(raw_value, str):
                  try:
                     # Try parsing the string to ensure it's a valid datetime
                     parsed_date = datetime.strptime(raw_value, "%Y-%m-%d %H:%M:%S.%f")  # noqa: DTZ007
                     return f"'{parsed_date.strftime('%Y-%m-%d %H:%M:%S.%f')}'"
                  except ValueError:
                     # If parsing fails, return NULL or raise an error
                     return "NULL"
            elif isinstance(raw_value, datetime):
                  # If it's already a datetime object, format it
                  return f"'{raw_value.strftime('%Y-%m-%d %H:%M:%S.%f')}'"
            else:
                  # Fallback for unexpected types
                  return "NULL"
         elif isinstance(raw_value, str):
            # Remove extra quotes if present
            clean_val = raw_value.strip("'")
            return f"'{clean_val}'"
         else:
            return str(raw_value)

      # Format column headers
      col_headers_str = "(" + ", ".join([f"[{col}]" for col in col_headers]) + ")"

      # Generate rows with safe value formatting
      values_rows = []
      for row in values:
         formatted_row = "(" + ", ".join(
            format_value(val, col_headers[idx])
            for idx, val in enumerate(row)
         ) + ")"
         values_rows.append(formatted_row)

      # Combine all parts of the query
      values_str = ",\n".join(values_rows)

      # Create final query with BEGIN TRY-CATCH block
      return f"""
         BEGIN TRY
            INSERT INTO {database}.{schema}.{table_name} {col_headers_str}
            VALUES
            {values_str};
         END TRY
         BEGIN CATCH
            DECLARE @ErrorMessage NVARCHAR(4000) = ERROR_MESSAGE();
            DECLARE @ErrorSeverity INT = ERROR_SEVERITY();
            DECLARE @ErrorState INT = ERROR_STATE();

            PRINT 'Error occurred while inserting into {database}.{schema}.{table_name}';
            PRINT 'Error Message: ' + @ErrorMessage;

            RAISERROR(
               @ErrorMessage,
               @ErrorSeverity,
               @ErrorState
            );
         END CATCH;
      """

   def create_query_for_row(self, database: str, schema: str, table_name: str, col_header: str, values: list) -> str:  # noqa: C901
      """Create an SQL INSERT query for a single row with optimized string formatting and error handling.

      :param database: Database name
      :param schema: Schema name
      :param table_name: Name of the table
      :param col_headers: list of column names
      :param values: list of values for a single row to be inserted
      :return: Completed SQL INSERT query string with error handling
      """

      def format_value(raw_value: str | bytes, col_name: str) -> str:  # noqa: PLR0911, PLR0912
         # Handle different types of values with explicit conversions
         if raw_value is None or raw_value == "NULL":
            return "NULL"
         if col_name == "ATTACHMENT_BODY":
            # For binary data, use explicit hex conversion
            if isinstance(raw_value, str):
                  # Remove b'' prefix if present and clean up
                  if raw_value.startswith("b'") and raw_value.endswith("'"):
                     raw_value = raw_value[2:-1]
                  # Convert to hex
                  try:
                     hex_val = raw_value.encode("latin1").hex()
                     return f"CONVERT(varbinary(max), 0x{hex_val})"  # noqa: TRY300
                  except Exception:  # noqa: BLE001
                     return f"CONVERT(varbinary(max), '{raw_value}')"
            elif isinstance(raw_value, bytes):
                  # Direct hex conversion for bytes
                  hex_val = raw_value.hex()
                  return f"CONVERT(varbinary(max), 0x{hex_val})"
            else:
                  return "NULL"
         elif col_name in ["CREATED_DATE", "LAST_UPDATED_DATE"]:
            # Handle date formatting explicitly
            if isinstance(raw_value, str):
                  try:
                     parsed_date = datetime.strptime(raw_value, "%Y-%m-%d %H:%M:%S.%f")  # noqa: DTZ007
                     return f"'{parsed_date.strftime('%Y-%m-%d %H:%M:%S.%f')}'"
                  except ValueError:
                     return "NULL"
            elif isinstance(raw_value, datetime):
                  return f"'{raw_value.strftime('%Y-%m-%d %H:%M:%S.%f')}'"
            else:
                  return "NULL"
         elif isinstance(raw_value, str):
            clean_val = raw_value.replace("'", "''")
            return f"'{clean_val}'"
         else:
            return str(raw_value)

      # Format column headers
      col_headers_str = "(["+ col_header + "])"

      # Format values for a single row
      formatted_values = "(" + ", ".join(
         format_value(raw_value, col_header) for idx, raw_value in enumerate(values)
      ) + ")"

      # Create final query with BEGIN TRY-CATCH block
      return f"""
         USE [{database}];
         BEGIN TRY
            INSERT INTO {database}.{schema}.{table_name} {col_headers_str}
            VALUES
            {formatted_values};
         END TRY
         BEGIN CATCH
            DECLARE @ErrorMessage NVARCHAR(4000) = ERROR_MESSAGE();
            DECLARE @ErrorSeverity INT = ERROR_SEVERITY();
            DECLARE @ErrorState INT = ERROR_STATE();

            'Error occurred while inserting into {database}.{schema}.{table_name}';
            'Error Message: ' + @ErrorMessage;

            RAISERROR(
                  @ErrorMessage,
                  @ErrorSeverity,
                  @ErrorState
            );
         END CATCH;
      """
