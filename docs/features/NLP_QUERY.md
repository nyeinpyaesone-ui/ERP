# Natural Language Query Interface

## Overview
Ask questions about your ERP data in plain English.

## Features
- Natural language to SQL conversion
- Voice input support
- Multi-language queries (English, Myanmar, Thai)
- Context-aware responses
- Data visualization suggestions

## API Endpoints

### POST /api/v1/nlp/query
Process a natural language query.

**Request:**
```json
{
  "query": "Show me top 10 selling products last month",
  "language": "en",
  "context": {"user_id": "123", "tenant_id": "t-001"}
}
```

**Response:**
```json
{
  "query_type": "analytics",
  "sql": "SELECT product_name, SUM(quantity) as total_sold...",
  "results": [...],
  "visualization": "bar_chart",
  "summary": "Product A sold 500 units, Product B sold 450 units..."
}
```

### POST /api/v1/nlp/chat
Interactive chat session.

**Request:**
```json
{
  "message": "What's our inventory turnover rate?",
  "session_id": "sess-123"
}
```

### GET /api/v1/nlp/suggestions
Get query suggestions based on user role.

## Supported Queries
- "Show sales report for Q2"
- "Which products are low stock?"
- "Compare revenue this month vs last month"
- "Predict demand for product X next week"
- "Who are our top customers?"

## Implementation
```python
from app.nlp import NLPEngine

engine = NLPEngine()
result = engine.process("Show me top selling products")
# Returns SQL, results, and visualization type
```

## Models
- OpenAI GPT-4 for query understanding
- Local LLM (Ollama) for offline mode
- Custom fine-tuned model for ERP domain
