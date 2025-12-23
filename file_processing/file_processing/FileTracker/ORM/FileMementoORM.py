class FileMementoORM:
    def __init__(self, db_connection):
        self.db_connection = db_connection
        
    
    def delete(self, commit_id):
        cursor = self.db_connection.cursor()
        cursor.execute("DELETE FROM file_mementos WHERE commit_id = %s", (commit_id,))
        self.db_connection.commit()
        cursor.close()
        
    def get_all(self):
        cursor = self.db_connection.cursor()
        cursor.execute("SELECT * FROM file_mementos")
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def save(self, memento, commit_id):
        cursor = self.db_connection.cursor()
        cursor.execute(
          "INSERT INTO file_mementos (file_path, file_hash, file_size, commit_id) VALUES (%s, %s, %s, %s)",
          (memento.file_path, memento.file_hash, memento.file_size, commit_id)
        )
        self.db_connection.commit()
        cursor.close()
    
    def find_by_commit_id(self, commit_id):
        cursor = self.db_connection.cursor()
        cursor.execute(
          "SELECT file_path, file_hash, file_size FROM file_mementos WHERE commit_id = %s",
          (commit_id,)
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows