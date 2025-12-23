class CommitORM:
    def __init__(self, db_connection):
        self.db_connection = db_connection

    def save(self, commit_id, timestamp, message):
        cursor = self.db_connection.cursor()
        cursor.execute(
              "INSERT INTO commits (commit_id, timestamp, message) VALUES (%s, %s, %s)",
              (commit_id, timestamp, message)
          )
        self.db_connection.commit()
        cursor.close()
    
    def find_by_id(self, commit_id) :
        cursor = self.db_connection.cursor()
        cursor.execute(
              "SELECT commit_id, timestamp, message FROM commits WHERE commit_id = %s",
              (commit_id,)
        )
        row = cursor.fetchone()
        cursor.close()
        if row:
            return row
        return None
    
    def get_all(self):
        cursor = self.db_connection.cursor()
        cursor.execute("SELECT commit_id, timestamp, message FROM commits ORDER BY timestamp DESC")
        rows = cursor.fetchall()
        cursor.close()
        return rows
    
    def delete(self, commit_id):
        cursor = self.db_connection.cursor()
        cursor.execute("DELETE FROM commits WHERE commit_id = %s", (commit_id,))
        self.db_connection.commit()
        cursor.close()