#!/usr/bin/env python3
"""
HTTP Reverse Proxy 
"""

import asyncio
import aiohttp
from aiohttp import web
import json
import logging
import sys
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ReverseProxy:
    
    def __init__(self, config):
        self.backends = self._parse_backends(config['backends'])
        self.current_backend = 0
        self.session = None
        
    def _parse_backends(self, backends):
        parsed = []
        for backend in backends:
            url = urlparse(backend['url'])
            parsed.append({
                'id': backend.get('id', backend['url']),
                'url': backend['url'],
                'host': url.hostname,
                'port': url.port or (443 if url.scheme == 'https' else 80),
                'healthy': True,
                'connections': 0
            })
        return parsed
    
    async def initialize(self):
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=100),
            timeout=aiohttp.ClientTimeout(total=30)
        )
        logger.info("Proxy initialized with %d backends", len(self.backends))
    
    async def handle_request(self, request):

        backend = self.select_backend()
        
        if not backend:
            logger.warning("No healthy backends available")
            return web.Response(text='503 Service Unavailable', status=503)
        
        target_url = f"{backend['url']}{request.path_qs}"
        logger.info(f"Proxying {request.method} {request.path} -> {backend['id']}")
        
        headers = self.process_headers(request)
        
        backend['connections'] += 1
        
        try:
            request_body = request.content if request.can_read_body else None
            
            async with self.session.request(
                method=request.method,
                url=target_url,
                headers=headers,
                data=request_body,
                allow_redirects=False
            ) as response:
                
                client_response = web.StreamResponse(
                    status=response.status,
                    headers=response.headers
                )
                await client_response.prepare(request)
                
                async for chunk in response.content.iter_chunked(8192):
                    await client_response.write(chunk)
                
                await client_response.write_eof()
                logger.info(f"Request completed: {response.status}")
                return client_response
                
        except asyncio.TimeoutError:
            backend['healthy'] = False
            logger.error(f"Gateway timeout for backend {backend['id']}")
            return web.Response(text='504 Gateway Timeout', status=504)
            
        except Exception as e:
            logger.error(f"Backend error for {backend['id']}: {e}")
            backend['healthy'] = False
            return web.Response(text='502 Bad Gateway', status=502)
            
        finally:
            backend['connections'] -= 1
    
    def process_headers(self, request):
        """Process and clean headers for backend request."""
        headers = dict(request.headers)
        
        hop_by_hop = ['connection', 'keep-alive', 'transfer-encoding', 'upgrade']
        for header in hop_by_hop:
            headers.pop(header, None)
        
        client_ip = request.remote or '127.0.0.1'
        
        headers['X-Forwarded-For'] = client_ip
        headers['X-Forwarded-Proto'] = request.scheme
        headers['X-Real-IP'] = client_ip
        
        return headers
    
    def select_backend(self):
        """Select backend using round-robin."""
        available = [b for b in self.backends if b['healthy']]
        if not available:
            return None
        
        backend = available[self.current_backend % len(available)]
        self.current_backend += 1
        return backend
    
    async def health_check(self):
        """Simple health check for backends."""
        while True:
            for backend in self.backends:
                try:
                    async with self.session.get(
                        f"{backend['url']}/health",
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        backend['healthy'] = (response.status == 200)
                        if backend['healthy']:
                            logger.debug(f"Backend {backend['id']} is healthy")
                        else:
                            logger.warning(f"Backend {backend['id']} unhealthy: {response.status}")
                except Exception as e:
                    backend['healthy'] = False
                    logger.warning(f"Backend {backend['id']} health check failed: {e}")
            
            await asyncio.sleep(10)
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.session:
            await self.session.close()
            logger.info("Proxy cleanup completed")

async def create_app():
    """Create and configure the proxy application."""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        logger.error("config.json not found!")
        print("ERROR: Please create a config.json file with backend configuration")
        print("Example:")
        print(json.dumps({
            "backends": [
                {"id": "backend1", "url": "http://localhost:3001"}
            ]
        }, indent=2))
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config.json: {e}")
        print(f"ERROR: Invalid JSON in config.json: {e}")
        sys.exit(1)
    
    proxy = ReverseProxy(config)
    await proxy.initialize()
    
    app = web.Application()
    
    async def health_handler(request):
        healthy = any(b['healthy'] for b in proxy.backends)
        return web.json_response({
            'status': 'healthy' if healthy else 'unhealthy',
            'backends': [
                {'id': b['id'], 'healthy': b['healthy'], 'connections': b['connections']}
                for b in proxy.backends
            ]
        }, status=200 if healthy else 503)
    
    app.router.add_get('/_health', health_handler)
    app.router.add_route('*', '/{path:.*}', proxy.handle_request)
    
    asyncio.create_task(proxy.health_check())
    
    async def cleanup(app):
        await proxy.cleanup()
    
    app.on_cleanup.append(cleanup)
    
    return app

def main():
    """Main entry point."""
    async def run():
        app = await create_app()
        print("Python Reverse Proxy starting...")
        print("Server running on http://localhost:8080")
        print("Health check: http://localhost:8080/_health")
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        
        try:
            await asyncio.Future()  # Run forever
        except KeyboardInterrupt:
            pass
        finally:
            await runner.cleanup()
    
    asyncio.run(run())

if __name__ == '__main__':
    main()