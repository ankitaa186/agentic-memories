// Rollback Neo4j graph constraints and indexes
// Drops indexes, constraints, and relationships

// Drop indexes
DROP INDEX episode_user_id IF EXISTS;
DROP INDEX episode_event_type IF EXISTS;

// Drop constraints
DROP CONSTRAINT goal_id_unique IF EXISTS;
DROP CONSTRAINT sector_name_unique IF EXISTS;
DROP CONSTRAINT holding_id_unique IF EXISTS;
DROP CONSTRAINT episode_id_unique IF EXISTS;

// Note: Nodes and relationships must be manually deleted if needed
// MATCH (n) DETACH DELETE n;  // WARNING: Deletes all data

