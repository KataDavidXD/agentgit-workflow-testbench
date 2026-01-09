-- ═══════════════════════════════════════════════════════════════════════════════
-- WTB Migration 003: PostgreSQL Production Setup
-- 
-- PostgreSQL-specific schema optimizations for production deployment.
-- Run this ONLY on PostgreSQL databases.
-- ═══════════════════════════════════════════════════════════════════════════════

-- ═══════════════════════════════════════════════════════════════════════════════
-- Batch Test Results Table (PostgreSQL version with JSONB)
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS wtb_batch_test_results (
    id SERIAL PRIMARY KEY,
    
    -- References
    batch_test_id VARCHAR(64) NOT NULL REFERENCES wtb_batch_tests(id) ON DELETE CASCADE,
    execution_id VARCHAR(64) NOT NULL,
    
    -- Variant identification
    combination_name VARCHAR(255) NOT NULL,
    variant_config JSONB NOT NULL,  -- JSONB for efficient querying
    
    -- Execution outcome
    success BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT,
    
    -- Metrics (JSONB for flexible schema)
    metrics JSONB,
    overall_score DOUBLE PRECISION DEFAULT 0.0,
    
    -- Timing
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER DEFAULT 0,
    
    -- Resource usage
    peak_memory_mb DOUBLE PRECISION,
    cpu_seconds DOUBLE PRECISION,
    
    -- Worker identification (for Ray)
    worker_id VARCHAR(255),
    worker_hostname VARCHAR(255),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- B-Tree Indexes (Primary Key Lookups)
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

-- ═══════════════════════════════════════════════════════════════════════════════
-- BRIN Indexes (Time-Series Queries)
-- BRIN is more efficient than B-Tree for time-series data with natural ordering
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_batch_test_results_time_brin 
    ON wtb_batch_test_results USING BRIN(created_at);

CREATE INDEX IF NOT EXISTS idx_batch_tests_created_brin 
    ON wtb_batch_tests USING BRIN(created_at);

CREATE INDEX IF NOT EXISTS idx_executions_created_brin 
    ON wtb_executions USING BRIN(created_at);

-- ═══════════════════════════════════════════════════════════════════════════════
-- GIN Indexes (JSONB Queries)
-- Enables efficient querying of JSONB fields
-- ═══════════════════════════════════════════════════════════════════════════════

-- Query variant configs: WHERE variant_config @> '{"node_1": "variant_a"}'
CREATE INDEX IF NOT EXISTS idx_batch_test_results_variant_config 
    ON wtb_batch_test_results USING GIN(variant_config);

-- Query metrics: WHERE metrics @> '{"accuracy": 0.9}'
CREATE INDEX IF NOT EXISTS idx_batch_test_results_metrics 
    ON wtb_batch_test_results USING GIN(metrics);

-- ═══════════════════════════════════════════════════════════════════════════════
-- Composite Indexes for Common Query Patterns
-- ═══════════════════════════════════════════════════════════════════════════════

-- Status + time for batch test listing
CREATE INDEX IF NOT EXISTS idx_batch_tests_status_created 
    ON wtb_batch_tests(status, created_at DESC);

-- Workflow + status for execution queries
CREATE INDEX IF NOT EXISTS idx_executions_workflow_status 
    ON wtb_executions(workflow_id, status);

-- ═══════════════════════════════════════════════════════════════════════════════
-- Table Partitioning (Optional - for high-volume deployments)
-- ═══════════════════════════════════════════════════════════════════════════════

-- Example: Partition batch_test_results by month
-- Uncomment and modify if expecting >10M results per month

/*
CREATE TABLE wtb_batch_test_results_partitioned (
    LIKE wtb_batch_test_results INCLUDING ALL
) PARTITION BY RANGE (created_at);

-- Create monthly partitions
CREATE TABLE wtb_batch_test_results_2025_01 
    PARTITION OF wtb_batch_test_results_partitioned
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

CREATE TABLE wtb_batch_test_results_2025_02 
    PARTITION OF wtb_batch_test_results_partitioned
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
*/

-- ═══════════════════════════════════════════════════════════════════════════════
-- Connection Pool Configuration (PgBouncer recommended settings)
-- ═══════════════════════════════════════════════════════════════════════════════

-- Add these to pgbouncer.ini:
-- [databases]
-- wtb = host=localhost dbname=wtb pool_mode=transaction max_db_connections=100
--
-- [pgbouncer]
-- pool_mode = transaction
-- max_client_conn = 1000
-- default_pool_size = 25
-- min_pool_size = 5
-- reserve_pool_size = 5

-- ═══════════════════════════════════════════════════════════════════════════════
-- Vacuum and Analyze Settings
-- ═══════════════════════════════════════════════════════════════════════════════

-- Adjust autovacuum for batch_test_results (high insert rate)
ALTER TABLE wtb_batch_test_results SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.02
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- Grants (adjust for your user/role setup)
-- ═══════════════════════════════════════════════════════════════════════════════

-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO wtb_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO wtb_app;

