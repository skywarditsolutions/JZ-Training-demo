import random

from faker import Faker

fake = Faker()

"""Fake Data Generation Utility

This module provides functions for generating fake data with configurable properties,
useful for creating test databases or populating sample data.
"""

def gen_is_null(nullable: bool) -> bool:
   """Determines whether a property should be set to NULL based on nullable flag.

   Args:
      nullable (bool): Flag indicating if the property can be NULL.

   Returns:
      bool: Randomly returns True/False if nullable is True,
            otherwise always returns False.
   """
   if nullable:
      return random.choice([True, False])  # noqa: S311
   return False

def fake_generate_fake_property() -> str:
   """Generates a random string property using Faker library.
   Mainly used for debugging, quick testing.

   Returns:
         str: A random string of 1-5 characters.
   """
   return fake.pystr(min_chars=1, max_chars=5)

def generate_fake_property(property_type: str, nullable: bool, max_length: int | None) -> str | int:  # noqa: PLR0911
      """Generates a fake property value based on specified type, nullability, and length constraints.

      Args:
         property_type (str): The database column type to generate 
               (supported types: varchar, nvarchar, char, text, varbinary, 
               bit, int, float, datetime, date, bool).
         nullable (bool): Whether the property can be NULL.
         max_length (int, optional): Maximum length for string/binary types. 
               Defaults to None (which sets a default of 25).

      Returns:
         str: A generated fake value as a string, formatted for SQL insertion.
               Returns 'NULL' if the property is determined to be NULL.

      Raises:
         ValueError: If an unsupported property type is provided.

      Notes:
         - For string types, truncates to max_length
         - For datetime, prints generated datetime for debugging
         - Boolean returns as 'TRUE' or 'FALSE'
         - Varbinary converts to hexadecimal representation
      """
      is_null = gen_is_null(nullable)

      # Handle NULL case
      if is_null:
         return "NULL"

      # Handle default max_length for -1 or None
      if max_length in [None, -1]:
         max_length = 25  # Default for VARCHAR(MAX) or NVARCHAR(MAX)

      if property_type in ["varchar", "nvarchar", "char", "text"]:
         max_length = max_length or 25
         generated_string = fake.pystr(min_chars=1, max_chars=max_length)
         return f"'{generated_string[:max_length]}'"  # Ensure truncation to column size
      if property_type in ["varbinary"]:
         result_bytes = min(random.randint(1, 10), max_length or 10)  # noqa: S311
         return "0x" + fake.binary(result_bytes).hex()  # Convert binary to hex
      if property_type == "bit":
         return random.choice([0, 1])  # noqa: S311
      if property_type == "int":
         return str(fake.pyint())
      if property_type == "float":
         return str(fake.pyfloat())
      if property_type == "datetime":
         dt = fake.date_time()
         formatted_dt = dt.strftime("%Y-%m-%d %H:%M:%S")
         print(f"Generated datetime: {formatted_dt}")  # Debug print  # noqa: T201
         return f"'{formatted_dt}'"
      if property_type == "date":
         return f"'{fake.date()}'"
      if property_type == "bool":
         return str(fake.pybool()).upper()  # Return TRUE/FALSE
      msg = f"Unsupported type: {property_type}"
      raise ValueError(msg)
