"""
Traefik Query Tools

MCP tools for querying Traefik configuration and status.
"""
import logging
from typing import Any, Dict, List, Optional

from mcp.types import TextContent
from ..traefik.api_client import TraefikClient, TraefikError
from ..traefik.models import Router, Service, Middleware, TraefikOverview

logger = logging.getLogger(__name__)


def format_router_list(routers: List[Router]) -> str:
    """Format router list for display."""
    if not routers:
        return "No routers found."
    
    output = ["## Traefik Routers\n"]
    for router in routers:
        status = router.status or "unknown"
        service = router.service or "no service"
        entrypoints = ", ".join(router.entryPoints) if router.entryPoints else "none"
        
        output.append(f"### {router.name}")
        output.append(f"- **Status**: {status}")
        output.append(f"- **Rule**: `{router.rule}`")
        output.append(f"- **Service**: {service}")
        output.append(f"- **Entry Points**: {entrypoints}")
        output.append(f"- **Provider**: {router.provider}")
        
        if router.middlewares:
            output.append(f"- **Middlewares**: {', '.join(router.middlewares)}")
        
        output.append("")
    
    return "\n".join(output)


def format_service_list(services: List[Service]) -> str:
    """Format service list for display."""
    if not services:
        return "No services found."
    
    output = ["## Traefik Services\n"]
    for service in services:
        output.append(f"### {service.name}")
        output.append(f"- **Type**: {service.service_type}")
        output.append(f"- **Provider**: {service.provider}")
        
        if service.servers:
            output.append(f"- **Servers**: {len(service.servers)} configured")
            for i, server in enumerate(service.servers[:3], 1):  # Show first 3 servers
                url = server.get('url', 'unknown')
                output.append(f"  {i}. {url}")
            if len(service.servers) > 3:
                output.append(f"  ... and {len(service.servers) - 3} more")
        
        output.append("")
    
    return "\n".join(output)


def format_middleware_list(middlewares: List[Middleware]) -> str:
    """Format middleware list for display."""
    if not middlewares:
        return "No middlewares found."
    
    output = ["## Traefik Middlewares\n"]
    for middleware in middlewares:
        output.append(f"### {middleware.name}")
        output.append(f"- **Type**: {middleware.middleware_type}")
        output.append(f"- **Provider**: {middleware.provider}")
        output.append("")
    
    return "\n".join(output)


def format_overview(overview: TraefikOverview) -> str:
    """Format overview for display."""
    output = ["## Traefik Overview\n"]
    
    output.append("### Summary")
    output.append(f"- **Total Routers**: {overview.total_routers}")
    output.append(f"- **Total Services**: {overview.total_services}")
    output.append(f"- **Total Middlewares**: {overview.total_middlewares}")
    output.append(f"- **Total EntryPoints**: {overview.total_entrypoints}")
    output.append("")
    
    if overview.router:
        output.append("### Routers by Provider")
        for provider, count in overview.router.items():
            output.append(f"- **{provider}**: {count}")
        output.append("")
    
    if overview.service:
        output.append("### Services by Provider")
        for provider, count in overview.service.items():
            output.append(f"- **{provider}**: {count}")
        output.append("")
    
    if overview.middleware:
        output.append("### Middlewares by Provider")
        for provider, count in overview.middleware.items():
            output.append(f"- **{provider}**: {count}")
        output.append("")
    
    return "\n".join(output)


