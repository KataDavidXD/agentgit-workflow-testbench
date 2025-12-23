import hashlib
import os
class BlobORM:
    def __init__(self, db_connection, storage_path):
        if not os.path.isdir(storage_path):
            raise ValueError("Storage path is not a directory")
        self.db_connection = db_connection
        self.storage_path = storage_path
        self.objects_path = os.path.join(storage_path, "objects")

        os.makedirs(self.objects_path, exist_ok=True) #如果目录不存在，则创建目录
        

    def save(self, blob):
        
        content_hash = hashlib.sha256(blob).hexdigest()

        #检查一下是不是已经有这个文档备份了
        if self.exists(content_hash):
            return content_hash
        
        storage_location = self._write(content_hash, blob)

        cursor = self.db_connection.cursor()
        cursor.execute(
            "INSERT INTO file_blobs (content_hash, storage_location, size, created_at) VALUES (%s, %s, %s, NOW())",
            (content_hash, storage_location, len(blob))
        )
        self.db_connection.commit()
        cursor.close()

        return content_hash
    
    def get(self, content_hash):

        cursor = self.db_connection.cursor()
        cursor.execute(
            "SELECT storage_location FROM file_blobs WHERE content_hash = %s",
            (content_hash,)
        )
        row = cursor.fetchone()
        cursor.close()

        if not row:
            return None

        storage_location = row[0]
        return self._read(storage_location)

    def exists(self, content_hash):
        cursor = self.db_connection.cursor()
        cursor.execute(
            "SELECT 1 FROM file_blobs WHERE content_hash = %s",
            (content_hash,)
        )
        exists = cursor.fetchone() is not None
        cursor.close()
        return exists

    def delete(self, content_hash):
        #从数据库和本地系统中删除blob
        cursor = self.db_connection.cursor()
        cursor.execute(
            "SELECT storage_location FROM file_blobs WHERE content_hash = %s",
            (content_hash,)
        )
        row = cursor.fetchone()

        if row:
            storage_location = row[0]    
            # Delete from file system
            if os.path.exists(storage_location):
                os.remove(storage_location)

            # Delete from database
            cursor.execute(
                "DELETE FROM file_blobs WHERE content_hash = %s",
                (content_hash,)
            )
            self.db_connection.commit()

        cursor.close()

    def _write(self, content_hash, blob):
        dir_name = content_hash[:2]
        file_name = content_hash[2:]
        dir_path = os.path.join(self.objects_path, dir_name)
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, file_name)
        with open(file_path, "wb") as f:
            f.write(blob)
        return file_path

    def _read(self, storage_location):
        if not os.path.exists(storage_location):
            raise FileNotFoundError(f"Blob file not found in: {storage_location}")
        with open(storage_location, "rb") as f:
            return f.read()
    
    def stats(self):
        cursor = self.db_connection.cursor()
        cursor.execute(
            "SELECT COUNT(*), SUM(size) FROM file_blobs"
        )
        row = cursor.fetchone()
        cursor.close()

        count = row[0] or 0
        total_size = row[1] or 0

        return {
            'blob_count': count,
            'total_size_bytes': total_size,
            'total_size_mb': total_size / (1024 * 1024)
        }

