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
- citation validity: a case fails if the answer cites a source that was never
  supplied to the model.

## Retrieval metrics

A case may declare `relevant_chunk_ids`, the ground-truth chunks it should
retrieve. When at least one case does, the response carries aggregate
`retrieval_metrics`: hit rate, recall, precision, nDCG at K, MRR, duplicate
rate, and empty-result rate. Cases without ground truth are graded but excluded
from the metrics.

```json
{
  "id": "hybrid-retrieval-described",
  "query": "How are dense and lexical search results combined?",
  "answer_contains": ["fusion"],
  "relevant_chunk_ids": ["retrieval-hybrid"]
}
```

Use this endpoint in CI or pre-release checks after indexing a known fixture corpus.

Checked-in smoke fixtures live in `evals/fixture_corpus.json` and
`evals/eval_cases.json`. The prompt-injection fixtures (`prompt-injection-fixture`
and `prompt-injection-exfiltration`) contain text that attempts to override the
system prompt and exfiltrate data; they must be treated as untrusted source
content, never as instructions. `insufficient-evidence-control` exists so the
suite can verify the model refuses rather than inventing an answer.
