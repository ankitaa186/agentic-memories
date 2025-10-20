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

// Portfolio graph relationships in Neo4j
// Track holding correlations, sector relationships, and goal dependencies

// Create constraints for portfolio nodes
CREATE CONSTRAINT holding_id_unique IF NOT EXISTS
FOR (h:Holding) REQUIRE h.id IS UNIQUE;

CREATE CONSTRAINT sector_name_unique IF NOT EXISTS
FOR (s:Sector) REQUIRE s.name IS UNIQUE;

CREATE CONSTRAINT goal_id_unique IF NOT EXISTS
FOR (g:Goal) REQUIRE g.id IS UNIQUE;

// Create indexes for common queries
// Note: Indexes on non-unique properties may require adjustment based on Neo4j version
// For Neo4j 5.x, use: CREATE INDEX FOR (h:Holding) ON (h.ticker);
// Skipping property indexes as they may not be needed for initial setup

// Example relationship patterns (created by application logic):
// (h1:Holding {ticker: 'AAPL'})-[:CORRELATED_WITH {coefficient: 0.85}]->(h2:Holding {ticker: 'MSFT'})
// (h1)-[:IN_SECTOR {sector: 'Technology'}]->(s:Sector {name: 'Technology'})
// (h1)-[:AFFECTS {impact: 'high'}]->(g:Goal {name: 'Retirement Fund'})
// (h1)-[:SIMILAR_TO {reason: 'same_industry'}]->(h2)

