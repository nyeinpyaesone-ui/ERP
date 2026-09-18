from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class TenancyMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and validate tenant context from requests"""
    
    async def dispatch(self, request: Request, call_next):
        # Extract tenant from subdomain or header
        host = request.headers.get("host", "")
        subdomain = host.split(".")[0] if "." in host else None
        
        # Allow API key override for system services
        api_key = request.headers.get("X-API-Key")
        tenant_id_header = request.headers.get("X-Tenant-ID")
        
        try:
            if api_key:
                # Validate API key and extract tenant
                tenant_id = await self.validate_api_key(api_key)
                request.state.tenant_id = tenant_id
            elif tenant_id_header:
                # Direct tenant ID from header (for internal services)
                request.state.tenant_id = int(tenant_id_header)
            elif subdomain:
                # Extract from subdomain
                tenant = await self.get_tenant_by_subdomain(subdomain)
                if not tenant or not tenant.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Invalid or inactive tenant"
                    )
                request.state.tenant_id = tenant.id
                request.state.tenant_schema = tenant.schema_name
            else:
                # Public endpoints (login, registration, health checks)
                public_paths = [
                    "/api/v1/auth/login",
                    "/api/v1/auth/register",
                    "/api/v1/auth/forgot-password",
                    "/api/v1/health",
                    "/docs",
                    "/openapi.json"
                ]
                
                if not any(request.url.path.startswith(path) for path in public_paths):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Tenant context required. Provide X-Tenant-ID header or use tenant subdomain."
                    )
            
            response = await call_next(request)
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Tenancy middleware error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to establish tenant context"
            )
    
    async def validate_api_key(self, api_key: str) -> Optional[int]:
        """Validate API key and return tenant ID"""
        from app.database import get_db
        from sqlalchemy import select
        from app.models import Tenant
        
        async for db in get_db():
            result = await db.execute(
                select(Tenant).where(Tenant.subdomain == api_key)
            )
            tenant = result.scalar_one_or_none()
            
            if tenant and tenant.is_active:
                return tenant.id
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
    
    async def get_tenant_by_subdomain(self, subdomain: str):
        """Get tenant by subdomain"""
        from app.database import get_db
        from sqlalchemy import select
        from app.models import Tenant
        
        async for db in get_db():
            result = await db.execute(
                select(Tenant).where(Tenant.subdomain == subdomain)
            )
            return result.scalar_one_or_none()
        
        return None
