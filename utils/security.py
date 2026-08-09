import re
import socket
import ssl
import http.client
import urllib.request
import html
from urllib.parse import urlparse

def is_safe_url(url: str) -> bool:
    """
    Validates a URL to prevent SSRF by checking:
    1. Scheme is HTTP or HTTPS.
    2. Hostname resolves to a public, non-private IP address.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
            
        hostname = parsed.hostname
        if not hostname:
            return False
            
        # Resolve hostname to IPs
        ips = socket.getaddrinfo(hostname, None)
        for ip_info in ips:
            ip = ip_info[4][0]
            # Check loopback
            if ip.startswith('127.'):
                return False
            # Check link-local / cloud metadata endpoints
            if ip.startswith('169.254.'):
                return False
            # Check private subnets
            if ip.startswith('10.'):
                return False
            if ip.startswith('172.'):
                parts = ip.split('.')
                if len(parts) >= 2 and 16 <= int(parts[1]) <= 31:
                    return False
            if ip.startswith('192.168.'):
                return False
            if ip == '0.0.0.0' or ip == '255.255.255.255':
                return False
            # IPv6 checks
            if ip == '::1' or ip.startswith('fe80:') or ip.startswith('fc00:') or ip.startswith('fd00:'):
                return False
        return True
    except Exception:
        return False

class DNSRebindingSafeHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, port=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, resolved_ip=None):
        super().__init__(host, port, timeout, source_address)
        self.resolved_ip = resolved_ip

    def connect(self):
        self.sock = self._create_connection(
            (self.resolved_ip, self.port), self.timeout, self.source_address
        )
        if self._tunnel_host:
            self._tunnel()

class DNSRebindingSafeHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host, port=None, key_file=None, cert_file=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, *, context=None, check_hostname=None, resolved_ip=None, **kwargs):
        import inspect
        base_sig = inspect.signature(http.client.HTTPSConnection.__init__)
        base_params = base_sig.parameters
        
        super_kwargs = {}
        if 'key_file' in base_params:
            super_kwargs['key_file'] = key_file
        if 'cert_file' in base_params:
            super_kwargs['cert_file'] = cert_file
        if 'timeout' in base_params:
            super_kwargs['timeout'] = timeout
        if 'source_address' in base_params and source_address is not None:
            super_kwargs['source_address'] = source_address
        if 'context' in base_params:
            super_kwargs['context'] = context
        if 'check_hostname' in base_params:
            super_kwargs['check_hostname'] = check_hostname
            
        for k, v in kwargs.items():
            if k in base_params:
                super_kwargs[k] = v
                
        super().__init__(host, port, **super_kwargs)
        self.resolved_ip = resolved_ip

    def connect(self):
        self.sock = self._create_connection(
            (self.resolved_ip, self.port), self.timeout, self.source_address
        )
        if self._tunnel_host:
            self._tunnel()
        server_hostname = self.host
        ctx = self._context if hasattr(self, '_context') else getattr(self, 'context', None)
        self.sock = ctx.wrap_socket(self.sock, server_hostname=server_hostname)

class DNSRebindingSafeHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, resolved_ip):
        super().__init__()
        self.resolved_ip = resolved_ip
        
    def http_open(self, req):
        return self.do_open(self._get_connection, req)
        
    def _get_connection(self, host, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, **kwargs):
        return DNSRebindingSafeHTTPConnection(host, timeout=timeout, resolved_ip=self.resolved_ip, **kwargs)

class DNSRebindingSafeHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, context, resolved_ip):
        super().__init__(context=context)
        self.resolved_ip = resolved_ip
        
    def https_open(self, req):
        return self.do_open(self._get_connection, req)
        
    def _get_connection(self, host, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, context=None, check_hostname=None, **kwargs):
        ctx = context if context is not None else getattr(self, '_context', None)
        return DNSRebindingSafeHTTPSConnection(
            host, timeout=timeout, context=ctx, check_hostname=check_hostname, resolved_ip=self.resolved_ip, **kwargs
        )

def sanitize_input(text: str) -> str:
    """
    Sanitizes plain text input by stripping all HTML tags and escaping special characters.
    """
    if not text:
        return ""
    stripped = re.sub(r'<[^>]*>', '', text)
    return html.escape(stripped)

def sanitize_url(url: str) -> str:
    """
    Sanitizes URL inputs by stripping HTML tags, removing whitespace, and ensuring
    characters that might break shell/markdown aren't present.
    """
    if not url:
        return ""
    clean_url = re.sub(r'<[^>]*>', '', url).strip()
    clean_url = re.sub(r'[\'"\s\r\n\t]', '', clean_url)
    if clean_url.lower().startswith("javascript:"):
        return ""
    return clean_url
