"""Main FastAPI application with async support."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from app.api.exception_handlers import register_exception_handlers
from app.api.graphql.schema import schema
# REST API routers (sync - FastAPI handles async wrapping automatically)
from app.api.rest.bank_transactions import router as bank_transactions_router
from app.api.rest.invoices import router as invoices_router
from app.api.rest.matches import router as matches_router
from app.api.rest.reconciliation import router as reconciliation_router
from app.api.rest.tenants import router as tenants_router
from app.api.rest.vendors import router as vendors_router
from app.core.config import get_settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # Startup: Initialize database
    init_db()
    yield
    # Shutdown: Cleanup if needed


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="""
Multi-Tenant Invoice Reconciliation API

This API provides:
- Multi-tenant invoice management
- Bank transaction import with idempotency
- Automated invoice-transaction reconciliation
- AI-powered match explanations

## Features

- **Multi-tenancy**: Complete data isolation between organizations
- **Async Support**: Database layer supports async operations
- **Reconciliation**: Deterministic matching with configurable scoring
- **AI Integration**: Natural language explanations with graceful fallback
- **Idempotency**: Safe bulk imports with idempotency keys
        """,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Register exception handlers
    register_exception_handlers(app)

    # Register REST API routers
    app.include_router(tenants_router)
    app.include_router(vendors_router)
    app.include_router(invoices_router)
    app.include_router(bank_transactions_router)
    app.include_router(matches_router)
    app.include_router(reconciliation_router)

    # Register GraphQL router
    graphql_app = GraphQLRouter(schema, path="/graphql")
    app.include_router(graphql_app, prefix="")

    @app.get("/", tags=["root"], include_in_schema=False)
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "Multi-Tenant Invoice Reconciliation API",
            "version": "1.0.0",
            "docs": "/docs",
            "graphql": "/graphql",
            "health": "/health",
        }

    @app.get("/health", tags=["health"])
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "version": "1.0.0"}

    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
