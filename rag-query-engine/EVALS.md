# Eval Guide

The backend exposes `POST /eval` for deterministic release checks around retrieval and answer grounding.

## Example

```bash
curl -X POST http://localhost:8000/eval \
  -H "Content-Type: application/json" \
  -d '{
    "k": 5,
    "cases": [
      {
        "id": "deployment-risks",
        "query": "What production deployment risks should I monitor?",
        "answer_contains": ["deployment"],
        "min_documents": 1,
        "min_relevance": 0.2
      }
    ]
  }'
```

Each case checks:

- `answer_contains`: required terms in the generated answer.
- `min_documents`: minimum retrieved source count.
- `min_relevance`: minimum top source relevance.

Use this endpoint in CI or pre-release checks after indexing a known fixture corpus.
