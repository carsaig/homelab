"""
Traefik MCP Server

A Model Context Protocol server for managing Traefik reverse proxy instances.
"""
import asyncio
import logging
import os
from typing import Any, List

from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio

from .traefik.api_client import TraefikClient, TraefikError
from .tools.query_tools import QueryTools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize server
server = Server("traefik-mcp")

# Global variables for client and tools
traefik_client: TraefikClient = None
query_tools: QueryTools = None


async def initialize_client():
    """Initialize Traefik client from environment variables with fallback support."""
    global traefik_client, query_tools
    
    api_url = os.getenv('TRAEFIK_API_URL') or 'http://traefik:8080'
    api_key = os.getenv('TRAEFIK_API_KEY')
    basic_auth_username = os.getenv('TRAEFIK_BASIC_AUTH_USERNAME')
    basic_auth_password = os.getenv('TRAEFIK_BASIC_AUTH_PASSWORD')
    timeout = float(os.getenv('MCP_TIMEOUT', '30.0'))
    
    def create_client(target_url: str) -> TraefikClient:
        if api_key:
            return TraefikClient(api_url=target_url, api_key=api_key, timeout=timeout)
        elif basic_auth_username and basic_auth_password:
            return TraefikClient(
                api_url=target_url, 
                basic_auth_username=basic_auth_username,
                basic_auth_password=basic_auth_password,
                timeout=timeout
            )
        else:
            return TraefikClient(api_url=target_url, timeout=timeout)

    logger.info(f"Initializing Traefik client for {api_url}")
    traefik_client = create_client(api_url)
    
    if await traefik_client.health_check():
        logger.info(f"Successfully connected to Traefik API at {api_url}")
    else:
        logger.warning(f"Failed to connect to Traefik API at {api_url}")
        fallbacks = ['http://traefik:8080', 'http://traefik']
        connected = False
        for fallback in fallbacks:
            if fallback != api_url:
                logger.info(f"Attempting fallback to {fallback}")
                candidate = create_client(fallback)
                if await candidate.health_check():
                    logger.info(f"Successfully connected to Traefik API via fallback {fallback}")
                    traefik_client = candidate
                    connected = True
                    break
        if not connected:
            logger.warning("All Traefik connection attempts failed - server will start but tools may fail")
    
    query_tools = QueryTools(traefik_client)


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available tools."""
    return [
        Tool(
            name="get_traefik_overview",
            description="Get an overview of the Traefik instance configuration",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="list_routers",
            description="List all HTTP routers in Traefik",
            inputSchema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "description": "Optional provider name to filter by"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_router_details",
            description="Get detailed configuration for a specific router",
            inputSchema={
                "type": "object",
                "properties": {
                    "router_name": {
                        "type": "string",
                        "description": "Name of the router"
                    },
                    "provider": {
                        "type": "string",
                        "description": "Optional provider name"
                    }
                },
                "required": ["router_name"]
            }
        ),
        Tool(
            name="list_services",
            description="List all HTTP services in Traefik",
            inputSchema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "description": "Optional provider name to filter by"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_service_details",
            description="Get detailed configuration for a specific service",
            inputSchema={
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Name of the service"
                    },
                    "provider": {
                        "type": "string",
                        "description": "Optional provider name"
                    }
                },
                "required": ["service_name"]
            }
        ),
        Tool(
            name="list_middlewares",
            description="List all HTTP middlewares in Traefik",
            inputSchema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "description": "Optional provider name to filter by"
                    }
                },
                "required": []
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    """Handle tool calls."""
    if not query_tools:
        return [TextContent(
            type="text",
            text="Traefik client not initialized. Please check your configuration."
        )]
    
    try:
        if name == "get_traefik_overview":
            return await query_tools.get_overview()
        
        elif name == "list_routers":
            provider = arguments.get('provider') if arguments else None
            return await query_tools.list_routers(provider)
        
        elif name == "get_router_details":
            router_name = arguments.get('router_name') if arguments else None
            provider = arguments.get('provider') if arguments else None
            if not router_name:
                return [TextContent(type="text", text="Error: router_name is required")]
            return await query_tools.get_router_details(router_name, provider)
        
        elif name == "list_services":
            provider = arguments.get('provider') if arguments else None
            return await query_tools.list_services(provider)
        
        elif name == "get_service_details":
            service_name = arguments.get('service_name') if arguments else None
            provider = arguments.get('provider') if arguments else None
            if not service_name:
                return [TextContent(type="text", text="Error: service_name is required")]
            return await query_tools.get_service_details(service_name, provider)
        
        elif name == "list_middlewares":
            provider = arguments.get('provider') if arguments else None
            return await query_tools.list_middlewares(provider)
        
        else:
            return [TextContent(
                type="text",
                text=f"Unknown tool: {name}"
            )]
    
    except Exception as e:
        logger.error(f"Error executing tool {name}: {str(e)}")
        return [TextContent(
            type="text",
            text=f"Error executing {name}: {str(e)}"
        )]


async def main():
    """Main entry point for the server."""
    try:
        # Initialize the Traefik client
        await initialize_client()
        
        # Start the MCP server
        logger.info("Starting Traefik MCP server")
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, 
                write_stream, 
                server.create_initialization_options()
            )
        
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        raise


def cli_main():
    """CLI entry point that handles async main."""
    asyncio.run(main())


if __name__ == "__main__":
    cli_main()
