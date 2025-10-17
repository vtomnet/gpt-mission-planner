import asyncio
import logging
import os
import tempfile
import time
from typing import Dict, Any, Optional
import yaml

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai

from mission_planner import MissionPlanner
from gpt_interface import LLMInterface
from network_interface import NetworkInterface
from utils.gps_utils import TreePlacementGenerator
from utils.xml_utils import parse_code, validate_output, parse_schema_location
from utils.os_utils import write_out_file

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Silence some noisy loggers
logging.getLogger("openai").setLevel(logging.CRITICAL)
logging.getLogger("anthropic").setLevel(logging.CRITICAL)
logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)
logging.getLogger("httpx").setLevel(logging.CRITICAL)
logging.getLogger("httpcore").setLevel(logging.CRITICAL)

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
config_data: Dict[str, Any] = {}
mission_planner: Optional[MissionPlanner] = None

class TextRequest(BaseModel):
    text: str
    schemaName: str
    geojsonName: Optional[str] = None
    model: str
    lon: Optional[float] = None
    lat: Optional[float] = None
    sendToRobot: Optional[bool] = True

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
        logger.info(f"Farm polygon points: {tpg.polygon_coords}")
        logger.info(f"Farm dimensions: {tpg.dimensions}")
    else:
        logger.warning("No farm polygon found. Proceeding without orchard grid...")

    # Setup LTL verification flags
    ltl = config_data.get("ltl", False)
    pml_template_path = config_data.get("promela_template", "")
    spin_path = config_data.get("spin_path", "")

    if ltl and not (pml_template_path and spin_path):
        ltl = False
        logger.warning("No spin configuration found. Proceeding without formal verification...")

    # Initialize mission planner
    mission_planner = MissionPlanner(
        token_path=config_data["token"],
        schema_paths=config_data["schema"],
        context_files=context_files,
        tpg=tpg,
        max_retries=config_data["max_retries"],
        max_tokens=config_data["max_tokens"],
        temperature=config_data["temperature"],
        ltl=ltl,
        promela_template_path=pml_template_path,
        spin_path=spin_path,
        log_directory=config_data["log_directory"],
        logger=logger,
    )

    logger.info("Mission planner initialized successfully")

def map_schema_name(schema_name: str) -> str:
    """Map frontend schema names to actual schema files."""
    schema_mapping = {
        "bd_spot": "amiga_btcpp.xsd",
        "clearpath_husky": "clearpath_husky.xsd",
        "kinova_gen3_6dof": "kinova_gen3_6dof.xsd",
        "gazebo_minimal": "gazebo_minimal.xsd"
    }
    return schema_mapping.get(schema_name, schema_name + ".xsd")

async def generate_mission_xml(prompt: str, schema_name: str, send_to_robot: bool = True) -> tuple[bool, str]:
    """Generate and validate XML mission using the mission planner."""
    if not mission_planner:
        raise HTTPException(status_code=500, detail="Mission planner not initialized")

    try:
        # Reset mission planner state
        mission_planner.reset()

        # Generate XML mission
        success, xml_output, task_count = mission_planner._generate_xml(prompt, count=True)

        if not success:
            logger.error(f"XML generation failed: {xml_output}")
            return False, f"Failed to generate valid XML: {xml_output}"

        logger.info(f"Successfully generated XML mission with {task_count} tasks")

        # Handle tree placement if available
        if mission_planner.tpg is not None:
            # Write XML to temporary file first
            temp_xml_file = write_out_file(config_data["log_directory"], xml_output)

            # Replace tree IDs with GPS coordinates
            final_xml_file = mission_planner.tpg.replace_tree_ids_with_gps(temp_xml_file)

            # Read the updated XML content
            with open(final_xml_file, "r") as f:
                xml_output = f.read()

            # Validate the final XML
            ret, err = mission_planner._lint_xml(xml_output)
            if not ret:
                logger.error(f"Failed to lint XML after replacing tree IDs: {err}")
                return False, f"XML validation failed after tree ID replacement: {err}"

            logger.info("Replaced tree IDs with GPS coordinates")
        else:
            # Write XML to file for sending to robot
            final_xml_file = write_out_file(config_data["log_directory"], xml_output)

        # Send to robot if requested
        if send_to_robot:
            try:
                # Initialize network interface
                nic = NetworkInterface(logger, config_data["host"], config_data["port"])
                nic.init_socket()

                # Send XML file to robot
                nic.send_file(final_xml_file)
                logger.info(f"Sent mission XML {final_xml_file} to robot at {config_data['host']}:{config_data['port']}")

                # Close network connection
                nic.close_socket()

            except ConnectionRefusedError:
                logger.warning(f"Could not connect to robot at {config_data['host']}:{config_data['port']}. Robot may not be running.")
            except Exception as e:
                logger.error(f"Error sending XML to robot: {e}")

        return True, xml_output

    except Exception as e:
        logger.error(f"Error generating XML mission: {e}")
        return False, str(e)

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    try:
        await load_config()
        logger.info("HTTP server startup complete")
    except Exception as e:
        logger.error(f"Failed to initialize server: {e}")
        raise

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "GPT Mission Planner HTTP Server is running"}

