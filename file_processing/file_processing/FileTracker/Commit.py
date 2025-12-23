import uuid
from datetime import datetime
class Commit:
    def __init__(self, message=None, commit_id=None):
        self._message = message
        self._commit_id = commit_id or str(uuid.uuid4())
        self._timestamp = datetime.now()
        self._mementos = []

    @property
    def commit_id(self):
        return self._commit_id
    
    @property
    def timestamp(self):
        return self._timestamp
    
    @property
    def message(self):
        return self._message
    
    @property
    def mementos(self):
        return self._mementos.copy()
    
    def add_memento(self, memento):
        self._mementos.append(memento)

    def get_files(self):
        return [m.file_path for m in self._mementos]