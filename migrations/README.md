# Database Migrations

## Overview

This directory contains database schema migrations for all storage layers, organized by database type. The migration system tracks applied migrations and supports both fresh deployments and incremental upgrades.

## Structure

```
migrations/
├── migrate.sh              # Migration manager script
├── DROP_ALL.sql            # Clean slate (dev only)
│
├── timescaledb/            # Time-series data
│   ├── 001_episodic_memories.sql
│   ├── 002_emotional_memories.sql
│   └── 003_portfolio_snapshots.sql
│
├── postgres/               # Relational data
│   ├── 001_procedural_memories.sql
│   ├── 002_skill_progressions.sql
│   ├── 003_semantic_memories.sql
│   ├── 004_identity_memories.sql
│   ├── 005_portfolio_holdings.sql
│   ├── 006_portfolio_transactions.sql
│   └── 007_portfolio_preferences.sql
│
├── neo4j/                  # Graph relationships
│   └── 001_graph_constraints.cql
│
└── chromadb/               # Vector embeddings
    └── 001_collections.py
```

## Migration Manager

### Commands

```bash
# Run pending migrations (safe, incremental)
./migrations/migrate.sh up

# Preview migrations without running (dry-run mode)
./migrations/migrate.sh up --dry-run

# Rollback last migration
./migrations/migrate.sh down

# Rollback last 3 migrations
./migrations/migrate.sh down 3

# Preview rollback without running
./migrations/migrate.sh down --dry-run

# Show migration status
./migrations/migrate.sh status

# Validate migration files (check for matching up/down pairs)
./migrations/migrate.sh validate

# Fresh install (DESTRUCTIVE - dev only)
./migrations/migrate.sh fresh

# Show help
./migrations/migrate.sh help
```

### Migration Generator

Create new migration pairs automatically with proper numbering:

```bash
# Generate a PostgreSQL migration
./migrations/generate.sh postgres add_user_preferences

# Generate a TimescaleDB migration
./migrations/generate.sh timescaledb add_metrics_table

# Generate a Neo4j migration
./migrations/generate.sh neo4j add_user_relationships

# Generate a ChromaDB migration
./migrations/generate.sh chromadb add_new_collection
```

The generator:
- Auto-numbers migrations sequentially
- Creates both `.up` and `.down` files
- Includes templates with best practices
- Handles all database types

### First Time Deployment

```bash
# 1. Set environment variables
export TIMESCALE_DSN="postgresql://user:pass@host:5432/dbname"
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="password"

# 2. Run migrations
./migrations/migrate.sh up

# 3. Verify
./migrations/migrate.sh status
```

### Adding New Migrations

```bash
# 1. Generate migration pair using the generator
./migrations/generate.sh postgres new_feature

# 2. Edit the generated files to add your changes
#    - Edit migrations/postgres/008_new_feature.up.sql (forward migration)
#    - Edit migrations/postgres/008_new_feature.down.sql (rollback migration)

# 3. Test locally
./migrations/migrate.sh validate     # Validate migration files
./migrations/migrate.sh up --dry-run # Preview changes
./migrations/migrate.sh up           # Apply migration
./migrations/migrate.sh down --dry-run # Preview rollback
./migrations/migrate.sh down         # Test rollback
./migrations/migrate.sh up           # Re-apply

# 4. Commit both migration files to git
git add migrations/postgres/008_new_feature.up.sql
git add migrations/postgres/008_new_feature.down.sql
git commit -m "Add new feature migration with rollback"

# 5. Deploy - migration runs automatically on next deployment
```

### Incremental Upgrades

The migration system tracks which migrations have been applied in the `schema_migrations` table. When you run `migrate.sh up`, it:

1. Checks which migrations are already applied
2. Skips applied migrations
3. Runs only new migrations in order
4. Records each successful migration

This means you can safely run `migrate.sh up` multiple times - it will only apply what's new.

### Dev Environment Reset

```bash
# Nuclear option - drops everything and rebuilds
./migrations/migrate.sh fresh

# Requires typing "DELETE ALL DATA" to confirm
```

