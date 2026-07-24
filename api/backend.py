"""Vercel Python Function entry point for the Green Canopy FastAPI app."""

from fastapi import FastAPI, Request

from backend.main import app as green_canopy_app


app = FastAPI(title="Green Canopy Vercel Function")


@app.middleware("http")
async def restore_rewritten_api_path(request: Request, call_next):
    """Restore the public API path when Vercel routes through /api/backend."""
    if request.url.path == "/api/backend":
        forwarded_path = request.query_params.get("_path", "").strip("/")
        request.scope["path"] = f"/api/{forwarded_path}" if forwarded_path else "/api"
    return await call_next(request)


app.mount("/", green_canopy_app)
