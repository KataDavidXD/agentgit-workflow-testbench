-- Migration: Consolidate wtb_checkpoint_files to checkpoint_file_links
-- Date: 2026-01-27
-- Issue: CRITICAL-001 - Dual Checkpoint-File Storage
--
-- This migration:
-- 1. Creates checkpoint_file_links table if not exists
-- 2. Migrates data from wtb_checkpoint_files to checkpoint_file_links
-- 3. Drops the deprecated wtb_checkpoint_files table
--
-- IMPORTANT: Run this in a transaction. Backup database before running.

-- Step 1: Create checkpoint_file_links table if not exists
CREATE TABLE IF NOT EXISTS checkpoint_file_links (
    checkpoint_id INTEGER PRIMARY KEY,
    commit_id VARCHAR(64) NOT NULL,
    linked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    file_count INTEGER NOT NULL,
    total_size_bytes BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_checkpoint_file_links_commit_id 
    ON checkpoint_file_links(commit_id);

-- Step 2: Migrate data from wtb_checkpoint_files (if table exists)
-- Note: SQLite doesn't support IF EXISTS for INSERT, so we use INSERT OR IGNORE
INSERT OR IGNORE INTO checkpoint_file_links (
    checkpoint_id,
    commit_id,
    linked_at,
    file_count,
    total_size_bytes
)
SELECT 
    checkpoint_id,
    file_commit_id,
    created_at,
    file_count,
    total_size_bytes
FROM wtb_checkpoint_files
WHERE EXISTS (SELECT 1 FROM sqlite_master WHERE type='table' AND name='wtb_checkpoint_files');

-- Step 3: Drop deprecated table
DROP TABLE IF EXISTS wtb_checkpoint_files;

-- Verification query (run manually to verify migration)
-- SELECT COUNT(*) as link_count FROM checkpoint_file_links;
