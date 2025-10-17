#!/usr/bin/env python3
"""
HTTP Server runner for GPT Mission Planner

This script starts the FastAPI HTTP server that provides the same API
interface as the original mpui server but with the powerful mission
planning capabilities from gpt-mission-planner.
"""

import os
import sys
import logging
from pathlib import Path

# Add app directory to Python path
app_dir = Path(__file__).parent
sys.path.insert(0, str(app_dir))

def main():
    """Run the HTTP server."""
    import uvicorn
    from http_server import app

    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Get configuration from environment or use defaults
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 9001))

    logger.info(f"Starting GPT Mission Planner HTTP Server on {host}:{port}")
    logger.info("API Documentation available at: http://{}:{}/docs".format(host, port))

    # Run the server
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=False,  # Set to True for development
        access_log=True,
        log_level="info"
    )

if __name__ == "__main__":
    main()