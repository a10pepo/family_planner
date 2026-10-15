"""AWS Lambda adapter for the Family Planner Streamable HTTP MCP server."""

import os


def make_handler():
    os.environ.setdefault("STORAGE_BACKEND", "dynamodb")
    from mangum import Mangum

    from app.mcp_server import create_mcp_app

    return Mangum(create_mcp_app(), lifespan="off")


handler = make_handler()
