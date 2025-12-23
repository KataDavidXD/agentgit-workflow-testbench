# FileTracker - File Version Control System

A Git-like file version control system built with Python, implementing the **Memento Design Pattern** for file state snapshots and **Repository Pattern** for data access abstraction.

---

## 📁 Project Structure

```
file_processing/
├── FileTracker/                    # Core package
│   ├── __init__.py                 # Exports: Commit, FileMemento
│   ├── Commit.py                   # Commit entity class
│   ├── FileMemento.py              # File snapshot class (Memento pattern)
│   │
│   ├── ORM/                        # Database access layer
│   │   ├── __init__.py             # Exports: CommitORM, FileMementoORM, BlobORM
│   │   ├── BlobORM.py              # Binary content storage operations
│   │   ├── CommitORM.py            # Commit table operations
│   │   └── FileMementoORM.py       # File memento table operations
│   │
│   └── Repository/                 # Business logic layer (Repository pattern)
│       ├── __init__.py             # Exports: CommitRepository, FileMementoRepository, BlobRepository
│       ├── BlobRepository.py       # High-level blob operations
│       ├── CommitRepository.py     # High-level commit operations
│       └── FileMementoRepository.py # High-level memento operations
│
├── sql/
│   └── schema.sql                  # Database schema definitions
│
├── config.json                     # Application configuration
├── data.csv                        # Sample data file
└── use.py                          # Usage example script
```

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Application Layer                         │
│                          (use.py)                                │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                      Repository Layer                            │
│  ┌─────────────────┐ ┌──────────────────┐ ┌─────────────────┐   │
│  │ CommitRepository│ │FileMementoRepository│ │ BlobRepository │   │
│  └────────┬────────┘ └─────────┬────────┘ └────────┬────────┘   │
└───────────┼────────────────────┼───────────────────┼────────────┘
            │                    │                   │
┌───────────▼────────────────────▼───────────────────▼────────────┐
│                          ORM Layer                               │
│  ┌─────────────────┐ ┌──────────────────┐ ┌─────────────────┐   │
│  │   CommitORM     │ │  FileMementoORM  │ │    BlobORM      │   │
│  └────────┬────────┘ └─────────┬────────┘ └────────┬────────┘   │
└───────────┼────────────────────┼───────────────────┼────────────┘
            │                    │                   │
┌───────────▼────────────────────▼───────────────────▼────────────┐
│                       PostgreSQL Database                        │
│  ┌─────────────────┐ ┌──────────────────┐ ┌─────────────────┐   │
│  │    commits      │ │  file_mementos   │ │   file_blobs    │   │
│  └─────────────────┘ └──────────────────┘ └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                                    │
                                    ┌───────────────▼───────────────┐
                                    │    File System (objects/)     │
                                    │    Content-addressable store  │
                                    └───────────────────────────────┘
```

---

## 📦 Core Classes

### 1. `Commit` (FileTracker/Commit.py)

Represents a version commit containing file snapshots.

| Property/Method | Type | Description |
|-----------------|------|-------------|
| `commit_id` | `str` | Unique UUID identifier |
| `timestamp` | `datetime` | Creation timestamp |
| `message` | `str` | Commit message |
| `mementos` | `list[FileMemento]` | Associated file snapshots |
| `add_memento(memento)` | `method` | Add a file snapshot to commit |
| `get_files()` | `method` | Returns list of tracked file paths |

---

### 2. `FileMemento` (FileTracker/FileMemento.py)

Captures a file's state at a point in time (Memento Design Pattern).

| Property | Type | Description |
|----------|------|-------------|
| `file_path` | `str` | Original file path |
| `file_hash` | `str` | SHA-256 hash of file content |
| `file_size` | `int` | File size in bytes |

**Constructor**: `FileMemento(file_path, blob_orm=None)`
- Reads file content and computes SHA-256 hash
- Optionally saves content to blob storage via `blob_orm`

---

## 🗄️ ORM Layer

### 3. `BlobORM` (FileTracker/ORM/BlobORM.py)

Manages binary file content storage using content-addressable storage (like Git).

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `save(blob)` | `blob: bytes` | `str` (content_hash) | Save binary content, returns hash |
| `get(content_hash)` | `content_hash: str` | `bytes` | Retrieve content by hash |
| `exists(content_hash)` | `content_hash: str` | `bool` | Check if content exists |
| `delete(content_hash)` | `content_hash: str` | `None` | Delete content from DB and filesystem |
| `stats()` | - | `dict` | Get storage statistics |

**Storage Strategy**: Files stored at `objects/{hash[:2]}/{hash[2:]}` (similar to Git)

---

### 4. `CommitORM` (FileTracker/ORM/CommitORM.py)

Direct database operations for commits table.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `save(commit_id, timestamp, message)` | - | `None` | Insert new commit |
| `find_by_id(commit_id)` | `commit_id: str` | `tuple\|None` | Find commit by ID |
| `get_all()` | - | `list[tuple]` | Get all commits (DESC by timestamp) |
| `delete(commit_id)` | `commit_id: str` | `None` | Delete commit |

---

### 5. `FileMementoORM` (FileTracker/ORM/FileMementoORM.py)

Direct database operations for file_mementos table.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `save(memento, commit_id)` | - | `None` | Insert memento record |
| `find_by_commit_id(commit_id)` | `commit_id: str` | `list[tuple]` | Find mementos by commit |
| `get_all()` | - | `list[tuple]` | Get all mementos |
| `delete(commit_id)` | `commit_id: str` | `None` | Delete mementos by commit ID |

---

## 🏛️ Repository Layer

### 6. `BlobRepository` (FileTracker/Repository/BlobRepository.py)

High-level blob operations with file I/O.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `save(file_path)` | `file_path: str` | `str` | Save file content, returns hash |
| `restore(content_hash, output_path)` | - | `None` | Restore file to output path |
| `get_content(content_hash)` | `content_hash: str` | `bytes` | Get raw content |
| `exists(content_hash)` | `content_hash: str` | `bool` | Check if blob exists |
| `stats()` | - | `dict` | Get storage statistics |

---

### 7. `CommitRepository` (FileTracker/Repository/CommitRepository.py)

High-level commit operations with memento handling.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `save(commit)` | `commit: Commit` | `None` | Save commit with all mementos |
| `find_by_id(commit_id)` | `commit_id: str` | `Commit\|None` | Find commit with mementos |
| `get_all()` | - | `list[Commit]` | Get all commits (without mementos) |
| `delete(commit_id)` | `commit_id: str` | `None` | Delete commit and mementos |

---

### 8. `FileMementoRepository` (FileTracker/Repository/FileMementoRepository.py)

High-level memento operations with object conversion.

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| `save(memento, commit_id)` | - | `None` | Save memento record |
| `find_by_commit_id(commit_id)` | `commit_id: str` | `list[FileMemento]` | Find mementos as objects |
| `get_all()` | - | `list[FileMemento]` | Get all mementos as objects |
| `delete_by_commit_id(commit_id)` | `commit_id: str` | `None` | Delete mementos by commit |

---

## 🗃️ Database Schema

```sql
-- Commits table
CREATE TABLE commits (
    commit_id VARCHAR(64) PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    message TEXT
);

