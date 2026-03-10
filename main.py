from server import mcp
import os
import uvicorn
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from utils.session_history_manager import SessionHistoryManager , UserConfigManager , SessionContextManager , WorkflowContextManager
from utils.mongodb_singleton import get_mongodb_client
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from utils.request_context import request_var
from starlette.responses import StreamingResponse
from starlette.routing import Route
from utils.markdown2docx import markdown_to_docx

# ============================================================================
# AGENT CONFIGURATION - Customize these settings for your use case
# ============================================================================
# Agent name/type (used in logging and identification)
AGENT_NAME = os.getenv("AGENT_NAME", "Generic Agent")
AGENT_TYPE = os.getenv("AGENT_TYPE", "assistant")

# Context window size for conversation history
DEFAULT_CONTEXT_WINDOW = int(os.getenv("CONTEXT_WINDOW_SIZE", "7"))

# Optional: Uncomment if using Redis caching (requires cache.redis_cache module)
# from cache.redis_cache import RedisCache
# r = RedisCache(f"{AGENT_TYPE}-cache-")

# Placeholder for Redis cache - set to None if not using Redis
# The code will fall back to MongoDB for caching
r = None

# Initialize MongoDB singleton
mongo_client = get_mongodb_client()

# Initialize managers with mongo_client dependency injection
session = SessionHistoryManager(mongo_client)
session_context = SessionContextManager(mongo_client)
user_config_manager = UserConfigManager(mongo_client)
workflow_context_manager = WorkflowContextManager(mongo_client)

# Import tools
import tools.hitl
import tools.cus_agent
import tools.stm
import tools.agent_chatbot

#  Expose the FastAPI app for Uvicorn
class HealthCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Debug logging to see all incoming requests with headers
        user_agent = request.headers.get("user-agent", "Unknown")
        origin = request.headers.get("origin", "None")
        print(f"📥 {request.method} {request.url.path} | Port: {request.client.port} | UA: {user_agent[:50]} | Origin: {origin}")
        
        request_var.set(request)
        
        if request.method.upper() == "OPTIONS":
            return await call_next(request)
        
        # Handle GET requests to /mcp endpoint (health checks)
        # TEMPORARILY DISABLED to prevent Postman continuous polling
        # Uncomment when you need health checks
        if request.url.path.startswith("/mcp") and request.method.upper() == "GET":
            # Return 405 Method Not Allowed to stop polling
            return JSONResponse(
                status_code=405,
                content={
                    "error": "Method Not Allowed",
                    "message": "GET requests temporarily disabled. Use POST for MCP operations.",
                    "allowed_methods": ["POST", "OPTIONS"]
                }
            )
        
        # Original health check response (currently disabled above)
        # if request.url.path.startswith("/mcp") and request.method.upper() == "GET":
        #     return JSONResponse(
        #         status_code=200,
        #         content={
        #             "status": "ok",
        #             "version": "1.0.0",
        #             "endpoints": {
        #                 "mcp": "/mcp",
        #                 "methods": ["POST", "OPTIONS"]
        #             }
        #         }
        #     )

        return await call_next(request)


# Security Headers and CORS Middleware
class SecurityAndCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data: https:; object-src 'none'; frame-ancestors 'none';"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Expose-Headers"] = "Authorization, Content-Type, Set-Cookie"
        return response


custom_middleware = [
    Middleware(HealthCheckMiddleware),
    Middleware(SecurityAndCORSMiddleware),
]


# Create the MCP HTTP app
base_app = mcp.http_app(
    transport="http",
    path="/mcp",
    middleware=custom_middleware,
    stateless_http=True
)

async def download_message(request: Request):
    data = await request.json()
    message = data.get("message", "")
    docx_stream = markdown_to_docx(message)
    docx_stream.seek(0)
    return StreamingResponse(
        docx_stream,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=message.docx"}
    )
    
# Register the route with the app
base_app.add_route("/download_message", download_message, methods=["POST"])

# Cookie Wrapper
class CookieWrapperApp:
    """Wrapper to intercept responses and set HttpOnly cookies"""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False
        status_code = None
        headers = []
        body_parts = []

        async def send_wrapper(message):
            nonlocal response_started, status_code, headers, body_parts

            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                headers = list(message.get("headers", []))
                return

            elif message["type"] == "http.response.body":
                body_parts.append(message.get("body", b""))
                if not message.get("more_body", False):
                    full_body = b"".join(body_parts)
                    try:
                        request = request_var.get()
                        if request and hasattr(request.state, 'refresh_token') and request.state.refresh_token:
                            refresh_token = request.state.refresh_token
                            refresh_token_expires = getattr(request.state, 'refresh_token_expires', 86400)
                            cookie_value = f"refresh_token={refresh_token}; Path=/; Max-Age={refresh_token_expires}; HttpOnly secure=true"
                            headers.append((b"set-cookie", cookie_value.encode("utf-8")))
                    except Exception:
                        pass
                    await send({
                        "type": "http.response.start",
                        "status": status_code,
                        "headers": headers,
                    })
                    await send({
                        "type": "http.response.body",
                        "body": full_body,
                    })
            else:
                await send(message)

        await self.app(scope, receive, send_wrapper)


# Wrap the MCP app
http_app = CookieWrapperApp(base_app)