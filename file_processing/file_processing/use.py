import psycopg2

from FileTracker import Commit, FileMemento
from FileTracker.ORM import BlobORM
from FileTracker.Repository import BlobRepository
from FileTracker.Repository import CommitRepository
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="filetracker",
    user="wangsiyuan",
    password=""
)

storage_path = "/Users/wangsiyuan/Desktop/Temp"

blob_orm = BlobORM(conn, storage_path)
blob_repo = BlobRepository(conn, storage_path)

# commit = Commit(message="Initial commit")

# memento1 = FileMemento("data.csv", blob_orm)
# memento2 = FileMemento("config.json", blob_orm)


# commit.add_memento(memento1)
# commit.add_memento(memento2)


commit_repo = CommitRepository(conn)
# commit_repo.save(commit)

# print(commit.commit_id)

old_commit = commit_repo.find_by_id("9b256f6e-9af2-4537-bc42-97bd0140361e")

for memento in old_commit.mementos:
    blob_repo.restore(memento.file_hash, memento.file_path)