class QueryTools:
    """Container for Traefik query tools."""
    
    def __init__(self, client: TraefikClient):
        """Initialize query tools with Traefik client."""
        self.client = client
    
    async def list_routers(self, provider: Optional[str] = None) -> List[TextContent]:
        """
        List all HTTP routers.
        
        Args:
            provider: Optional provider name to filter by
            
        Returns:
            Formatted list of routers
        """
        try:
            routers_data = await self.client.get_routers(provider)
            routers = [Router(**data) for data in routers_data]
            formatted = format_router_list(routers)
            
            return [TextContent(type="text", text=formatted)]
            
        except TraefikError as e:
            error_msg = f"Failed to list routers: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]
    
    async def get_router_details(self, router_name: str, provider: Optional[str] = None) -> List[TextContent]:
        """
        Get specific router configuration.
        
        Args:
            router_name: Name of the router
            provider: Optional provider name
            
        Returns:
            Detailed router configuration
        """
        try:
            router_data = await self.client.get_router(router_name, provider)
            router = Router(name=router_name, **router_data)
            
            output = [f"## Router: {router.name}\n"]
            output.append(f"- **Rule**: `{router.rule}`")
            output.append(f"- **Status**: {router.status or 'unknown'}")
            output.append(f"- **Service**: {router.service or 'none'}")
            output.append(f"- **Provider**: {router.provider}")
            output.append(f"- **Priority**: {router.priority or 'default'}")
            
            if router.entryPoints:
                output.append(f"- **Entry Points**: {', '.join(router.entryPoints)}")
            
            if router.middlewares:
                output.append(f"- **Middlewares**: {', '.join(router.middlewares)}")
            
            if router.using:
                output.append(f"- **Using**: {', '.join(router.using)}")
            
            return [TextContent(type="text", text="\n".join(output))]
            
        except TraefikError as e:
            error_msg = f"Failed to get router '{router_name}': {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]
    
    async def list_services(self, provider: Optional[str] = None) -> List[TextContent]:
        """
        List all HTTP services.
        
        Args:
            provider: Optional provider name to filter by
            
        Returns:
            Formatted list of services
        """
        try:
            services_data = await self.client.get_services(provider)
            services = [Service(**data) for data in services_data]
            formatted = format_service_list(services)
            
            return [TextContent(type="text", text=formatted)]
            
        except TraefikError as e:
            error_msg = f"Failed to list services: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]
    
    async def get_service_details(self, service_name: str, provider: Optional[str] = None) -> List[TextContent]:
        """
        Get specific service configuration.
        
        Args:
            service_name: Name of the service
            provider: Optional provider name
            
        Returns:
            Detailed service configuration
        """
        try:
            service_data = await self.client.get_service(service_name, provider)
            service = Service(name=service_name, **service_data)
            
            output = [f"## Service: {service.name}\n"]
            output.append(f"- **Type**: {service.service_type}")
            output.append(f"- **Provider**: {service.provider}")
            
            if service.servers:
                output.append(f"- **Total Servers**: {len(service.servers)}")
                output.append("\n### Servers:")
                for i, server in enumerate(service.servers, 1):
                    url = server.get('url', 'unknown')
                    weight = server.get('weight', 'default')
                    output.append(f"{i}. **URL**: {url} (weight: {weight})")
            
            # Show additional configuration based on service type
            if service.loadBalancer:
                output.append("\n### Load Balancer Configuration:")
                lb = service.loadBalancer
                if 'method' in lb:
                    output.append(f"- **Method**: {lb['method']}")
                if 'sticky' in lb:
                    output.append(f"- **Sticky**: {lb['sticky']}")
                if 'healthCheck' in lb:
                    output.append(f"- **Health Check**: {lb['healthCheck']}")
            
            return [TextContent(type="text", text="\n".join(output))]
            
        except TraefikError as e:
            error_msg = f"Failed to get service '{service_name}': {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]
    
    async def list_middlewares(self, provider: Optional[str] = None) -> List[TextContent]:
        """
        List all HTTP middlewares.
        
        Args:
            provider: Optional provider name to filter by
            
        Returns:
            Formatted list of middlewares
        """
        try:
            middlewares_data = await self.client.get_middlewares(provider)
            middlewares = [Middleware(**data) for data in middlewares_data]
            formatted = format_middleware_list(middlewares)
            
            return [TextContent(type="text", text=formatted)]
            
        except TraefikError as e:
            error_msg = f"Failed to list middlewares: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]
    
    async def get_overview(self) -> List[TextContent]:
        """
        Get complete Traefik status overview.
        
        Returns:
            Formatted overview information
        """
        try:
            overview_data = await self.client.get_overview()
            overview = TraefikOverview(**overview_data)
            formatted = format_overview(overview)
            
            return [TextContent(type="text", text=formatted)]
            
        except TraefikError as e:
            error_msg = f"Failed to get overview: {str(e)}"
            logger.error(error_msg)
            return [TextContent(type="text", text=error_msg)]
