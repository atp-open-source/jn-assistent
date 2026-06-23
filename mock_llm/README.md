# mock_llm

Lille FastAPI-service, der emulerer Azure OpenAI chat completions-endpointet:

- `POST /openai/deployments/{deployment}/chat/completions`
- accepterer `api-version` query parameter og `api-key` header
- ignorerer begge felter
- returnerer et OpenAI-formet `chat.completion`-svar

Servicen returnerer altid en fenced `json`-blok med præcis nøglerne `oplysninger` og `status`. Det matcher valideringskaldet direkte, og genereringskaldet kan også tåle det, fordi `JNModelBusinessComponent.predict()` blot sender strengsvaret videre til næste LLM-kald.

## Kør lokalt

```bash
pip install -r mock_llm/requirements.txt
python -m mock_llm
```

## Curl-eksempel

```bash
curl -X POST 'http://127.0.0.1:8000/openai/deployments/gpt-4o/chat/completions?api-version=2024-10-21' \
  -H 'content-type: application/json' \
  -H 'api-key: ignored' \
  -d '{
    "messages": [
      {"role": "system", "content": "Skriv et journalnotat"},
      {"role": "user", "content": "Borger ringer om status på sin sag"}
    ],
    "model": "gpt-4o"
  }'
```

## Docker

```bash
docker build -t mock-llm -f mock_llm/Dockerfile .
docker run --rm -p 8000:8000 mock-llm
```
