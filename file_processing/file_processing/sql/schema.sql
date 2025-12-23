-- Table for commits
  CREATE TABLE commits (
      commit_id VARCHAR(64) PRIMARY KEY,
      timestamp TIMESTAMP NOT NULL,
      message TEXT
  );

  -- Table for file blobs (actual content storage)
  CREATE TABLE file_blobs (
      content_hash VARCHAR(64) PRIMARY KEY,
      storage_location VARCHAR(512) NOT NULL,
      size INTEGER NOT NULL,
      created_at TIMESTAMP DEFAULT NOW()
  );

  -- Table for file mementos (file metadata in each commit)
  CREATE TABLE file_mementos (
      id SERIAL PRIMARY KEY,
      file_path VARCHAR(255) NOT NULL,
      file_hash VARCHAR(64) NOT NULL,
      file_size INTEGER NOT NULL,
      commit_id VARCHAR(64) NOT NULL REFERENCES commits(commit_id) ON DELETE CASCADE,
      UNIQUE(file_path, commit_id)
  );