@app.get("/api/models")
async def get_models():
    """Get available models."""
    # Return compatible model list for frontend
    models = [
        "gpt-5/high", "gpt-5/medium", "gpt-5/low", "gpt-5/minimal",
        "gpt-5-mini/high", "gpt-5-mini/medium", "gpt-5-mini/low", "gpt-5-mini/minimal"
    ]
    return {"models": models}

@app.get("/api/schemas")
async def get_schemas():
    """Get available schemas."""
    schemas = ["bd_spot", "clearpath_husky", "kinova_gen3_6dof", "gazebo_minimal"]
    return {"schemas": schemas}

@app.get("/api/geojson")
async def get_geojson():
    """Get available geojson files."""
    geojson_files = ["reza", "ucm_graph40", "test", "none"]
    return {"geojson": geojson_files}

@app.post("/api/text", response_model=MissionResponse)
async def generate_text_mission(request: TextRequest):
    """Generate mission from text input."""
    try:
        # Validate inputs
        allowed_schemas = ["bd_spot", "clearpath_husky", "kinova_gen3_6dof", "gazebo_minimal"]
        if request.schemaName not in allowed_schemas:
            raise HTTPException(status_code=422, detail=f"Unrecognized schema: {request.schemaName}")

        allowed_models = [
            "gpt-5/high", "gpt-5/medium", "gpt-5/low", "gpt-5/minimal",
            "gpt-5-mini/high", "gpt-5-mini/medium", "gpt-5-mini/low", "gpt-5-mini/minimal"
        ]
        if request.model not in allowed_models:
            raise HTTPException(status_code=422, detail=f"Unrecognized model: {request.model}")

        # Generate mission
        success, result = await generate_mission_xml(request.text, request.schemaName, request.sendToRobot)

        if not success:
            raise HTTPException(status_code=500, detail=result)

        # Log the request
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

        # Write to log file
        os.makedirs("logs", exist_ok=True)
        with open("logs/requests.log", "a") as f:
            f.write(str(log_entry) + "\n")

        return MissionResponse(result=result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in text mission generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/voice")
async def generate_voice_mission(
    file: UploadFile = File(...),
    schemaName: str = Form(...),
    model: str = Form(...),
    lon: Optional[float] = Form(None),
    lat: Optional[float] = Form(None),
    sendToRobot: Optional[bool] = Form(True)
):
    """Generate mission from voice input with streaming response."""

    async def generate_response():
        try:
            # Validate inputs
            allowed_schemas = ["bd_spot", "clearpath_husky", "kinova_gen3_6dof", "gazebo_minimal"]
            if schemaName not in allowed_schemas:
                yield f'{{"error": "Unrecognized schema: {schemaName}"}}\n'
                return

            allowed_models = [
                "gpt-5/high", "gpt-5/medium", "gpt-5/low", "gpt-5/minimal",
                "gpt-5-mini/high", "gpt-5-mini/medium", "gpt-5-mini/low", "gpt-5-mini/minimal"
            ]
            if model not in allowed_models:
                yield f'{{"error": "Unrecognized model: {model}"}}\n'
                return

            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_file_path = temp_file.name

            try:
                # Initialize OpenAI client
                client = openai.OpenAI()

                # Transcribe audio
                with open(temp_file_path, "rb") as audio_file:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        prompt="The user is a farmer speaking instructions for an ag-tech robot."
                    )

                logger.info(f"Transcript: {transcript.text}")

                # Send STT result immediately
                yield f'{{"stt": "{transcript.text}"}}\n'

                # Generate mission XML
                success, result = await generate_mission_xml(transcript.text, schemaName, sendToRobot)

                if not success:
                    yield f'{{"error": "{result}"}}\n'
                    return

                # Log the request
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
                    "audioFile": f"voice_{int(time.time())}.webm"
                }

                # Write to log file
                os.makedirs("logs", exist_ok=True)
                with open("logs/requests.log", "a") as f:
                    f.write(str(log_entry) + "\n")

                logger.info(f"Generated mission: {result[:100]}...")
                yield f'{{"result": "{result.replace(chr(10), chr(92) + chr(110)).replace(chr(34), chr(92) + chr(34))}"}}\n'

            finally:
                # Clean up temp file
                os.unlink(temp_file_path)

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

if __name__ == "__main__":
    import uvicorn

    # Default configuration
    port = int(os.getenv("PORT", 9001))
    host = os.getenv("HOST", "127.0.0.1")

    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)