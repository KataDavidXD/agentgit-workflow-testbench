from FileTracker.ORM import FileMementoORM
from FileTracker import FileMemento
class FileMementoRepository:
    def __init__(self, db_connection):
        self.orm = FileMementoORM(db_connection)
        

    def get_all(self):
        rows = self.orm.get_all()
        return [self._row_to_memento(row) for row in rows]
        
    
    def save(self, memento, commit_id):
        self.orm.save(memento, commit_id)
    
    def find_by_commit_id(self, commit_id):
        rows = self.orm.find_by_commit_id(commit_id)
        return [self._row_to_memento(row) for row in rows]

    def delete_by_commit_id(self, commit_id):
        self.orm.delete(commit_id)  

    def _row_to_memento(self, row):
        memento = object.__new__(FileMemento)
        memento._file_path = row[0]
        memento._file_hash = row[1]
        memento._file_size = row[2]
        return memento
    
    

    
    
