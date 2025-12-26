-- Epic 6 Story 6.2: Condition Expression Support
-- Add condition_type and condition_expression columns for flexible conditions

-- 1. Add condition_type column for categorizing conditions (price, portfolio, silence)
ALTER TABLE scheduled_intents
ADD COLUMN condition_type VARCHAR(32);

-- 2. Add condition_expression column for human-readable condition strings
ALTER TABLE scheduled_intents
ADD COLUMN condition_expression TEXT;

-- 3. Add comments for the new columns
COMMENT ON COLUMN scheduled_intents.condition_type IS 'Condition category: price, portfolio, silence';
COMMENT ON COLUMN scheduled_intents.condition_expression IS 'Human-readable condition expression (e.g., NVDA < 130, any_holding_change > 5%)';

-- Note: Both columns are nullable for backward compatibility with existing triggers
