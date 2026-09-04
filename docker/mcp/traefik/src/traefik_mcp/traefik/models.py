"""
Traefik Data Models

Pydantic models for Traefik entities with validation and serialization.
"""
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict


class TraefikModel(BaseModel):
    """Base model for all Traefik entities."""
    
    model_config = ConfigDict(extra='allow')  # Allow additional fields from Traefik API


class Router(TraefikModel):
    """Traefik HTTP Router model."""
    
    name: str
    provider: str
    rule: str
    entryPoints: List[str] = Field(default_factory=list)
    middlewares: List[str] = Field(default_factory=list)
    service: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    using: List[str] = Field(default_factory=list)
    
    @field_validator('entryPoints', mode='before')
    @classmethod
    def parse_entrypoints(cls, v):
        if isinstance(v, str):
            return [v]
        return v or []
    
    @field_validator('middlewares', mode='before')
    @classmethod
    def parse_middlewares(cls, v):
        if isinstance(v, str):
            return [v]
        return v or []


class Service(TraefikModel):
    """Traefik HTTP Service model."""
    
    name: str
    provider: str
    loadBalancer: Optional[Dict[str, Any]] = None
    mirroring: Optional[Dict[str, Any]] = None
    weighted: Optional[Dict[str, Any]] = None
    
    @property
    def service_type(self) -> str:
        """Determine the service type based on configuration."""
        if self.loadBalancer:
            return 'loadbalancer'
        elif self.mirroring:
            return 'mirroring'
        elif self.weighted:
            return 'weighted'
        else:
            return 'unknown'
    
    @property
    def servers(self) -> List[Dict[str, Any]]:
        """Extract servers from loadBalancer configuration."""
        if self.loadBalancer and 'servers' in self.loadBalancer:
            return self.loadBalancer['servers']
        return []


class Middleware(TraefikModel):
    """Traefik HTTP Middleware model."""
    
    name: str
    provider: str
    middleware_type: Optional[str] = None
    
    @field_validator('middleware_type', mode='before')
    @classmethod
    def extract_middleware_type(cls, v, info):
        """Extract middleware type from the configuration."""
        if v:
            return v
        
        # Try to determine type from available keys in the input data
        if info and info.context:
            data = info.context.get('data', {})
        else:
            # Fallback: check if we have any additional fields
            return 'unknown'
        
        for key in data.keys():
            if key not in ['name', 'provider', 'middleware_type']:
                return key
        return 'unknown'
    
    def model_post_init(self, __context) -> None:
        """Post-initialization to set middleware_type if not already set."""
        if self.middleware_type is None:
            # Check all fields except the basic ones
            for field_name, value in self.model_dump(exclude={'name', 'provider', 'middleware_type'}).items():
                if value is not None:
                    self.middleware_type = field_name
                    break
            else:
                self.middleware_type = 'unknown'


class EntryPoint(TraefikModel):
    """Traefik EntryPoint model."""
    
    name: str
    address: str
    http: Optional[Dict[str, Any]] = None
    transport: Optional[Dict[str, Any]] = None
    forwardedHeaders: Optional[Dict[str, Any]] = None


class Provider(TraefikModel):
    """Traefik Provider model."""
    
    name: str
    provider_type: str


class TraefikOverview(TraefikModel):
    """Traefik overview information."""
    
    http: Dict[str, Any] = Field(default_factory=dict)
    tcp: Dict[str, Any] = Field(default_factory=dict)
    udp: Dict[str, Any] = Field(default_factory=dict)
    features: Dict[str, Any] = Field(default_factory=dict)
    providers: List[str] = Field(default_factory=list)
    
    @property
    def total_routers(self) -> int:
        """Total number of routers."""
        return (self.http.get('routers', {}).get('total', 0) + 
                self.tcp.get('routers', {}).get('total', 0) + 
                self.udp.get('routers', {}).get('total', 0))
    
    @property
    def total_services(self) -> int:
        """Total number of services."""
        return (self.http.get('services', {}).get('total', 0) + 
                self.tcp.get('services', {}).get('total', 0) + 
                self.udp.get('services', {}).get('total', 0))
    
    @property
    def total_middlewares(self) -> int:
        """Total number of middlewares."""
        return (self.http.get('middlewares', {}).get('total', 0) + 
                self.tcp.get('middlewares', {}).get('total', 0) + 
                self.udp.get('middlewares', {}).get('total', 0))
    
    @property
    def total_entrypoints(self) -> int:
        """Total number of entrypoints."""
        # EntryPoints are not in overview, would need separate API call
        return 0
    
    @property
    def router(self) -> Dict[str, int]:
        """Router counts by protocol."""
        return {
            'http': self.http.get('routers', {}).get('total', 0),
            'tcp': self.tcp.get('routers', {}).get('total', 0),
            'udp': self.udp.get('routers', {}).get('total', 0)
        }
    
    @property
    def service(self) -> Dict[str, int]:
        """Service counts by protocol."""
        return {
            'http': self.http.get('services', {}).get('total', 0),
            'tcp': self.tcp.get('services', {}).get('total', 0),
            'udp': self.udp.get('services', {}).get('total', 0)
        }
    
    @property
    def middleware(self) -> Dict[str, int]:
        """Middleware counts by protocol."""
        return {
            'http': self.http.get('middlewares', {}).get('total', 0),
            'tcp': self.tcp.get('middlewares', {}).get('total', 0),
            'udp': self.udp.get('middlewares', {}).get('total', 0)
        }


class TraefikVersion(TraefikModel):
    """Traefik version information."""
    
    version: str
    codename: Optional[str] = None
    build_date: Optional[str] = None


class HealthStatus(TraefikModel):
    """Health status information."""
    
    healthy: bool
    message: Optional[str] = None
    version: Optional[str] = None
    uptime: Optional[str] = None


# Utility functions for model conversion
def parse_router(data: Dict[str, Any], name: str) -> Router:
    """Parse router data from API response."""
    return Router(name=name, **data)


def parse_service(data: Dict[str, Any], name: str) -> Service:
    """Parse service data from API response."""
    return Service(name=name, **data)


def parse_middleware(data: Dict[str, Any], name: str) -> Middleware:
    """Parse middleware data from API response."""
    return Middleware(name=name, **data)


def parse_entrypoint(data: Dict[str, Any], name: str) -> EntryPoint:
    """Parse entrypoint data from API response."""
    return EntryPoint(name=name, **data)
