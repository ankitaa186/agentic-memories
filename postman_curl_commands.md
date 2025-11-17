# Postman Collection - Orchestrator Test Scenario

Import these curl commands into Postman using the "Import" feature (Raw text option).

## Setup
- API URL: `http://localhost:8080`
- User ID: `sf-worker-20s`
- Conversation ID: `sf-worker-conversation`

---

## 1. Baseline Context Storage

```bash
curl -X POST http://localhost:8080/v1/store \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "sf-worker-20s",
    "history": [
      {
        "role": "user",
        "content": "I am a 27-year-old software engineer living in San Francisco with my girlfriend Sarah. We have been together for 3 years and live in a small apartment in the Mission District."
      }
    ]
  }'
```

---

## 2. Orchestrator Message Streaming

### Message 1: Work Stress
```bash
curl -X POST http://localhost:8080/v1/orchestrator/message \
  -H 'Content-Type: application/json' \
  -d '{
    "conversation_id": "sf-worker-conversation",
    "role": "user",
    "content": "Work has been really stressful lately. My manager keeps pushing unrealistic deadlines and I am feeling overwhelmed. We are working on a critical project launch next month.",
    "metadata": {"user_id": "sf-worker-20s"},
    "flush": false
  }'
```

### Message 2: Relationship Issue
```bash
curl -X POST http://localhost:8080/v1/orchestrator/message \
  -H 'Content-Type: application/json' \
  -d '{
    "conversation_id": "sf-worker-conversation",
    "role": "user",
    "content": "Sarah and I had another fight last night. She thinks I am not present enough because I am always working. I feel stuck between my job and my relationship.",
    "metadata": {"user_id": "sf-worker-20s"},
    "flush": false
  }'
```

### Message 3: SF Lifestyle / Financial Pressure
```bash
curl -X POST http://localhost:8080/v1/orchestrator/message \
  -H 'Content-Type: application/json' \
  -d '{
    "conversation_id": "sf-worker-conversation",
    "role": "user",
    "content": "The rent in Mission District is killing me. $3500 for a tiny apartment. Sarah wants to move to Oakland but I am worried about the commute. Plus all my friends are in SF.",
    "metadata": {"user_id": "sf-worker-20s"},
    "flush": false
  }'
```

### Message 4: Emotional State
```bash
curl -X POST http://localhost:8080/v1/orchestrator/message \
  -H 'Content-Type: application/json' \
  -d '{
    "conversation_id": "sf-worker-conversation",
    "role": "user",
    "content": "I am feeling really depressed about everything. Sometimes I wonder if I made the right choices coming to SF. The pressure is intense and I do not know how much longer I can handle this.",
    "metadata": {"user_id": "sf-worker-20s"},
    "flush": false
  }'
```

### Message 5: Specific Work Event
```bash
curl -X POST http://localhost:8080/v1/orchestrator/message \
  -H 'Content-Type: application/json' \
  -d '{
    "conversation_id": "sf-worker-conversation",
    "role": "user",
    "content": "Today my manager called me into a meeting and criticized my work quality. He said I missed some important details in the last sprint review. I felt humiliated in front of the team.",
    "metadata": {"user_id": "sf-worker-20s"},
    "flush": false
  }'
```

### Message 6: Relationship Therapy Request (with flush)
```bash
curl -X POST http://localhost:8080/v1/orchestrator/message \
  -H 'Content-Type: application/json' \
  -d '{
    "conversation_id": "sf-worker-conversation",
    "role": "user",
    "content": "Sarah asked me to go to couples therapy. She says we need to work on our communication. I am scared but I think she might be right. We have been together for 3 years and I do not want to lose her.",
    "metadata": {"user_id": "sf-worker-20s"},
    "flush": true
  }'
```

---

## 3. Orchestrator Retrieval Queries

### Query 1: Work Stress
```bash
curl -X POST http://localhost:8080/v1/orchestrator/retrieve \
  -H 'Content-Type: application/json' \
  -d '{
    "conversation_id": "sf-worker-conversation",
    "query": "work stress manager deadlines",
    "metadata": {"user_id": "sf-worker-20s"},
    "limit": 5
  }'
```

