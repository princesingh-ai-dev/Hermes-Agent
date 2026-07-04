import sys
import os
import socket
import urllib.request
from unittest.mock import MagicMock, patch

# Prepend project root to sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR in sys.path:
    sys.path.remove(ROOT_DIR)
sys.path.insert(0, ROOT_DIR)

# Bypass local 'docker' namespace folder shadowing
import sys
if "docker" in sys.modules and not hasattr(sys.modules["docker"], "from_env"):
    del sys.modules["docker"]
orig_path = sys.path.copy()
new_path = []
for p in sys.path:
    if not p:
        continue
    norm_p = os.path.normcase(os.path.abspath(p))
    if os.path.exists(os.path.join(norm_p, "docker", "__init__.py")) and "site-packages" not in norm_p:
        continue
    new_path.append(p)
sys.path = new_path

from hermes.tools.code_exec import SandboxProxyServer, DockerSandboxManager
import docker # Force import of real docker package

sys.path = orig_path

def test_proxy_host_filtering():
    print("test_proxy_host_filtering: Running...")
    proxy = SandboxProxyServer()
    
    # Whitelisted
    assert proxy._is_host_allowed("pypi.org") is True
    assert proxy._is_host_allowed("files.pythonhosted.org") is True
    assert proxy._is_host_allowed("github.com") is True
    assert proxy._is_host_allowed("subdomain.github.com") is True
    
    # Blocked
    assert proxy._is_host_allowed("google.com") is False
    assert proxy._is_host_allowed("evil-server.com") is False
    assert proxy._is_host_allowed("my-external-api.net") is False
    print("test_proxy_host_filtering: PASSED")

def test_proxy_blocking_behavior():
    print("test_proxy_blocking_behavior: Running...")
    proxy = SandboxProxyServer(host="127.0.0.1")
    proxy.start()
    
    try:
        # Construct proxy handler using urllib pointing to our local proxy
        proxy_support = urllib.request.ProxyHandler({"http": f"http://127.0.0.1:{proxy.port}"})
        opener = urllib.request.build_opener(proxy_support)
        
        # 1. Attempt to fetch a blocked URL
        blocked_url = "http://google.com/"
        try:
            opener.open(blocked_url, timeout=3)
            raise AssertionError("Request to google.com should have been blocked!")
        except urllib.error.HTTPError as e:
            assert e.code == 403
            assert "Blocked" in e.read().decode("utf-8")
            
        print("test_proxy_blocking_behavior: PASSED")
    finally:
        proxy.stop()

def test_docker_manager_proxy_config():
    print("test_docker_manager_proxy_config: Running...")
    # Reset singleton cache to avoid test crosstalk from previous suites
    DockerSandboxManager._instance = None
    DockerSandboxManager._proxy_server = None
    
    # Patch client and connection to simulate Docker SDK availability
    with patch("docker.from_env") as mock_from_env:
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client
        mock_client.ping.return_value = True
        
        mock_client.containers.get.side_effect = Exception("Container not found")
        
        mgr = DockerSandboxManager.get_instance()
        assert mgr.is_available() is True
        
        # Verify that the proxy was started
        assert mgr._proxy_server is not None
        assert mgr._proxy_server.port is not None
        
        # Check container environment variables passed
        mock_container = MagicMock()
        mock_client.containers.run.return_value = mock_container
        
        container = mgr.get_or_create_container("test_proxy_session")
        args, kwargs = mock_client.containers.run.call_args
        
        env = kwargs.get("environment", {})
        assert "HTTP_PROXY" in env
        assert "HTTPS_PROXY" in env
        assert f"host.docker.internal:{mgr._proxy_server.port}" in env["HTTP_PROXY"]
        
        extra_hosts = kwargs.get("extra_hosts", {})
        assert extra_hosts.get("host.docker.internal") == "host-gateway"
        
        print("test_docker_manager_proxy_config: PASSED")
        
        # Stop proxy
        mgr.cleanup_container("test_proxy_session")
        if DockerSandboxManager._proxy_server:
            DockerSandboxManager._proxy_server.stop()

def main():
    print("--- Running Fine-Grained Network Proxy Sandbox Tests ---")
    test_proxy_host_filtering()
    test_proxy_blocking_behavior()
    test_docker_manager_proxy_config()
    print("All proxy sandbox tests passed successfully! 🎉")

if __name__ == "__main__":
    main()
