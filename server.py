from fastmcp import FastMCP
import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from typing import AsyncIterator
from utils.mongodb_singleton import get_mongodb_client
import logging

load_dotenv()

@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:
    # Initialize MongoDB singleton
    mongo_client = get_mongodb_client()
    logging.info("✅ MongoDB singleton initialized in lifespan")
    
    try:
        yield
    finally:
        # Close MongoDB connection on shutdown
        logging.info("🔧 Shutting down lifespan, closing MongoDB...")
        mongo_client.close()
        logging.info("✅ Lifespan cleanup complete")

mcp = FastMCP(
    name="BA Server",
    lifespan=lifespan,
    instructions="This is a Business Analyst server for managing project requirements and creating BRD document from those requirements."
)
