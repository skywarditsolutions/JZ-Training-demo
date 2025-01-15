class CursorManager:
      def __init__(self, connection):
         self._connection = connection
         self._cursor = None

      def __enter__(self):
         self._cursor = self._connection.cursor()
         return self._cursor

      def __exit__(self, exc_type, exc_val, exc_tb):
         if self._cursor:
               self._cursor.close()
         return False  # Propagate exceptions
