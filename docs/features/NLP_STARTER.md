# NLP Query Interface — v1.1.0 Starter

## File Structure
```
backend/app/nlp/
├── __init__.py
├── engine.py          # NLP engine
├── query_builder.py   # SQL generator
├── api.py             # FastAPI endpoints
└── tests/
    └── test_nlp.py
```

## Quick Start

### 1. Install Dependencies
```bash
cd backend
source venv/bin/activate
pip install openai sqlalchemy
```

### 2. Create Engine
```python
# backend/app/nlp/engine.py
import openai
from typing import Dict, Any
import os

class NLPEngine:
    def __init__(self, model='gpt-4'):
        self.model = model
        openai.api_key = os.getenv('OPENAI_API_KEY')

    def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process natural language query."""

        # Build prompt with schema context
        prompt = f"""
You are an ERP assistant. Convert this query to SQL:
User query: {query}
Available tables: products, orders, customers, inventory, sales
Context: {context}

Respond with JSON:
{{
    "query_type": "analytics|lookup|action",
    "sql": "SELECT ...",
    "visualization": "table|chart|summary",
    "summary": "human readable summary"
}}
"""

        response = openai.ChatCompletion.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse response
        import json
        result = json.loads(response.choices[0].message.content)

        return result
```

### 3. Create API Endpoint
```python
# backend/app/nlp/api.py
from fastapi import APIRouter
from .engine import NLPEngine

router = APIRouter(prefix="/api/v1/nlp", tags=["nlp"])
engine = NLPEngine()

@router.post("/query")
def nlp_query(query: str, language: str = "en"):
    """Process natural language query."""
    result = engine.process(query, {"language": language})
    return result

@router.post("/chat")
def chat_message(message: str, session_id: str = "default"):
    """Interactive chat."""
    return {
        "response": "I understand you're asking about: " + message,
        "suggested_queries": [
            "Show sales report",
            "Check inventory levels",
            "Predict demand for next week"
        ]
    }
```

## Testing
```bash
cd backend
pytest app/nlp/tests/ -v
```

## Next Steps
1. Implement schema introspection for dynamic SQL generation
2. Add conversation memory for chat sessions
3. Implement fallback to local LLM (Ollama) when offline
4. Add voice input support
