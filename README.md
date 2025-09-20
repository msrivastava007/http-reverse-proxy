# HTTP Reverse Proxy

A custom HTTP reverse proxy implementation built without third-party proxy libraries, using only standard networking utilities (aiohttp for HTTP client functionality).

### Prerequisites
- Python 3.9+

### Installation

First, clone the repository and set up the environment:

```bash
# Clone the repository
git clone https://github.com/msrivastava007/http-reverse-proxy.git
cd http-reverse-proxy


# Install dependencies
pip install -r requirements.txt
```

### Configuration
Edit `config.json` to add your backend servers:
```json
{
  "backends": [
    { "id": "backend1", "url": "http://localhost:3001" },
    { "id": "backend2", "url": "http://localhost:3002" }
  ]
}
```

### Running

**Step 1: Start Backend Servers (keep these running)**
```bash
# Terminal 1 - Backend 1
python3 test_backend.py 3001

# Terminal 2 - Backend 2  
python3 test_backend.py 3002
```

**Step 2: Start the Proxy (keep this running)**
```bash
# Terminal 3 - Proxy
python3 proxy.py
```

**Step 3: Test the Implementation**
```bash
# Terminal 4 - Tests
python3 test.py

# Manual testing
curl http://localhost:8080/test
curl http://localhost:8080/_health
```

## Design Decisions & Architecture

The primary goal was to create a I/O-bound service that correctly implements the core responsibilities of a reverse proxy.

### Why asyncio and aiohttp?

For a proxy, the vast majority of time is spent waiting on network I/O (waiting for the client to send data, waiting for the backend to respond). A synchronous, thread-per-request model would not scale well. `asyncio` provides a single-threaded, event-driven concurrency model that can handle thousands of simultaneous connections. `aiohttp` was used as the underlying toolkit for its asyncio-native server and client implementations.

### Full Streaming Architecture

I implemented a bidirectional streaming without buffering. This prevents memory exhaustion with large files and is the key difference between a toy implementation and a production-ready proxy.

The proxy maintains constant memory usage remains low and constant regardless of payload size by streaming data directly using (`request.content`) through chunks rather than loading entire payloads into memory.

### Request Lifecycle

1. A client request is accepted by the aiohttp server.
2. The `handle_request` method is invoked.
3. A healthy backend is selected via a simple round-robin strategy. If none are available, a 503 Service Unavailable is immediately returned.
4. Hop-by-hop headers (e.g., Connection, Transfer-Encoding) are stripped from the original request.
5. `X-Forwarded-*` headers are added to provide the backend with client context.
6. A new request is made to the selected backend, streaming the original request's body.
7. As the backend responds, its response is streamed back to the client. The proxy does not wait for the full response to complete.

### Limitations & TODOs

This implementation is focused and intentionally limited.

- **HTTP/1.1 Only**: There is no support for HTTP/2 or WebSocket.
- **Basic Load Balancing**:  A least-connections algorithm would be a clear next step for better load distribution.
- **Stateless**: Health checks and connection counts are managed in-memory and are local to each instance. This works for a single node but is a limitation for a horizontally scaled deployment.
- **No TLS Termination**: The proxy operates on plain HTTP. Production use would require it to handle HTTPS.

## Scaling Strategy

The current implementation is vertically scalable on a single machine. To handle enterprise-level traffic, a multi-layered approach is required.

### Vertical Scaling (Single Node)

 I'd use `gunicorn` with a `uvicorn` worker to manage multiple proxy processes on a single host, allowing it to utilize all available CPU cores.

```bash
# Example: Run 4 worker processes
gunicorn -w 4 -k uvicorn.workers.UvicornWorker proxy:create_app
```

### Horizontal Scaling (Multi-Node)

When a single machine is maxed out, you scale horizontally:

1. Deploy the proxy service across multiple nodes.
2. Place a dedicated L4/L7 load balancer (e.g., NGINX, HAProxy, or an AWS ALB) in front of the proxy fleet to distribute traffic.

**Problem**: State is now an issue. To implement features like least-connections load balancing or session affinity, a shared data store like Redis is required to store connection counts and session mappings.

**Problem**: Configuration is now static. Backends should be registered dynamically. I would integrate with a service discovery tool like Consul or rely on a platform like Kubernetes for service discovery.

## 🛡️ Security Measures

### Current Security

- **Header Sanitization**: Correctly removes hop-by-hop headers, preventing header leakage or misinterpretation by backends.
- **Timeout Protection**: Outbound requests have a 30-second timeout, preventing stuck connections from exhausting resources.
- **Resilience**: Health checks prevent traffic from being routed to known-dead backends.

### Production Hardening Roadmap

**Add TLS Termination**: Use Python's `ssl` module to load a certificate and key, and serve traffic over HTTPS.

**Implement Rate Limiting**: Add per-IP rate limiting to mitigate DoS attacks. A token bucket algorithm stored in Redis would be an effective approach.

**Enforce Auth**: The proxy is the logical place to terminate authentication. I'd add middleware to validate Authorization headers (e.g., JWTs) before proxying requests to trusted backends.

```python
# Example middleware logic
auth_header = request.headers.get('Authorization')
if not is_jwt_valid(auth_header):
    return web.Response(status=401, text='Unauthorized')
```

**Input Validation**: Add a layer that validates requests against a basic schema: check for allowed HTTP methods, reasonable URL lengths, and reject requests with suspicious characters (e.g., path traversal).

**Add Security Headers**: Append headers like `Strict-Transport-Security` (HSTS) and `X-Content-Type-Options: nosniff` to responses.


## Resources Used

- **Python asyncio documentation**: Core async patterns and event loop management
- **aiohttp documentation**: HTTP client/server functionality (not as a proxy library)
- **GitHub Copilot**: Used for:
  - Autocomplete suggestions for boilerplate code
  - Test case generation
  - Debugging async/await issues
  - Documentation formatting
- **Stack Overflow**: Error handling patterns and asyncio best practices




