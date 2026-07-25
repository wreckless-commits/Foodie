# Foodie – Semantic Recipe Search

A full-stack recipe search app with multiple search backends (keyword, semantic via sqlite-vec, pgvector, FAISS) and a Streamlit UI orchestrated by .NET Aspire.

## Prerequisites

- Python 3.14+ with [uv](https://docs.astral.sh/uv/)
- .NET 10 SDK
- Docker Desktop
- [Ollama](https://ollama.ai/) running locally with `nomic-embed-text`:
  ```bash
  ollama pull nomic-embed-text
  ```

## Setup

### 1. Python dependencies

```bash
uv sync
```

### 2. Download the dataset and vectorize

The app uses the [corbt/all-recipes](https://huggingface.co/datasets/corbt/all-recipes) dataset from Hugging Face (~2.1M recipes).

**Download and ingest into SQLite:**

```bash
uv run python Data/main.py
```

**Vectorize with Ollama (creates embeddings for semantic search):**

> ⚠️ Vectorizing all 2.1M recipes takes **a very long time** (hours). Start with a small limit to verify everything works, then increase as needed.

```bash
# Quick test – first 100 recipes
uv run python Data/vectorize.py --limit 100

# Full dataset (prepare to wait)
uv run python Data/vectorize.py
```

(Optional) Quantize binary vectors and/or migrate to PostgreSQL:

```bash
uv run python Data/quantize_bit.py
uv run python Data/migrate_to_postgres.py
```

### 3. Set up Aspire

The `Foodie/` Aspire AppHost orchestrates PostgreSQL (pgvector), the .NET API, and the Streamlit UI.

Create the development settings file with the database password:

```bash
# Foodie/appsettings.Development.json is gitignored.
# Create it with:
echo '{
  "ConnectionStrings": {
    "DB_PASSWORD": "FOODI5Ev3ything"
  }
}' > Foodie/appsettings.Development.json
```

### 4. Run

Launch the full stack with Aspire:

```bash
dotnet run --project Foodie
```

This starts:
- **PostgreSQL** (pgvector) in Docker on port 5430
- **Foodie.Api** on `https://localhost:7184`
- **Streamlit UI** on port 8000
- **Aspire Dashboard** for logs, traces, and metrics

Open `http://localhost:8000` in your browser.
