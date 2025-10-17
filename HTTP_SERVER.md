# GPT Mission Planner HTTP Server

This HTTP server provides a REST API interface to the powerful GPT Mission Planner system, making it compatible with the MPUI frontend while leveraging all the advanced features of the mission planning system.

## Features

- **Advanced Mission Planning**: Full XML mission generation with schema validation
- **Multi-LLM Support**: OpenAI, Anthropic, and Gemini models via LiteLLM
- **Formal Verification**: Optional LTL and SPIN model checking
- **Agricultural Robotics**: Specialized context for precision agriculture
- **Voice Input**: Speech-to-text transcription and mission generation
- **Comprehensive Validation**: XML schema validation, syntax checking
- **FastAPI**: Modern async web framework with automatic OpenAPI documentation

## Quick Start

### 1. Install Dependencies

```bash
cd gpt-mission-planner
uv pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root with your API keys:

```bash
# OpenAI
OPENAI_API_KEY=your_openai_key_here

# Anthropic
ANTHROPIC_API_KEY=your_anthropic_key_here

# Optional: Gemini
GEMINI_API_KEY=your_gemini_key_here
```

### 3. Run the Server

```bash
# Using make
make run-http

# Or directly
python3 app/run_server.py
```

The server will start on `http://127.0.0.1:9001`

## API Endpoints

### GET /
Health check endpoint

### GET /docs
Interactive API documentation (Swagger UI)

### POST /api/text
Generate mission from text input

**Request Body:**
```json
{
    "text": "Move to tree 5 and take thermal sensor reading",
    "schemaName": "bd_spot",
    "geojsonName": "none",
    "model": "gpt-5/high",
    "lon": -120.420,
    "lat": 37.266
}
```

**Response:**
```json
{
    "result": "<xml mission plan>"
}
```

### POST /api/voice
Generate mission from voice input (streaming response)

**Request:** multipart/form-data with audio file and parameters

**Response:** NDJSON stream with STT results and final mission

## Configuration

The server uses `app/config/http_server.yaml` for configuration. Key settings:

- **schema**: List of XSD schema files
- **context_files**: Additional context for mission planning
- **farm_polygon**: GPS coordinates for agricultural operations
- **max_retries**: Maximum LLM retry attempts
- **temperature**: LLM sampling temperature
- **ltl**: Enable formal verification (requires SPIN)

## Integration with MPUI

This server is designed to be a drop-in replacement for the original MPUI server. Update your MPUI configuration to point to this server:

```json
{
    "apiEndpoint": "http://127.0.0.1:9001/api"
}
```

## Development

For development, you can enable reload mode:

```python
uvicorn app.http_server:app --reload --host 127.0.0.1 --port 9001
```

API documentation is automatically available at `/docs` when the server is running.