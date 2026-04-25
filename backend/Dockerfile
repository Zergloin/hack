FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    libcairo2 libffi-dev libgdk-pixbuf-2.0-0 libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
    shared-mime-info fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
