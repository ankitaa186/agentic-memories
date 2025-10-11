-- Active: 1760220859473@@127.0.0.1@7687@neo4j
-- Active: 1760219563785@@127.0.0.1@7474@neo4j
// Up: create indexes and constraints for episodes and relationships
CREATE CONSTRAINT episode_id_unique IF NOT EXISTS
FOR (e:Episode) REQUIRE e.id IS UNIQUE;

// Optional: indexes on common properties
CREATE INDEX episode_event_type IF NOT EXISTS FOR (e:Episode) ON (e.event_type);
CREATE INDEX episode_user_id IF NOT EXISTS FOR (e:Episode) ON (e.user_id);

// Relationship types referenced in docs: LED_TO, INFLUENCED, SIMILAR_TO
// No DDL required for relationship types in Neo4j; enforced via application logic.

// Down:
// DROP CONSTRAINT episode_id_unique IF EXISTS;
// DROP INDEX episode_event_type IF EXISTS;
// DROP INDEX episode_user_id IF EXISTS;

