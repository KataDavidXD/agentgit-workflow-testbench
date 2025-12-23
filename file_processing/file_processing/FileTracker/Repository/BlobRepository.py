from FileTracker.ORM import BlobORM

class BlobRepository:
    def __init__(self, db_connection, storage_path):
        self.orm = BlobORM(db_connection, storage_path)

    def save(self, file_path):
        with open(file_path, 'rb') as f:
            content = f.read()
        return self.orm.save(content)

    def restore(self, content_hash,output_path):
        content = self.orm.get(content_hash)
        if content is None:
            raise ValueError(f"Blob not found: {content_hash}")

        with open(output_path, 'wb') as f:
            f.write(content)
        
    def get_content(self, content_hash):
        return self.orm.get(content_hash)

    def exists(self, content_hash): #检查一下是不是已经有这个文档备份了
        return self.orm.exists(content_hash)
    
    def stats(self):
        return self.orm.stats()