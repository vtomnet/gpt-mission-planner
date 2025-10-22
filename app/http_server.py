import logging
import os
import tempfile
import time
import yaml
import shutil
import openai
import uvicorn
import ipdb as pdb
from pydub import AudioSegment

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from mission_planner import MissionPlanner
from utils.gps_utils import TreePlacementGenerator
from utils.os_utils import write_out_file

KNOWN_MODELS = [
    "gpt-5/high", "gpt-5/medium", "gpt-5/low", "gpt-5/minimal",
    "gpt-5-mini/high", "gpt-5-mini/medium", "gpt-5-mini/low", "gpt-5-mini/minimal"
]

KNOWN_SCHEMAS = [
    "bd_spot",
    "clearpath_husky",
    "kinova_gen3_6dof",
    "gazebo_minimal"
]

KNOWN_GEOJSON = [
    "reza", "ucm_graph40", "test", "none"
]

def rewrite_model(input_model: str) -> str:
    name, effort = input_model.split('/')
    # FIXME effort is unused
    output_model = "openai/" + name
    return output_model

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="GPT Mission Planner HTTP Server", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for mission planner configuration
config_data = {}
mission_planner: MissionPlanner | None = None

class TextRequest(BaseModel):
    text: str
    schemaName: str
    geojsonName: str | None = None
    model: str
    lon: float | None = None
    lat: float | None = None

class MissionResponse(BaseModel):
    result: str

class ErrorResponse(BaseModel):
    error: str

async def load_config(config_path: str = "./app/config/http_server.yaml"):
    """Load configuration from YAML file."""
    global config_data, mission_planner

    with open(config_path, "r") as file:
        config_data = yaml.safe_load(file)

    # Setup context files
    context_files = config_data.get("context_files", [])

    # Setup tree placement generator if farm polygon is defined
    tpg = None
    if "farm_polygon" in config_data:
        tpg = TreePlacementGenerator(
            config_data["farm_polygon"]["points"],
            config_data["farm_polygon"]["dimensions"],
        )

    # Initialize mission planner
    mission_planner = MissionPlanner(
        token_path=config_data["token"],
        schema_paths=config_data["schema"],
        context_files=context_files,
        tpg=tpg,
        max_retries=config_data["max_retries"],
    )

def map_schema_name(schema_name: str) -> str:
    """Map frontend schema names to actual schema files."""
    schema_mapping = {
        "bd_spot": "amiga_btcpp.xsd",
        "clearpath_husky": "clearpath_husky.xsd",
        "kinova_gen3_6dof": "kinova_gen3_6dof.xsd",
        "gazebo_minimal": "gazebo_minimal.xsd"
    }
    return schema_mapping.get(schema_name, schema_name + ".xsd")

async def generate_mission_xml(prompt: str, model: str) -> str:
    """Generate and validate XML mission using the mission planner."""
    if not mission_planner:
        raise Exception("Mission planner not initialized")

    # model = rewrite_model(model)
    model = "anthropic/claude-sonnet-4-5-20250929"
    mission_planner.reset()
    xml_output, _ = mission_planner._generate_xml(prompt, model)
    mission_planner._lint_xml(xml_output)
    xml_output = mission_planner.tpg.replace_tree_ids_with_gps(xml_output)
    return xml_output

@app.on_event("startup")
async def startup_event():
    os.makedirs("logs/audio", exist_ok=True)
    await load_config()
    logger.info("HTTP server startup complete")

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "GPT Mission Planner HTTP Server is running"}

@app.get("/api/models")
async def get_models():
    return {"models": KNOWN_MODELS}

@app.get("/api/schemas")
async def get_schemas():
    return {"schemas": KNOWN_SCHEMAS}

@app.get("/api/geojson")
async def get_geojson():
    return {"geojson": KNOWN_GEOJSON}

@app.post("/api/text", response_model=MissionResponse)
async def generate_text_mission(request: TextRequest):
    """Generate mission from text input."""
    try:
        if request.schemaName not in KNOWN_SCHEMAS:
            raise HTTPException(status_code=422, detail=f"Unrecognized schema: {request.schemaName}")

        if request.model not in KNOWN_MODELS:
            raise HTTPException(status_code=422, detail=f"Unrecognized model: {request.model}")

        result = await generate_mission_xml(request.text, request.model)

        log_entry = {
            "timestamp": time.time(),
            "type": "text",
            "request": {
                "text": request.text,
                "schemaName": request.schemaName,
                "geojsonName": request.geojsonName,
                "model": request.model,
                "lon": request.lon,
                "lat": request.lat
            },
            "response": result
        }

        os.makedirs("logs", exist_ok=True)
        with open("logs/requests.log", "a") as f:
            f.write(str(log_entry) + "\n")

        return MissionResponse(result=result)

    except Exception as e:
        logger.error(f"Error in text mission generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/voice")
async def generate_voice_mission(
    file: UploadFile = File(...),
    schemaName: str = Form(...),
    model: str = Form(...),
    lon: float | None = Form(None),
    lat: float | None = Form(None),
):
    async def generate_response():
        try:
            if schemaName not in KNOWN_SCHEMAS:
                yield f'{{"error": "Unrecognized schema: {schemaName}"}}\n'
                return

            if model not in KNOWN_MODELS:
                yield f'{{"error": "Unrecognized model: {model}"}}\n'
                return

            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_file_path = temp_file.name

            try:
                # Convert audio to WAV format
                audio = AudioSegment.from_file(temp_file_path)
                wav_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                audio.export(wav_temp_file.name, format="wav")
                wav_file_path = wav_temp_file.name
                wav_temp_file.close()

                logged_audio_filename = f"{int(time.time())}_{os.path.basename(temp_file_path)}"
                permanent_audio_path = os.path.join("logs", "audio", logged_audio_filename)

                shutil.copy2(temp_file_path, permanent_audio_path)
                logger.info(f"Saved audio file: {permanent_audio_path}")

                client = openai.OpenAI()

                with open(wav_file_path, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="gpt-4o-mini-transcribe",
                        file=audio_file,
                        prompt="The user is a farmer speaking instructions for an ag-tech robot."
                    )

                logger.info(f"Transcript: {transcript.text}")

                yield f'{{"stt": "{transcript.text}"}}\n'

                result = await generate_mission_xml(transcript.text, model)

                log_entry = {
                    "timestamp": time.time(),
                    "type": "voice",
                    "request": {
                        "text": transcript.text,
                        "schemaName": schemaName,
                        "model": model,
                        "lon": lon,
                        "lat": lat
                    },
                    "response": result,
                    "audioFile": logged_audio_filename
                }

                os.makedirs("logs", exist_ok=True)
                with open("logs/requests.log", "a") as f:
                    f.write(f"{str(log_entry)}\n")

                logger.info(f"Generated mission: {result[:100]}...")
                yield f'{{"result": "{result.replace(chr(10), chr(92) + chr(110)).replace(chr(34), chr(92) + chr(34))}"}}\n'

            finally:
                os.unlink(temp_file_path)
                if 'wav_file_path' in locals():
                    os.unlink(wav_file_path)

        except Exception as e:
            logger.error(f"Error in voice mission generation: {e}")
            yield f'{{"error": "{str(e)}"}}\n'

    return StreamingResponse(
        generate_response(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )

def main():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8002))

    logger.info(f"Starting GPT Mission Planner HTTP Server on {host}:{port}")

    # TODO: maybe prefer 'uv run uvicorn' over calling it in python?
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=False,
        access_log=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()