### Query 2: Relationship
```bash
curl -X POST http://localhost:8080/v1/orchestrator/retrieve \
  -H 'Content-Type: application/json' \
  -d '{
    "conversation_id": "sf-worker-conversation",
    "query": "Sarah relationship fight therapy",
    "metadata": {"user_id": "sf-worker-20s"},
    "limit": 5
  }'
```

### Query 3: Emotional State
```bash
curl -X POST http://localhost:8080/v1/orchestrator/retrieve \
  -H 'Content-Type: application/json' \
  -d '{
    "conversation_id": "sf-worker-conversation",
    "query": "depressed feeling overwhelmed pressure",
    "metadata": {"user_id": "sf-worker-20s"},
    "limit": 5
  }'
```

### Query 4: Overall Context
```bash
curl -X POST http://localhost:8080/v1/orchestrator/retrieve \
  -H 'Content-Type: application/json' \
  -d '{
    "conversation_id": "sf-worker-conversation",
    "query": "overall situation context",
    "metadata": {"user_id": "sf-worker-20s"},
    "limit": 5
  }'
```

---

## 4. Persona-Aware Retrieval

### With Narrative and Explainability
```bash
curl -X POST http://localhost:8080/v1/retrieve \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "sf-worker-20s",
    "query": "work stress relationship balance",
    "limit": 5,
    "granularity": "episodic",
    "include_narrative": true,
    "explain": true
  }'
```

### With Raw Granularity
```bash
curl -X POST http://localhost:8080/v1/retrieve \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "sf-worker-20s",
    "query": "work stress relationship balance",
    "limit": 5,
    "granularity": "raw",
    "include_narrative": false
  }'
```

---

## 5. Traditional Retrieval (Comparison)

### GET Request
```bash
curl -X GET "http://localhost:8080/v1/retrieve?user_id=sf-worker-20s&query=relationship+work+stress&limit=3"
```

### POST Request (Simple)
```bash
curl -X POST http://localhost:8080/v1/retrieve \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "sf-worker-20s",
    "query": "relationship work stress",
    "limit": 3
  }'
```

---

## 6. Transcript Processing

### Full Conversation Transcript
```bash
curl -X POST http://localhost:8080/v1/orchestrator/transcript \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": "sf-worker-20s",
    "history": [
      {
        "role": "user",
        "content": "I am thinking about asking for a raise. My performance has been good despite the stress."
      },
      {
        "role": "assistant",
        "content": "That sounds like a reasonable next step. What makes you feel ready?"
      },
      {
        "role": "user",
        "content": "I completed three major features last quarter and got positive feedback from users. But I am nervous about the conversation with my manager."
      },
      {
        "role": "assistant",
        "content": "It is normal to feel nervous. Have you prepared talking points?"
      },
      {
        "role": "user",
        "content": "Yes, I have. I also want to ask for better work-life balance. Sarah and I need more time together."
      }
    ]
  }'
```

---

## 7. Health Check

```bash
curl -X GET http://localhost:8080/health
```

### Full Health Check
```bash
curl -X GET http://localhost:8080/health/full
```

---

## Postman Import Instructions

1. Open Postman
2. Click **Import** button
3. Select **Raw text** tab
4. Paste any of the curl commands above
5. Postman will automatically parse the request
6. Create a collection and organize by category

### Tips for Postman:
- Set `API_URL` as a collection variable for easy switching
- Create environment variables: `user_id`, `conversation_id`
- Use Pre-request Scripts to set variables dynamically
- Save responses as examples for documentation

---

## Environment Variables (Postman)

Create these variables in your Postman environment:

```json
{
  "api_url": "http://localhost:8080",
  "user_id": "sf-worker-20s",
  "conversation_id": "sf-worker-conversation"
}
```

Then use in requests as: `{{api_url}}/v1/orchestrator/message`





