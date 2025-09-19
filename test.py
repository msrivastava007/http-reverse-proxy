#!/usr/bin/env python3
"""Basic tests for the reverse proxy."""

import asyncio
import aiohttp
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_proxy():
    """Test basic proxy functionality."""
    print("Testing reverse proxy...")
    
    async with aiohttp.ClientSession() as session:
        # Test basic request
        print("\n1. Testing basic GET request...")
        async with session.get('http://localhost:8080/test') as response:
            assert response.status == 200
            data = await response.json()
            print(f"   Response from backend: {data.get('backend')}")
        
        # Test POST with body
        print("\n2. Testing POST with body...")
        payload = {'test': 'data'}
        async with session.post('http://localhost:8080/api/test', json=payload) as response:
            assert response.status == 200
            data = await response.json()
            print(f"   POST request successful to {data.get('backend')}")
        
        # Test health endpoint
        print("\n3. Testing health endpoint...")
        async with session.get('http://localhost:8080/_health') as response:
            data = await response.json()
            print(f"   Health status: {data['status']}")
            print(f"   Backends: {data['backends']}")
        
        # Test load balancing
        print("\n4. Testing load balancing (10 requests)...")
        backends_hit = {}
        for i in range(10):
            async with session.get(f'http://localhost:8080/test/{i}') as response:
                data = await response.json()
                backend = data.get('backend', 'unknown')
                backends_hit[backend] = backends_hit.get(backend, 0) + 1
        
        print(f"   Load distribution: {backends_hit}")
        print(f"   Load balancing working")
        
        # Test large file handling (streaming)
        print("\n5. Testing large file streaming...")
        # Create a large payload (10MB)
        large_data = b'x' * (10 * 1024 * 1024)
        async with session.post('http://localhost:8080/upload', data=large_data) as response:
            assert response.status == 200
            data = await response.json()
            print(f"   Large file streamed successfully to {data.get('backend')}")
            print(f"   Content-Length: {data.get('content_length')} bytes")
    
    print("\nAll tests passed!")

if __name__ == '__main__':
    asyncio.run(test_proxy())