#!/usr/bin/env python3
"""Simple mock backend server for testing."""

from aiohttp import web
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def handle_request(request):
    """Handle all requests."""
    port = request.app['port']
    
    # Log request details
    logger.info(f"Backend {port} received: {request.method} {request.path}")
    
    content_length = request.headers.get('Content-Length', '0')
    
    return web.json_response({
        'backend': f'backend-{port}',
        'port': port,
        'method': request.method,
        'path': request.path,
        'content_length': content_length,
        'headers': dict(request.headers)
    })

async def health_handler(request):
    return web.Response(text='OK', status=200)

def create_backend(port):
    """Create a mock backend server."""
    app = web.Application()
    app['port'] = port
    
    app.router.add_get('/health', health_handler)
    app.router.add_route('*', '/{path:.*}', handle_request)
    
    return app

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3001
    app = create_backend(port)
    print(f"Mock backend running on port {port}")
    web.run_app(app, host='0.0.0.0', port=port, print=None)