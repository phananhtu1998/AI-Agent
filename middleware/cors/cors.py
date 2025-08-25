from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

def configure_cors(app: FastAPI):
    """
    Configure CORS middleware for the FastAPI application
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allows all origins
        # allow_origins=["http://localhost:3000"],  # Allows all origins
        allow_credentials=True,
        allow_methods=["*"],  # Allows all methods
        allow_headers=["*"],  # Allows all headers
    )
