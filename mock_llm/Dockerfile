FROM python:3.12-slim

WORKDIR /app

COPY mock_llm/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY mock_llm ./mock_llm

EXPOSE 8000

CMD ["uvicorn", "mock_llm.app:app", "--host", "0.0.0.0", "--port", "8000"]
