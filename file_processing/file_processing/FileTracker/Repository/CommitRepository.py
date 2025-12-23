from FileTracker.ORM import CommitORM
from FileTracker import Commit
from .FileMementoRepository import FileMementoRepository
class CommitRepository:
    def __init__(self, db_connection):
        self.commit_orm = CommitORM(db_connection)
        self.memento_repo = FileMementoRepository(db_connection)

    def save(self, commit):
        self.commit_orm.save(commit.commit_id, commit.timestamp, commit.message)

        for memento in commit.mementos:
            self.memento_repo.save(memento, commit.commit_id)

    def find_by_id(self, commit_id):
        commit_row = self.commit_orm.find_by_id(commit_id)
        if not commit_row:
            return None
        
        mementos = self.memento_repo.find_by_commit_id(commit_id)

        return self._row_to_commit(commit_row,mementos)


    def get_all(self):
        commit_rows = self.commit_orm.get_all()
        return [self._row_to_commit(commit_row,[]) for commit_row in commit_rows] #没放memento,这里只是展示信息，不需要带上memento
    
    def delete(self, commit_id):
        self.memento_repo.delete_by_commit_id(commit_id)
        self.commit_orm.delete(commit_id)

    def _row_to_commit(self, commit_row,mementos):
        commit = object.__new__(Commit)
        commit._commit_id = commit_row[0]
        commit._timestamp = commit_row[1]
        commit._message = commit_row[2]
        
        commit._mementos = mementos
        return commit

    