-- File blobs (content-addressable storage metadata)
CREATE TABLE file_blobs (
    content_hash VARCHAR(64) PRIMARY KEY,
    storage_location VARCHAR(512) NOT NULL,
    size INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- File mementos (file metadata per commit)
CREATE TABLE file_mementos (
    id SERIAL PRIMARY KEY,
    file_path VARCHAR(255) NOT NULL,
    file_hash VARCHAR(64) NOT NULL,
    file_size INTEGER NOT NULL,
    commit_id VARCHAR(64) NOT NULL REFERENCES commits(commit_id) ON DELETE CASCADE,
    UNIQUE(file_path, commit_id)
);
```

---

## 🚀 Usage Example

### Creating a Commit

```python
import psycopg2
from FileTracker import Commit, FileMemento
from FileTracker.ORM import BlobORM
from FileTracker.Repository import CommitRepository, BlobRepository

# Connect to database
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="filetracker",
    user="your_user",
    password="your_password"
)

storage_path = "/path/to/storage"
blob_orm = BlobORM(conn, storage_path)

# Create a new commit
commit = Commit(message="Initial commit")

# Create file mementos (snapshots)
memento1 = FileMemento("data.csv", blob_orm)
memento2 = FileMemento("config.json", blob_orm)

# Add mementos to commit
commit.add_memento(memento1)
commit.add_memento(memento2)

# Save commit to database
commit_repo = CommitRepository(conn)
commit_repo.save(commit)

print(f"Created commit: {commit.commit_id}")
```

### Restoring Files from a Commit

```python
# Find an existing commit
blob_repo = BlobRepository(conn, storage_path)
commit_repo = CommitRepository(conn)

old_commit = commit_repo.find_by_id("9b256f6e-9af2-4537-bc42-97bd0140361e")

# Restore all files from commit
for memento in old_commit.mementos:
    blob_repo.restore(memento.file_hash, memento.file_path)
    print(f"Restored: {memento.file_path}")
```

---

## ⚙️ Configuration

The `config.json` file contains application settings:

```json
{
  "application": {
    "name": "FileTracker",
    "version": "1.0.0",
    "debug": true
  },
  "database": {
    "host": "localhost",
    "port": 5432,
    "name": "filetracker_db",
    "user": "postgres",
    "pool_size": 10
  },
  "storage": {
    "blob_path": "/path/to/file_storage",
    "max_file_size_mb": 100,
    "compression_enabled": false
  },
  "logging": {
    "level": "INFO",
    "file": "logs/filetracker.log",
    "max_size_mb": 50
  }
}
```

---

## 🎯 Design Patterns Used

| Pattern | Implementation | Purpose |
|---------|----------------|---------|
| **Memento** | `FileMemento` class | Capture file state without exposing internals |
| **Repository** | `*Repository` classes | Abstract data access from business logic |
| **ORM** | `*ORM` classes | Map objects to database tables |
| **Content-Addressable Storage** | `BlobORM._write()` | Deduplicate file content using hash-based storage |

---

## 📋 Dependencies

- **Python 3.x**
- **psycopg2** - PostgreSQL adapter
- **PostgreSQL** - Database server

---

## 🔧 Setup

1. Create PostgreSQL database:
   ```sql
   CREATE DATABASE filetracker;
   ```

2. Run schema:
   ```bash
   psql -d filetracker -f sql/schema.sql
   ```

3. Configure `config.json` with your database credentials

4. Create storage directory for blob files

---

## 📄 License

This project is for educational/demonstration purposes.

