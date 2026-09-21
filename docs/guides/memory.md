# Memory that carries across sessions

[Documentation](../README.md) / Concepts

An agent uses its current context window to answer a request. Agentic Memories turns
submitted conversations into persistent memories, then exposes tools to recall the
useful context in later requests.
The integrating application decides when to call those tools and what retrieved context
to include in the model's prompt.

![Conversation extraction, organization, storage, and later recall.](../assets/extraction-pipeline.svg)

## Biomimetic design

Human memory offers useful design inspiration: episodic records describe experiences;
semantic records retain facts; procedural records capture skills; emotional records
retain emotional context. The software implements distinct record types, retrieval paths,
and lifecycle operations, rather than a biological model of a brain.

The consciousness-inspired ambition is personal continuity across interactions. A companion
can use remembered preferences and experiences to contextualize its next response. The
service does not establish that the companion has consciousness or subjective experience.

## Conversation extraction

Use `store_transcript` to submit conversation turns. The caller provides dialogue;
the pipeline does the work of deciding what to retain and turning it into memories.
The [unified ingestion graph](../../src/services/unified_ingestion_graph.py) performs:

1. **Worthiness assessment:** evaluate whether the conversation contains information
   worth retaining. A conversation can end here without creating memories.
2. **Extraction:** use the conversation and relevant existing memories to identify
   candidate personal facts, experiences, preferences, and other useful context.
3. **Classification and enrichment:** organize candidates into memory types, build
   memory records and embeddings, and retain supported metadata.
4. **Duplicate checks:** compare candidates against existing content and semantic matches.
5. **Profile extraction and storage:** derive structured profile fields where applicable,
   store vector memories, and write applicable typed records.

The graph is a sequence of processing stages, not a claim that every conversation
creates every memory type or that every storage backend succeeds atomically. Inspect
results; extraction wording, classification, and count vary with the model. Avoid
reporting an empty extraction as success in an example intended to demonstrate recall.

The [main example](../../examples/README.md) runs this pipeline through MCP, prints
actual extracted memories, and checks that some of those records are recalled in a
new session. Orchestrator tools provide a conversational ingestion path with their own
buffering and retrieval behavior; see the [integration guide](../internal/CHATBOT_INTEGRATION_GUIDE.md).

## Advanced: preformatted memories

`store_memory_direct` is useful for migrations, imports, or an application that already
produces a memory record. It bypasses worthiness assessment and conversation extraction.
The [direct-write example](../../examples/README.md#advanced-direct-write-example) covers
that path separately; it is not evidence that the extraction pipeline works.

## Recall

Use `retrieve` with a query for semantic relevance. Ordinary text recall ranks by measured
cosine similarity. Time, layer/type, and metadata filters narrow the selection; filter-only
retrieval uses its own ordering rules. Structured, persona, and narrative tools offer
additional retrieval paths. See [REST contracts](../api-contracts-server.md) and MCP discovery
for accepted fields and defaults.

Retrieved content is evidence for the agent's next answer, not proof that every stored
statement is true. Keep the distinction between remembered user statements and verified facts.

## Update and retain

- `patch_memory` changes a stored record; content changes regenerate its embedding.
- `delete_memory` removes a record across the applicable stores.
- An explicit `ttl_seconds` on direct writes applies to every memory layer. If omitted,
  short-term records use the configured default; other layers have no expiration.
- PATCH with `ttl_seconds: null` clears expiration; leaving the field out preserves it.
- TTL deletion is asynchronous. A record can linger until the next sweep; expiration is
  not a hard real-time deletion guarantee.
- Maintenance supports cleanup, deduplication, and LLM-based consolidation. Configure
  scheduling deliberately and inspect its results.

## Profiles and structured records

User profiles store named fields and completeness information. Portfolio tools support
equities and options; see the [portfolio guide](../portfolio-api.md). These structured
records complement conversational memory and have their own APIs and validation.

## Scheduled intents

Intents retain a requested action, its schedule or trigger conditions, and execution state.
An integrating worker discovers eligible intents, claims them, performs the action, and
reports the outcome. Creating an intent alone does not send an email or run an external task.

## User scope and access

Requests carry user IDs and some mutations verify record ownership. These checks do not
provide a complete identity or tenant-authorization system. Review [access controls](../MCP.md#access-controls-and-hosting)
before allowing remote users or agents to access your deployment.
