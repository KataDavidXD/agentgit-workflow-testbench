import hashlib
import os

class FileMemento:
    def __init__(self, file_path, blob_orm = None):
        self._file_path = file_path
        self._file_size = os.path.getsize(self._file_path)
        
        with open(file_path, 'rb') as f:
            content = f.read()
            self._file_hash = hashlib.sha256(content).hexdigest()

        if blob_orm:
            blob_orm.save(content)

    @property
    def file_path(self):
        return self._file_path
    
    @property
    def file_hash(self):
        return self._file_hash

    @property
    def file_size(self):
        return self._file_size

    