## Migration Tracking

Migrations are tracked in the `schema_migrations` table:

```sql
SELECT * FROM schema_migrations ORDER BY applied_at DESC;
```

| database_type | migration_file | applied_at | checksum |
|---------------|----------------|------------|----------|
| postgres | 002_skill_progressions.sql | 2025-10-12 18:30:00 | abc123... |
| timescaledb | 001_episodic_memories.sql | 2025-10-12 18:29:55 | def456... |

## Best Practices

### Naming Conventions

- Use sequential numbers: `001_`, `002_`, `003_`
- Descriptive names: `002_skill_progressions.up.sql`
- Each database type starts from `001`
- Always create matching `.up` and `.down` pairs

### Migration Files

- **Idempotent**: Use `IF NOT EXISTS` where possible
- **Reversible**: Always create down migrations for production safety
- **Tested**: Test both up and down migrations on dev before production
- **Small**: One logical change per migration
- **Documented**: Add comments explaining complex changes
- **Safe Rollbacks**: Ensure down migrations properly clean up all changes

### Example Migration

```sql
-- 008_add_user_preferences.sql
-- Adds user preferences table for customization

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id VARCHAR(64) PRIMARY KEY,
    theme VARCHAR(16) DEFAULT 'light',
    notifications_enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_prefs_theme 
    ON user_preferences(theme);
```

### Production Deployments

```bash
# 1. Validate migrations locally
./migrations/migrate.sh validate

# 2. Check what will be applied
./migrations/migrate.sh status

# 3. Preview changes (dry-run)
./migrations/migrate.sh up --dry-run

# 4. Backup database
pg_dump $TIMESCALE_DSN > backup_$(date +%Y%m%d).sql

# 5. Run migrations
./migrations/migrate.sh up

# 6. Verify application works
curl http://localhost:8080/health/full

# 7. If issues arise, rollback
./migrations/migrate.sh down   # Rollback last migration

# 8. Monitor logs
docker-compose logs -f api
```

## Troubleshooting

### Migration Failed

```bash
# Check error details
./migrations/migrate.sh status

# If migration is partially applied:
# 1. Manually fix the database state
# 2. Mark as applied or remove from tracking table

# Remove failed migration from tracking (use with caution):
psql $TIMESCALE_DSN -c "DELETE FROM schema_migrations WHERE migration_file='008_broken.sql'"
```

### Reset Dev Environment

```bash
# Complete reset
./migrations/migrate.sh fresh

# Then rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
```

### Check Applied Migrations

```bash
# Show all applied migrations
psql $TIMESCALE_DSN -c "SELECT * FROM schema_migrations ORDER BY applied_at DESC;"

# Count by database type
psql $TIMESCALE_DSN -c "SELECT database_type, COUNT(*) FROM schema_migrations GROUP BY database_type;"
```

## Database-Specific Notes

### TimescaleDB

- Hypertables require special handling
- Compression policies applied after creation
- Retention policies commented out (configure as needed)

### PostgreSQL

- Standard SQL migrations
- Use constraints and indexes liberally
- JSONB for flexible schemas

### Neo4j

- Requires `cypher-shell` or manual execution
- Constraint syntax varies by Neo4j version
- Check Neo4j logs if migration fails

### ChromaDB

- Python-based migrations
- Collections created via API
- Requires ChromaDB to be accessible

## CI/CD Integration

### Docker Entrypoint

```bash
#!/bin/bash
# Run migrations before starting app
./migrations/migrate.sh up

# Start application
exec python -m uvicorn src.app:app --host 0.0.0.0 --port 8080
```

### GitHub Actions

```yaml
- name: Run Migrations
  env:
    TIMESCALE_DSN: ${{ secrets.DATABASE_URL }}
  run: |
    ./migrations/migrate.sh up
```

## Support

For issues or questions:
1. Check `./migrations/migrate.sh help`
2. Review this README
3. Check migration logs in `schema_migrations` table
4. Contact dev team

