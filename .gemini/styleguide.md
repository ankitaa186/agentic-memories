# Agentic Memories Code Style Guide

This document describes the coding standards for the Agentic Memories project.

## Project Overview

- **Backend**: Python 3.12+ with FastAPI, async/await patterns
- **Frontend**: TypeScript with React 18
- **Architecture**: Service-oriented with polyglot persistence (ChromaDB, TimescaleDB/PostgreSQL, Redis)

## Python Backend Standards

### Type Hints

All functions must have complete type annotations:

```python
# Good
async def get_memories(user_id: str, limit: int = 10) -> list[Memory]:
    ...

# Bad - missing return type
async def get_memories(user_id: str, limit: int = 10):
    ...
```

Use `Optional[]` or `| None` for nullable types. Prefer the union syntax for Python 3.10+.

### Async Patterns

- All database operations must be async
- Use `asyncio.gather()` for parallel operations
- Never block the event loop with synchronous I/O

```python
# Good - parallel database calls
results = await asyncio.gather(
    chroma_client.query(embedding),
    timescale_client.get_recent(user_id),
)

# Bad - sequential when parallel is possible
chroma_result = await chroma_client.query(embedding)
timescale_result = await timescale_client.get_recent(user_id)
```

### Error Handling

- Use specific exception types, not bare `except:`
- Log errors with context before re-raising
- FastAPI endpoints should return appropriate HTTP status codes

```python
# Good
try:
    result = await db.execute(query)
except DatabaseError as e:
    logger.error(f"Database query failed for user {user_id}: {e}")
    raise HTTPException(status_code=500, detail="Database error")

# Bad
try:
    result = await db.execute(query)
except:
    raise
```

### Naming Conventions

- Classes: `PascalCase` (e.g., `MemoryService`, `EpisodicMemory`)
- Functions/methods: `snake_case` (e.g., `get_memories`, `extract_profile`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_RETRY_COUNT`)
- Private methods: prefix with underscore (e.g., `_internal_helper`)

### Service Layer Pattern

Services should:
- Accept dependencies via constructor injection
- Have a single responsibility
- Return domain objects, not raw database results

```python
class MemoryService:
    def __init__(self, chroma: ChromaClient, timescale: TimescaleClient):
        self.chroma = chroma
        self.timescale = timescale

    async def retrieve(self, query: str, user_id: str) -> list[Memory]:
        ...
```

### Pydantic Models

- Use Pydantic v2 syntax
- Define explicit `model_config` instead of inner `Config` class
- Use `Field()` for validation and documentation

```python
class MemoryCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    memory_type: MemoryType
    user_id: str

    model_config = ConfigDict(str_strip_whitespace=True)
```

## TypeScript Frontend Standards

### Component Structure

- Use functional components with hooks
- Props interfaces should be named `{ComponentName}Props`
- Keep components focused and composable

```typescript
interface MemoryCardProps {
  memory: Memory;
  onDelete?: (id: string) => void;
}

export function MemoryCard({ memory, onDelete }: MemoryCardProps) {
  ...
}
```

### Type Safety

- Avoid `any` type - use `unknown` if type is truly unknown
- Define explicit return types for functions
- Use discriminated unions for state management

### API Integration

- Use React Query for data fetching
- Handle loading and error states explicitly
- Type API responses with shared types

## Testing Standards

### Python Tests

- Use pytest with async support (`pytest-asyncio`)
- Mock external services, not internal logic
- Test file naming: `test_{module_name}.py`
- Use descriptive test names that explain the scenario

```python
async def test_memory_retrieval_returns_empty_list_for_new_user():
    ...

async def test_memory_extraction_skips_low_worthiness_content():
    ...
```

### Test Organization

- Unit tests in `tests/unit/`
- Integration tests in `tests/e2e/`
- LLM evaluation tests in `tests/evals/`

## Documentation

- Public functions need docstrings explaining purpose and parameters
- Complex algorithms should have inline comments
- API endpoints need OpenAPI descriptions via FastAPI decorators

## Security Considerations

- Never log sensitive data (API keys, user content in full)
- Validate all user input at API boundaries
- Use parameterized queries for all database operations
- Sanitize LLM outputs before storing

## Performance Guidelines

- Use database indexes for frequently queried fields
- Implement pagination for list endpoints
- Cache expensive computations in Redis with appropriate TTL
- Profile before optimizing - avoid premature optimization
