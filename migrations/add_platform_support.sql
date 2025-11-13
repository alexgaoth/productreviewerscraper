-- Migration: Add Multi-Platform Support
-- Date: 2025-11-13
-- Description: Extends database schema to support multiple e-commerce platforms (Amazon, Shopify, etc.)

-- ======================
-- SELLERS TABLE UPDATES
-- ======================

-- Add platform column
ALTER TABLE sellers ADD COLUMN IF NOT EXISTS platform VARCHAR(20) NOT NULL DEFAULT 'amazon';

-- Add encrypted access token field for Shopify (permanent tokens)
ALTER TABLE sellers ADD COLUMN IF NOT EXISTS encrypted_access_token TEXT NULL;

-- Make Amazon-specific fields nullable
ALTER TABLE sellers ALTER COLUMN marketplace_id DROP NOT NULL;
ALTER TABLE sellers ALTER COLUMN lwa_client_id DROP NOT NULL;
ALTER TABLE sellers ALTER COLUMN encrypted_refresh_token DROP NOT NULL;

-- Add index on platform
CREATE INDEX IF NOT EXISTS idx_sellers_platform ON sellers(platform);

-- Add check constraint for platform values
ALTER TABLE sellers ADD CONSTRAINT IF NOT EXISTS check_platform_sellers
    CHECK (platform IN ('amazon', 'shopify'));


-- ======================
-- FETCH_JOBS TABLE UPDATES
-- ======================

-- Add platform column
ALTER TABLE fetch_jobs ADD COLUMN IF NOT EXISTS platform VARCHAR(20) NOT NULL DEFAULT 'amazon';

-- Add Shopify-specific fields
ALTER TABLE fetch_jobs ADD COLUMN IF NOT EXISTS product_ids JSON NULL;
ALTER TABLE fetch_jobs ADD COLUMN IF NOT EXISTS request_params JSON NULL;

-- Add generic progress tracking fields
ALTER TABLE fetch_jobs ADD COLUMN IF NOT EXISTS total_items INTEGER DEFAULT 0;
ALTER TABLE fetch_jobs ADD COLUMN IF NOT EXISTS completed_items INTEGER DEFAULT 0;
ALTER TABLE fetch_jobs ADD COLUMN IF NOT EXISTS failed_items INTEGER DEFAULT 0;

-- Make Amazon-specific fields nullable
ALTER TABLE fetch_jobs ALTER COLUMN marketplace_id DROP NOT NULL;
ALTER TABLE fetch_jobs ALTER COLUMN asins DROP NOT NULL;

-- Add index on platform
CREATE INDEX IF NOT EXISTS idx_fetch_jobs_platform ON fetch_jobs(platform);

-- Add check constraint for platform values
ALTER TABLE fetch_jobs ADD CONSTRAINT IF NOT EXISTS check_platform_fetch_jobs
    CHECK (platform IN ('amazon', 'shopify'));


-- ======================
-- ASIN_FETCH_RESULTS TABLE UPDATES
-- ======================

-- Add platform column
ALTER TABLE asin_fetch_results ADD COLUMN IF NOT EXISTS platform VARCHAR(20) NOT NULL DEFAULT 'amazon';

-- Add Shopify product ID field
ALTER TABLE asin_fetch_results ADD COLUMN IF NOT EXISTS product_id VARCHAR(50) NULL;

-- Make ASIN nullable (for non-Amazon platforms)
ALTER TABLE asin_fetch_results ALTER COLUMN asin DROP NOT NULL;

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_asin_fetch_results_platform ON asin_fetch_results(platform);
CREATE INDEX IF NOT EXISTS idx_asin_fetch_results_product_id ON asin_fetch_results(product_id);

-- Add check constraint for platform values
ALTER TABLE asin_fetch_results ADD CONSTRAINT IF NOT EXISTS check_platform_asin_fetch_results
    CHECK (platform IN ('amazon', 'shopify'));


-- ======================
-- DATA MIGRATION
-- ======================

-- Set platform='amazon' for all existing records (should already be default)
UPDATE sellers SET platform = 'amazon' WHERE platform IS NULL OR platform = '';
UPDATE fetch_jobs SET platform = 'amazon' WHERE platform IS NULL OR platform = '';
UPDATE asin_fetch_results SET platform = 'amazon' WHERE platform IS NULL OR platform = '';

-- Copy legacy progress tracking to new generic fields
UPDATE fetch_jobs
SET
    total_items = total_asins,
    completed_items = completed_asins,
    failed_items = failed_asins
WHERE total_items = 0;


-- ======================
-- VERIFICATION QUERIES
-- ======================

-- Uncomment to verify migration

-- SELECT 'Sellers by platform' as check_name, platform, COUNT(*) as count
-- FROM sellers
-- GROUP BY platform;

-- SELECT 'Jobs by platform' as check_name, platform, COUNT(*) as count
-- FROM fetch_jobs
-- GROUP BY platform;

-- SELECT 'Fetch results by platform' as check_name, platform, COUNT(*) as count
-- FROM asin_fetch_results
-- GROUP BY platform;

-- SELECT 'Jobs with mismatched counts' as check_name, COUNT(*) as count
-- FROM fetch_jobs
-- WHERE total_items != total_asins OR completed_items != completed_asins OR failed_items != failed_asins;


-- ======================
-- ROLLBACK SCRIPT
-- ======================

-- Uncomment and run if rollback is needed

-- ALTER TABLE sellers DROP CONSTRAINT IF EXISTS check_platform_sellers;
-- ALTER TABLE sellers DROP COLUMN IF EXISTS encrypted_access_token;
-- ALTER TABLE sellers DROP COLUMN IF EXISTS platform;
-- DROP INDEX IF EXISTS idx_sellers_platform;

-- ALTER TABLE fetch_jobs DROP CONSTRAINT IF EXISTS check_platform_fetch_jobs;
-- ALTER TABLE fetch_jobs DROP COLUMN IF EXISTS request_params;
-- ALTER TABLE fetch_jobs DROP COLUMN IF EXISTS product_ids;
-- ALTER TABLE fetch_jobs DROP COLUMN IF EXISTS failed_items;
-- ALTER TABLE fetch_jobs DROP COLUMN IF EXISTS completed_items;
-- ALTER TABLE fetch_jobs DROP COLUMN IF EXISTS total_items;
-- ALTER TABLE fetch_jobs DROP COLUMN IF EXISTS platform;
-- DROP INDEX IF EXISTS idx_fetch_jobs_platform;

-- ALTER TABLE asin_fetch_results DROP CONSTRAINT IF EXISTS check_platform_asin_fetch_results;
-- ALTER TABLE asin_fetch_results DROP COLUMN IF EXISTS product_id;
-- ALTER TABLE asin_fetch_results DROP COLUMN IF EXISTS platform;
-- DROP INDEX IF EXISTS idx_asin_fetch_results_product_id;
-- DROP INDEX IF EXISTS idx_asin_fetch_results_platform;
