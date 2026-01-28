-- Migration: 005_node_boundary_cleanup.sql
-- Purpose: Align NodeBoundaryORM with DDD domain model (2026-01-15 changes)
-- Reference: ARCHITECTURE_REVIEW_2026_01_28.md - ISSUE-CP-001
-- 
-- Domain Model Changes (2026-01-15):
-- - Removed: internal_session_id (AgentGit-specific)
-- - Removed: tool_count (LangGraph doesn't track tools)
-- - Removed: checkpoint_count (redundant)
-- - entry_checkpoint_id: Now Optional[str] (LangGraph UUID format)
-- - exit_checkpoint_id: Now Optional[str] (LangGraph UUID format)

-- Safety: Make internal_session_id nullable first before eventual removal
-- This allows gradual migration without breaking existing code
ALTER TABLE wtb_node_boundaries 
    ALTER COLUMN internal_session_id DROP NOT NULL;

-- For SQLite (which doesn't support DROP NOT NULL directly), use:
-- CREATE TABLE wtb_node_boundaries_new AS SELECT * FROM wtb_node_boundaries;
-- DROP TABLE wtb_node_boundaries;
-- ALTER TABLE wtb_node_boundaries_new RENAME TO wtb_node_boundaries;

-- Note: Actual column removal should be done in a separate migration
-- after all code references are removed and verified
-- 
-- Future migration (006_node_boundary_remove_deprecated.sql):
-- ALTER TABLE wtb_node_boundaries DROP COLUMN internal_session_id;
-- ALTER TABLE wtb_node_boundaries DROP COLUMN tool_count;
-- ALTER TABLE wtb_node_boundaries DROP COLUMN checkpoint_count;

-- Verification query
-- SELECT 
--     column_name, 
--     is_nullable, 
--     data_type 
-- FROM information_schema.columns 
-- WHERE table_name = 'wtb_node_boundaries';
