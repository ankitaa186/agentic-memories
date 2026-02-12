# 🤖 **Complete Guide: Injecting Memories into Chatbots with Agentic Memories**

## **📋 Table of Contents**
1. [Quick Start Guide](#quick-start-guide)
2. [Architecture Overview](#architecture-overview)
3. [Integration Patterns](#integration-patterns)
4. [Persona-Aware Chatbots](#persona-aware-chatbots)
5. [Streaming Memory Orchestrator](#streaming-memory-orchestrator)
6. [Advanced Features](#advanced-features)
7. [Production Deployment](#production-deployment)
8. [Troubleshooting](#troubleshooting)

---

## **🚀 Quick Start Guide**

### **Step 1: Setup Agentic Memories**
```bash
# Clone and start the system
git clone <agentic-memories-repo>
cd agentic-memories
docker compose up -d

# Verify it's running
curl http://localhost:8080/health
```

### **Step 2: Basic Chatbot Integration**
```python
import requests
import json

class SimpleMemoryChatbot:
    def __init__(self, api_url="http://localhost:8080"):
        self.api_url = api_url
        self.session = requests.Session()
    
    def store_conversation(self, user_id: str, messages: list):
        """Store conversation as memories"""
        response = self.session.post(
            f"{self.api_url}/v1/store",
            json={
                "user_id": user_id,
                "history": messages
            }
        )
        return response.json()
    
    def get_memories(self, user_id: str, query: str, limit: int = 5):
        """Retrieve relevant memories"""
        response = self.session.get(
            f"{self.api_url}/v1/retrieve",
            params={
                "user_id": user_id,
                "query": query,
                "limit": limit
            }
        )
        return response.json()
    
    def chat(self, user_id: str, message: str):
        """Main chat function"""
        # 1. Store user message
        self.store_conversation(user_id, [{"role": "user", "content": message}])
        
        # 2. Get relevant memories
        memories = self.get_memories(user_id, message)
        
        # 3. Generate response (replace with your LLM)
        context = self.build_context(memories)
        response = self.generate_response(message, context)
        
        # 4. Store bot response
        self.store_conversation(user_id, [{"role": "assistant", "content": response}])
        
        return response
    
    def build_context(self, memories):
        """Build context from memories"""
        context_parts = []
        for memory in memories.get("results", []):
            context_parts.append(f"- {memory['content']}")
        return "\n".join(context_parts)
    
    def generate_response(self, message: str, context: str):
        """Generate response using your LLM"""
        # Replace this with your actual LLM call
        return f"Based on your memories: {context[:100]}... I understand you're asking about: {message}"

# Usage
chatbot = SimpleMemoryChatbot()
response = chatbot.chat("user123", "Tell me about my recent investments")
print(response)
```

---

## **🏗️ Architecture Overview**

### **Memory Flow Diagram**
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User Input    │───▶│   Memory Store   │───▶│   Persona       │
│                 │    │   (ChromaDB)     │    │   Detection     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Context       │    │   Multi-Tier     │    │   Dynamic       │
│   Retrieval     │◀───│   Summarization  │◀───│   Weighting     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │
         ▼
┌─────────────────┐
│   LLM Response   │
│   Generation    │
└─────────────────┘
```

### **Key Components**
- **Memory Storage**: ChromaDB + TimescaleDB + Redis
- **Persona Detection**: Automatic persona classification
- **Multi-Tier Summarization**: Raw → Episodic → Arc
- **Dynamic Weighting**: Persona-specific scoring
- **State Management**: Persistent user context

---

## **🔧 Integration Patterns**

### **Pattern 1: Basic Memory Injection**
```python
class BasicMemoryChatbot:
    def __init__(self, llm_client, memory_api_url="http://localhost:8080"):
        self.llm = llm_client
        self.memory_api = memory_api_url
        self.session = requests.Session()
    
    def process_message(self, user_id: str, message: str) -> str:
        # Store conversation
        self._store_message(user_id, message)
        
        # Retrieve context
        context = self._get_context(user_id, message)
        
        # Generate response
        response = self._generate_response(message, context)
        
        # Store response
        self._store_message(user_id, response, role="assistant")
        
        return response
    
    def _store_message(self, user_id: str, content: str, role: str = "user"):
        self.session.post(f"{self.memory_api}/v1/store", json={
            "user_id": user_id,
            "history": [{"role": role, "content": content}]
        })
    
    def _get_context(self, user_id: str, query: str) -> str:
        response = self.session.get(f"{self.memory_api}/v1/retrieve", params={
            "user_id": user_id,
            "query": query,
            "limit": 5
        })
        
        memories = response.json().get("results", [])
        return "\n".join([f"- {mem['content']}" for mem in memories])
    
    def _generate_response(self, message: str, context: str) -> str:
        prompt = f"""
        Context from user's memories:
        {context}
        
        User message: {message}
        
        Respond as a helpful assistant with access to the user's memory context.
        """
        return self.llm.generate(prompt)
```

### **Pattern 2: Persona-Aware Integration**
```python
class PersonaAwareChatbot:
    def __init__(self, llm_client, memory_api_url="http://localhost:8080"):
        self.llm = llm_client
        self.memory_api = memory_api_url
        self.session = requests.Session()
        self.persona_detector = PersonaDetector()
    
    def process_message(self, user_id: str, message: str) -> str:
        # Detect persona
        persona = self.persona_detector.detect(message)
        
        # Store with persona context
        self._store_with_persona(user_id, message, persona)
        
        # Retrieve with persona awareness
        context = self._get_persona_context(user_id, message, persona)
        
        # Generate persona-aware response
        response = self._generate_persona_response(message, context, persona)
        
        # Store response
        self._store_with_persona(user_id, response, persona, role="assistant")
        
        return response
    
    def _store_with_persona(self, user_id: str, content: str, persona: str, role: str = "user"):
        self.session.post(f"{self.memory_api}/v1/store", json={
            "user_id": user_id,
            "history": [{"role": role, "content": content}],
            "persona_context": {"forced_persona": persona}
        })
    
    def _get_persona_context(self, user_id: str, query: str, persona: str) -> dict:
        response = self.session.post(f"{self.memory_api}/v1/retrieve", json={
            "user_id": user_id,
            "query": query,
            "persona_context": {
                "forced_persona": persona,
                "mood": "conversational"
            },
            "granularity": "episodic",
            "include_narrative": True,
            "limit": 5
        })
        return response.json()
    
    def _generate_persona_response(self, message: str, context: dict, persona: str) -> str:
        memories = context.get("results", {}).get("memories", [])
        narrative = context.get("results", {}).get("narrative", "")
        
        prompt = f"""
        Persona: {persona}
        
        User's recent activities: {narrative}
        
        Relevant memories:
        {chr(10).join([f"- {mem['content']}" for mem in memories])}
        
        User message: {message}
        
        Respond as a {persona} specialist with access to the user's memory context.
        """
        return self.llm.generate(prompt)

class PersonaDetector:
    def detect(self, message: str) -> str:
        message_lower = message.lower()
        
        # Financial persona
        if any(keyword in message_lower for keyword in [
            "invest", "stock", "portfolio", "trading", "finance", "money", "budget"
        ]):
            return "finance"
        
        # Health persona
        if any(keyword in message_lower for keyword in [
            "fitness", "health", "exercise", "gym", "diet", "workout"
        ]):
            return "health"
        
        # Work persona
        if any(keyword in message_lower for keyword in [
            "work", "project", "meeting", "deadline", "career"
        ]):
            return "work"
        
        return "identity"
```

### **Pattern 3: Advanced Multi-Persona Integration**
```python
class MultiPersonaChatbot:
    def __init__(self, llm_client, memory_api_url="http://localhost:8080"):
        self.llm = llm_client
        self.memory_api = memory_api_url
        self.session = requests.Session()
        self.conversation_cache = {}
    
    def process_message(self, user_id: str, message: str) -> str:
        # Get conversation history
        conversation = self.conversation_cache.get(user_id, [])
        conversation.append({"role": "user", "content": message})
        
        # Get multi-persona context
        contexts = self._get_multi_persona_context(user_id, message)
        
        # Generate comprehensive response
        response = self._generate_multi_persona_response(message, contexts, conversation)
        
        # Update conversation
        conversation.append({"role": "assistant", "content": response})
        self.conversation_cache[user_id] = conversation[-10:]  # Keep last 10 messages
        
        # Store in long-term memory
        self._store_conversation(user_id, conversation[-2:])
        
        return response
    
    def _get_multi_persona_context(self, user_id: str, query: str) -> dict:
        personas = ["finance", "health", "work", "identity"]
        contexts = {}
        
        for persona in personas:
            response = self.session.post(f"{self.memory_api}/v1/retrieve", json={
                "user_id": user_id,
                "query": query,
                "persona_context": {"forced_persona": persona},
                "granularity": "episodic",
                "include_narrative": True,
                "limit": 3
            })
            contexts[persona] = response.json()
        
        return contexts
    
    def _generate_multi_persona_response(self, message: str, contexts: dict, conversation: list) -> str:
        # Build comprehensive context
        context_parts = []
        for persona, context in contexts.items():
            memories = context.get("results", {}).get("memories", [])
            if memories:
                context_parts.append(f"\n{persona.title()} context:")
                for mem in memories:
                    context_parts.append(f"- {mem['content']}")
        
        # Build conversation history
        conversation_text = "\n".join([
            f"{msg['role']}: {msg['content']}" 
            for msg in conversation[-5:]  # Last 5 messages
        ])
        
        prompt = f"""
        Conversation history:
        {conversation_text}
        
        User's memories across personas:
        {chr(10).join(context_parts)}
        
        Current message: {message}
        
        Respond as a helpful assistant with access to the user's comprehensive memory context.
        """
        
        return self.llm.generate(prompt)
    
    def _store_conversation(self, user_id: str, messages: list):
        self.session.post(f"{self.memory_api}/v1/store", json={
            "user_id": user_id,
            "history": messages
        })
```

---

## **🎯 Persona-Aware Chatbots**

### **Financial Advisor Chatbot**
```python
class FinancialAdvisorChatbot:
    def __init__(self, llm_client, memory_api_url="http://localhost:8080"):
        self.llm = llm_client
        self.memory_api = memory_api_url
        self.session = requests.Session()
    
    def get_financial_advice(self, user_id: str, query: str) -> str:
        # Get financial context
        context = self.session.post(f"{self.memory_api}/v1/retrieve", json={
            "user_id": user_id,
            "query": query,
            "persona_context": {
                "forced_persona": "finance",
                "mood": "analytical"
            },
            "granularity": "episodic",
            "include_narrative": True,
            "explain": True,
            "limit": 10
        }).json()
        
        # Extract portfolio data
        portfolio_info = self._extract_portfolio_info(context)
        
        # Generate financial advice
        prompt = f"""
        User's financial history: {context.get('results', {}).get('narrative', '')}
        
        Portfolio information: {portfolio_info}
        
        User query: {query}
        
        Provide personalized financial advice based on their investment history and current portfolio.
        """
        
        return self.llm.generate(prompt)
    
    def _extract_portfolio_info(self, context: dict) -> str:
        memories = context.get("results", {}).get("memories", [])
        portfolio_items = []
        
        for memory in memories:
            metadata = memory.get("metadata", {})
            if "portfolio" in metadata:
                portfolio_items.append(f"- {memory['content']}")
        
        return "\n".join(portfolio_items)
```

### **Health Coach Chatbot**
```python
class HealthCoachChatbot:
    def __init__(self, llm_client, memory_api_url="http://localhost:8080"):
        self.llm = llm_client
        self.memory_api = memory_api_url
        self.session = requests.Session()
    
    def get_health_advice(self, user_id: str, query: str) -> str:
        # Get health context
        context = self.session.post(f"{self.memory_api}/v1/retrieve", json={
            "user_id": user_id,
            "query": query,
            "persona_context": {
                "forced_persona": "health",
                "mood": "motivated"
            },
            "granularity": "episodic",
            "include_narrative": True,
            "limit": 8
        }).json()
        
        # Extract emotional context
        emotional_context = self._extract_emotional_context(context)
        
        # Generate health advice
        prompt = f"""
        User's health journey: {context.get('results', {}).get('narrative', '')}
        
        Emotional context: {emotional_context}
        
        User query: {query}
        
        Provide personalized health and fitness advice based on their journey and current emotional state.
        """
        
        return self.llm.generate(prompt)
    
    def _extract_emotional_context(self, context: dict) -> str:
        memories = context.get("results", {}).get("memories", [])
        emotional_items = []
        
        for memory in memories:
            if memory.get("emotional_signature"):
                emotional_items.append(f"- {memory['content']} (emotion: {memory['emotional_signature']})")
        
        return "\n".join(emotional_items)
```

---

## **⚡ Streaming Memory Orchestrator**

The new adaptive orchestrator lets you stream chat events without manually
micromanaging storage or retrieval.  The orchestrator ingests every message,
automatically batches or compresses them based on volume, and pushes relevant
memories back to your runtime the moment they become useful.

### **Why use the orchestrator?**

- **Cost-aware ingestion:** message bursts are merged into batched transcripts so
  vector upserts stay affordable.
- **Stateful retrieval:** it tracks recent turns and suppresses duplicate memory
  injections, preventing the LLM from seeing stale context repeatedly.
- **Simple integration surface:** you stream `MessageEvent` instances and listen
  for `MemoryInjection` callbacks.

### **Quick start**

```python
from src.memory_orchestrator import AdaptiveMemoryOrchestrator, MessageEvent, MessageRole

orchestrator = AdaptiveMemoryOrchestrator()

async def on_memory(injection):
    # Push injected memory to your LLM context window
    await chatbot.push_memory(injection.content)

conversation_id = session.conversation_id
subscription = orchestrator.subscribe_injections(
    on_memory, conversation_id=conversation_id
)
try:
    for idx, turn in enumerate(conversation_stream()):
        event = MessageEvent(
            conversation_id=conversation_id,
            message_id=turn.get("id"),
            role=MessageRole(turn["role"]),
            content=turn["content"],
            metadata={"user_id": turn["user_id"]},
        )
        await orchestrator.stream_message(event)
finally:
    await orchestrator.shutdown()
    subscription.close()
```

Always scope the subscription with the active `conversation_id` so only memories
for that chat stream are delivered back to your runtime. This prevents
concurrent sessions from surfacing unrelated injections when multiple users are
connected simultaneously.

### **Batch ingestion from existing transcripts**

If you already rely on `TranscriptRequest` payloads, the
`ChatRuntimeBridge` converts them into streaming events for you:

```python
from src.schemas import Message, TranscriptRequest
from src.services.chat_runtime import ChatRuntimeBridge

history = [
    Message(role="user", content="How is my savings goal looking?"),
    Message(role="assistant", content="You're 60% of the way there."),
]

bridge = ChatRuntimeBridge()
injections = await bridge.run_with_injections(
    TranscriptRequest(user_id="user-123", history=history)
)
for injection in injections:
    print("retrieved memory", injection.memory_id, injection.content)
```

### **Tuning policies**

`AdaptiveMemoryOrchestrator` accepts `IngestionPolicy` and `RetrievalPolicy`
overrides if you need bespoke thresholds.  For example:

```python
from datetime import timedelta
from src.memory_orchestrator.policies import IngestionPolicy, RetrievalPolicy

orchestrator = AdaptiveMemoryOrchestrator(
    ingestion_policy=IngestionPolicy(
        low_volume_cutoff=4,
        high_volume_cutoff=12,
        medium_volume_batch_size=4,
        flush_interval=timedelta(seconds=15),
    ),
    retrieval_policy=RetrievalPolicy(min_similarity=0.65, max_injections_per_message=2),
)
```

These knobs let you trade off cost, latency, and context richness without
rewriting your chatbot logic.

### **Accessing the orchestrator over HTTP**

If you cannot host the orchestrator in-process, the API exposes three helper
endpoints:

- `POST /v1/orchestrator/message` streams a single chat turn and immediately
  returns any injected memories.
- `POST /v1/orchestrator/transcript` accepts the existing `TranscriptRequest`
  payload and returns every memory injection emitted while replaying that
  transcript through the orchestrator.
- `POST /v1/orchestrator/retrieve` fetches the top memories for a
  conversation/query pair without emitting a new streamed turn.

Example request for the streaming endpoint:

```bash
curl -X POST http://localhost:8080/v1/orchestrator/message \
  -H 'Content-Type: application/json' \
  -d '{
        "conversation_id": "chat-42",
        "role": "user",
        "content": "Any updates on my savings goal?",
        "metadata": {"user_id": "user-123"},
        "flush": true
      }'
```

To retrieve memories on demand, issue a separate call:

```bash
curl -X POST http://localhost:8080/v1/orchestrator/retrieve \
  -H 'Content-Type: application/json' \
  -d '{
        "conversation_id": "chat-42",
        "query": "budget status",
        "metadata": {"user_id": "user-123"},
        "limit": 5
      }'
```

The response contains a list of memory injections that mirror the
`MemoryInjection` dataclass exposed in the Python client:

```json
{
  "injections": [
    {
      "memory_id": "mem-abc123",
      "content": "You reached 60% of your savings goal last week.",
      "source": "long_term",
      "channel": "inline",
      "score": 0.91,
      "metadata": {
        "layer": "semantic",
        "conversation_id": "chat-42"
      }
    }
  ]
}
```

## **🚀 Advanced Features**

### **1. Memory Summarization**
```python
class SummarizedMemoryChatbot:
    def __init__(self, llm_client, memory_api_url="http://localhost:8080"):
        self.llm = llm_client
        self.memory_api = memory_api_url
        self.session = requests.Session()
    
    def get_summarized_context(self, user_id: str, query: str, granularity: str = "arc") -> str:
        """Get summarized context at different granularities"""
        response = self.session.post(f"{self.memory_api}/v1/retrieve", json={
            "user_id": user_id,
            "query": query,
            "granularity": granularity,  # "raw", "episodic", "arc"
            "include_narrative": True,
            "limit": 20
        })
        
        context = response.json()
        return context.get("results", {}).get("narrative", "")
    
    def chat_with_summary(self, user_id: str, message: str) -> str:
        # Get arc-level summary for broad context
        arc_context = self.get_summarized_context(user_id, message, "arc")
        
        # Get episodic details for specific context
        episodic_context = self.get_summarized_context(user_id, message, "episodic")
        
        prompt = f"""
        User's life story (arc): {arc_context}
        
        Recent activities (episodic): {episodic_context}
        
        Current message: {message}
        
        Respond with deep understanding of their journey and recent activities.
        """
        
        return self.llm.generate(prompt)
```

### **2. Explainable AI Integration**
```python
class ExplainableMemoryChatbot:
    def __init__(self, llm_client, memory_api_url="http://localhost:8080"):
        self.llm = llm_client
        self.memory_api = memory_api_url
        self.session = requests.Session()
    
    def chat_with_explanation(self, user_id: str, message: str) -> dict:
        """Get response with explanation of memory retrieval"""
        response = self.session.post(f"{self.memory_api}/v1/retrieve", json={
            "user_id": user_id,
            "query": message,
            "include_narrative": True,
            "explain": True,
            "limit": 5
        })
        
        context = response.json()
        
        # Generate response
        bot_response = self.llm.generate(f"""
        Context: {context.get('results', {}).get('narrative', '')}
        User message: {message}
        Respond helpfully.
        """)
        
        # Return response with explanation
        return {
            "response": bot_response,
            "explanation": {
                "persona": context.get("persona", {}),
                "weights": context.get("explainability", {}).get("weights", {}),
                "source_memories": context.get("explainability", {}).get("source_links", [])
            }
        }
```

### **3. Stateful Conversation Management**
```python
class StatefulMemoryChatbot:
    def __init__(self, llm_client, memory_api_url="http://localhost:8080"):
        self.llm = llm_client
        self.memory_api = memory_api_url
        self.session = requests.Session()
        self.user_states = {}
    
    def chat_with_state(self, user_id: str, message: str) -> str:
        # Get current state
        current_state = self.user_states.get(user_id, {})
        
        # Get memories with state context
        context = self.session.post(f"{self.memory_api}/v1/retrieve", json={
            "user_id": user_id,
            "query": message,
            "persona_context": {
                "active_personas": current_state.get("active_personas", []),
                "mood": current_state.get("mood", "neutral")
            },
            "include_narrative": True,
            "limit": 5
        }).json()
        
        # Update state based on response
        new_state = self._update_state(current_state, context, message)
        self.user_states[user_id] = new_state
        
        # Generate response
        response = self.llm.generate(f"""
        User's current state: {new_state}
        Context: {context.get('results', {}).get('narrative', '')}
        Message: {message}
        Respond appropriately.
        """)
        
        return response
    
    def _update_state(self, current_state: dict, context: dict, message: str) -> dict:
        # Update based on persona selection
        selected_persona = context.get("persona", {}).get("selected", "identity")
        
        # Update mood based on emotional content
        mood = self._detect_mood(message, context)
        
        return {
            "active_personas": [selected_persona],
            "mood": mood,
            "last_updated": datetime.now().isoformat()
        }
    
    def _detect_mood(self, message: str, context: dict) -> str:
        # Simple mood detection based on message content
        if any(word in message.lower() for word in ["happy", "excited", "great"]):
            return "positive"
        elif any(word in message.lower() for word in ["sad", "worried", "stressed"]):
            return "negative"
        return "neutral"
```

---

## **🏭 Production Deployment**

### **1. Docker Integration**
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy chatbot code
COPY chatbot/ ./chatbot/

# Environment variables
ENV MEMORY_API_URL=http://agentic-memories:8080
ENV LLM_API_KEY=your_llm_key

# Run chatbot
CMD ["python", "chatbot/main.py"]
```

### **2. Kubernetes Deployment**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: memory-chatbot
spec:
  replicas: 3
  selector:
    matchLabels:
      app: memory-chatbot
  template:
    metadata:
      labels:
        app: memory-chatbot
    spec:
      containers:
      - name: chatbot
        image: your-registry/memory-chatbot:latest
        env:
        - name: MEMORY_API_URL
          value: "http://agentic-memories-service:8080"
        - name: LLM_API_KEY
          valueFrom:
            secretKeyRef:
              name: llm-secrets
              key: api-key
        ports:
        - containerPort: 8000
---
apiVersion: v1
kind: Service
metadata:
  name: memory-chatbot-service
spec:
  selector:
    app: memory-chatbot
  ports:
  - port: 8000
    targetPort: 8000
  type: LoadBalancer
```

### **3. Monitoring and Logging**
```python
import logging
import time
from functools import wraps

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def monitor_performance(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(f"{func.__name__} completed in {duration:.2f}s")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} failed: {str(e)}")
            raise
    return wrapper

class MonitoredMemoryChatbot:
    def __init__(self, llm_client, memory_api_url="http://localhost:8080"):
        self.llm = llm_client
        self.memory_api = memory_api_url
        self.session = requests.Session()
    
    @monitor_performance
    def process_message(self, user_id: str, message: str) -> str:
        # Your chatbot logic here
        pass
```

---

## **🔧 Troubleshooting**

### **Common Issues and Solutions**

#### **1. Memory API Connection Issues**
```python
class RobustMemoryChatbot:
    def __init__(self, llm_client, memory_api_url="http://localhost:8080"):
        self.llm = llm_client
        self.memory_api = memory_api_url
        self.session = requests.Session()
        self.fallback_mode = False
    
    def _safe_api_call(self, method: str, url: str, **kwargs):
        """Make API call with fallback handling"""
        try:
            response = getattr(self.session, method)(url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.warning(f"API call failed: {e}, using fallback mode")
            self.fallback_mode = True
            return None
    
    def process_message(self, user_id: str, message: str) -> str:
        if not self.fallback_mode:
            # Try to get memories
            memories = self._safe_api_call(
                "post", f"{self.memory_api}/v1/retrieve",
                json={"user_id": user_id, "query": message, "limit": 5}
            )
            
            if memories:
                context = self._build_context(memories)
            else:
                context = "No memory context available"
        else:
            context = "Memory system unavailable"
        
        # Generate response
        prompt = f"""
        Context: {context}
        User message: {message}
        Respond helpfully.
        """
        
        return self.llm.generate(prompt)
```

#### **2. Memory Storage Failures**
```python
class ResilientMemoryChatbot:
    def __init__(self, llm_client, memory_api_url="http://localhost:8080"):
        self.llm = llm_client
        self.memory_api = memory_api_url
        self.session = requests.Session()
        self.local_cache = {}  # Fallback storage
    
    def _store_message_safe(self, user_id: str, content: str, role: str = "user"):
        """Store message with fallback to local cache"""
        try:
            response = self.session.post(f"{self.memory_api}/v1/store", json={
                "user_id": user_id,
                "history": [{"role": role, "content": content}]
            })
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            # Fallback to local cache
            if user_id not in self.local_cache:
                self.local_cache[user_id] = []
            self.local_cache[user_id].append({"role": role, "content": content})
            logger.warning(f"Stored message locally for user {user_id}")
            return False
    
    def _get_memories_safe(self, user_id: str, query: str):
        """Get memories with fallback to local cache"""
        try:
            response = self.session.get(f"{self.memory_api}/v1/retrieve", params={
                "user_id": user_id,
                "query": query,
                "limit": 5
            })
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            # Fallback to local cache
            local_memories = self.local_cache.get(user_id, [])
            return {"results": local_memories[-5:]}  # Last 5 messages
```

#### **3. Performance Optimization**
```python
import asyncio
import aiohttp
from typing import List, Dict

class AsyncMemoryChatbot:
    def __init__(self, llm_client, memory_api_url="http://localhost:8080"):
        self.llm = llm_client
        self.memory_api = memory_api_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
    
    async def process_message_async(self, user_id: str, message: str) -> str:
        """Process message asynchronously"""
        # Store and retrieve in parallel
        store_task = self._store_message_async(user_id, message)
        retrieve_task = self._get_memories_async(user_id, message)
        
        await store_task
        memories = await retrieve_task
        
        # Generate response
        context = self._build_context(memories)
        response = await self._generate_response_async(message, context)
        
        # Store response
        await self._store_message_async(user_id, response, role="assistant")
        
        return response
    
    async def _store_message_async(self, user_id: str, content: str, role: str = "user"):
        async with self.session.post(f"{self.memory_api}/v1/store", json={
            "user_id": user_id,
            "history": [{"role": role, "content": content}]
        }) as response:
            return await response.json()
    
    async def _get_memories_async(self, user_id: str, query: str):
        async with self.session.get(f"{self.memory_api}/v1/retrieve", params={
            "user_id": user_id,
            "query": query,
            "limit": 5
        }) as response:
            return await response.json()
    
    async def _generate_response_async(self, message: str, context: str) -> str:
        # Implement async LLM call
        return await self.llm.generate_async(f"Context: {context}\nMessage: {message}")
```

---

## **📊 Best Practices**

### **1. Memory Management**
- **Store conversations regularly** to build rich memory
- **Use appropriate granularity** (raw for details, episodic for events, arc for life story)
- **Implement memory cleanup** for old, irrelevant memories
- **Monitor memory usage** and implement limits

### **2. Persona Detection**
- **Train persona detection models** on your specific use cases
- **Use multiple signals** (keywords, context, user behavior)
- **Implement fallback personas** for edge cases
- **Allow manual persona override** for users

### **3. Performance Optimization**
- **Cache frequently accessed memories**
- **Use async operations** for better throughput
- **Implement connection pooling** for API calls
- **Monitor and optimize** response times

### **4. Error Handling**
- **Implement graceful degradation** when memory system is unavailable
- **Use local caching** as fallback
- **Log errors** for debugging and improvement
- **Provide user feedback** when systems are down

---

## **🎯 Conclusion**

This comprehensive guide provides everything you need to inject memories into your chatbots using Agentic Memories. The system offers:

- **Rich memory storage** with multi-tier summarization
- **Persona-aware retrieval** for contextually appropriate responses
- **Explainable AI** for transparency and debugging
- **Production-ready** deployment patterns
- **Robust error handling** and fallback mechanisms

Start with the basic integration and gradually add advanced features as your needs grow. The persona-aware retrieval system will significantly improve your chatbot's ability to provide personalized, contextually relevant responses! 🚀

---

## **📚 Additional Resources**

- **API Documentation**: `/docs` endpoint when running Agentic Memories
- **Example Implementations**: See the `examples/` directory
- **Performance Tuning**: Monitor logs and adjust parameters
- **Community Support**: Join our Discord for help and updates

**Happy Building!** 🎉
