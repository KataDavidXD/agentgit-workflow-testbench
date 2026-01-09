-- ═══════════════════════════════════════════════════════════════════════════════
-- WTB Migration 002: Batch Test Tables
-- 
-- Creates tables for batch test execution and results storage.
-- Supports both SQLite (development) and PostgreSQL (production).
-- ═══════════════════════════════════════════════════════════════════════════════

-- Note: wtb_batch_tests already exists in models.py ORM
-- This migration adds the results table and indexes for batch test queries

-- ═══════════════════════════════════════════════════════════════════════════════
-- Batch Test Results Table (separate from evaluation_results for clarity)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS wtb_batch_test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- References
    batch_test_id VARCHAR(64) NOT NULL,
    execution_id VARCHAR(64) NOT NULL,
    
    -- Variant identification
    combination_name VARCHAR(255) NOT NULL,
    variant_config TEXT NOT NULL,  -- JSON: node_id -> variant_id mapping
    
    -- Execution outcome
    success INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    
    -- Metrics (JSON)
    metrics TEXT,
    overall_score REAL DEFAULT 0.0,
    
    -- Timing
    started_at TEXT,
    completed_at TEXT,
    duration_ms INTEGER DEFAULT 0,
    
    -- Resource usage (optional)
    peak_memory_mb REAL,
    cpu_seconds REAL,
    
    -- Worker identification (for Ray)
    worker_id VARCHAR(255),
    worker_hostname VARCHAR(255),
    
    -- Timestamps
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    
    FOREIGN KEY (batch_test_id) REFERENCES wtb_batch_tests(id) ON DELETE CASCADE
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- Indexes for Batch Test Queries
-- ═══════════════════════════════════════════════════════════════════════════════

-- Primary query: Get results for a batch test
CREATE INDEX IF NOT EXISTS idx_batch_test_results_batch 
    ON wtb_batch_test_results(batch_test_id);

-- Query: Get results by execution
CREATE INDEX IF NOT EXISTS idx_batch_test_results_execution 
    ON wtb_batch_test_results(execution_id);

-- Query: Find best performing variants
CREATE INDEX IF NOT EXISTS idx_batch_test_results_score 
    ON wtb_batch_test_results(batch_test_id, overall_score DESC);

-- Query: Time-series analysis of batch tests
CREATE INDEX IF NOT EXISTS idx_batch_test_results_time 
    ON wtb_batch_test_results(created_at);

-- ═══════════════════════════════════════════════════════════════════════════════
-- Additional Indexes for wtb_batch_tests (if not already present)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_batch_tests_created 
    ON wtb_batch_tests(created_at);

CREATE INDEX IF NOT EXISTS idx_batch_tests_status_created 
    ON wtb_batch_tests(status, created_at);

-- ═══════════════════════════════════════════════════════════════════════════════
-- WAL Mode for SQLite (optional, run separately)
-- ═══════════════════════════════════════════════════════════════════════════════
-- To enable WAL mode for concurrent access:
-- PRAGMA journal_mode=WAL;
-- PRAGMA synchronous=NORMAL;
-- PRAGMA wal_autocheckpoint=1000;

