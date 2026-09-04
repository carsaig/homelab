"""
Traefik API Client

Async HTTP client for interacting with Traefik's REST API.
"""
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
import base64

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TraefikError(Exception):
    """Base exception for Traefik API errors."""
    pass


class TraefikConnectionError(TraefikError):
    """Exception raised when connection to Traefik fails."""
    pass


class TraefikAPIError(TraefikError):
    """Exception raised when Traefik API returns an error."""
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class TraefikClient:
    """
    Async client for Traefik API.
    
    Provides methods to query Traefik configuration, status, and metrics.
    """
    
    def __init__(self, api_url: str, api_key: Optional[str] = None, 
                 basic_auth_username: Optional[str] = None, 
                 basic_auth_password: Optional[str] = None, timeout: float = 30.0):
        """
        Initialize Traefik API client.
        
        Args:
            api_url: Base URL for Traefik API (e.g., http://localhost:8080)
            api_key: Optional API key for authentication (Bearer token)
            basic_auth_username: Optional username for basic authentication
            basic_auth_password: Optional password for basic authentication
            timeout: Request timeout in seconds
        """
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.basic_auth_username = basic_auth_username
        self.basic_auth_password = basic_auth_password
        self.timeout = timeout
        
        # Prepare headers
        self.headers = {
            'User-Agent': 'traefik-mcp-server/0.1.0',
            'Accept': 'application/json',
        }
        
        # Set authentication header - API key takes precedence over basic auth
        if api_key:
            self.headers['Authorization'] = f'Bearer {api_key}'
        elif basic_auth_username and basic_auth_password:
            credentials = f"{basic_auth_username}:{basic_auth_password}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            self.headers['Authorization'] = f'Basic {encoded_credentials}'
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make HTTP request to Traefik API.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., '/api/overview')
            **kwargs: Additional arguments for httpx request
            
        Returns:
            Parsed JSON response
            
        Raises:
            TraefikConnectionError: If connection fails
            TraefikAPIError: If API returns an error
        """
        url = urljoin(self.api_url, endpoint)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                logger.debug(f"Making {method} request to {url}")
                
                response = await client.request(method, url, **kwargs)
                
                if response.status_code == 401:
                    raise TraefikAPIError(
                        "Authentication failed. Check your API key.",
                        status_code=response.status_code
                    )
                
                if response.status_code == 404:
                    raise TraefikAPIError(
                        f"Endpoint not found: {endpoint}",
                        status_code=response.status_code
                    )
                
                if response.status_code >= 400:
                    error_msg = f"API request failed: {response.status_code}"
                    try:
                        error_data = response.json()
                        error_msg += f" - {error_data.get('message', 'Unknown error')}"
                    except:
                        pass
                    
                    raise TraefikAPIError(
                        error_msg,
                        status_code=response.status_code,
                        response=response.text
                    )
                
                # Return empty dict for 204 No Content
                if response.status_code == 204:
                    return {}
                
                return response.json()
                
        except httpx.TimeoutException:
            raise TraefikConnectionError(f"Request timeout after {self.timeout}s")
        except httpx.ConnectError as e:
            raise TraefikConnectionError(f"Failed to connect to Traefik at {self.api_url}: {e}")
        except httpx.HTTPError as e:
            raise TraefikConnectionError(f"HTTP error: {e}")
    
    async def health_check(self) -> bool:
        """
        Check if Traefik API is accessible.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            await self.get_overview()
            return True
        except TraefikError:
            return False
    
    async def get_overview(self) -> Dict[str, Any]:
        """
        Get Traefik overview information.
        
        Returns:
            Overview data with router, service, and middleware counts
        """
        return await self._make_request('GET', '/api/overview')
    
    async def get_routers(self, provider: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all HTTP routers.
        
        Args:
            provider: Optional provider name to filter by
            
        Returns:
            List of router configurations
        """
        endpoint = '/api/http/routers'
        if provider:
            endpoint += f'?provider={provider}'
        
        response = await self._make_request('GET', endpoint)
        return response
    
    async def get_router(self, router_name: str, provider: Optional[str] = None) -> Dict[str, Any]:
        """
        Get specific router configuration.
        
        Args:
            router_name: Name of the router
            provider: Optional provider name
            
        Returns:
            Router configuration
        """
        endpoint = f'/api/http/routers/{router_name}'
        if provider:
            endpoint += f'?provider={provider}'
        
        return await self._make_request('GET', endpoint)
    
    async def get_services(self, provider: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all HTTP services.
        
        Args:
            provider: Optional provider name to filter by
            
        Returns:
            List of service configurations
        """
        endpoint = '/api/http/services'
        if provider:
            endpoint += f'?provider={provider}'
        
        response = await self._make_request('GET', endpoint)
        return response
    
    async def get_service(self, service_name: str, provider: Optional[str] = None) -> Dict[str, Any]:
        """
        Get specific service configuration.
        
        Args:
            service_name: Name of the service
            provider: Optional provider name
            
        Returns:
            Service configuration
        """
        endpoint = f'/api/http/services/{service_name}'
        if provider:
            endpoint += f'?provider={provider}'
        
        return await self._make_request('GET', endpoint)
    
    async def get_middlewares(self, provider: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all HTTP middlewares.
        
        Args:
            provider: Optional provider name to filter by
            
        Returns:
            List of middleware configurations
        """
        endpoint = '/api/http/middlewares'
        if provider:
            endpoint += f'?provider={provider}'
        
        response = await self._make_request('GET', endpoint)
        return response
    
    async def get_middleware(self, middleware_name: str, provider: Optional[str] = None) -> Dict[str, Any]:
        """
        Get specific middleware configuration.
        
        Args:
            middleware_name: Name of the middleware
            provider: Optional provider name
            
        Returns:
            Middleware configuration
        """
        endpoint = f'/api/http/middlewares/{middleware_name}'
        if provider:
            endpoint += f'?provider={provider}'
        
        return await self._make_request('GET', endpoint)
    
    async def get_entrypoints(self) -> List[Dict[str, Any]]:
        """
        Get all entrypoints.
        
        Returns:
            List of entrypoint configurations
        """
        response = await self._make_request('GET', '/api/entrypoints')
        return response
    
    async def get_version(self) -> Dict[str, Any]:
        """
        Get Traefik version information.
        
        Returns:
            Version information
        """
        return await self._make_request('GET', '/api/version')
