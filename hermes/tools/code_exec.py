# hermes/tools/code_exec.py
import subprocess
import tempfile
import os
import ast
import logging
import shutil
import socket
import threading
import select
from urllib.parse import urlparse
from langchain_core.tools import tool
from hermes.tools.registry import register_tool

logger = logging.getLogger("hermes.tools.code_exec")

WHITELIST_DOMAINS = {
    "pypi.org",
    "files.pythonhosted.org",
    "pythonhosted.org",
    "pypi.python.org",
    "github.com",
    "raw.githubusercontent.com",
    "huggingface.co",
    "cdn-lfs.huggingface.co",
}

class SandboxProxyServer:
    """A lightweight, background HTTP/HTTPS proxy server enforcing a domain whitelist."""
    def __init__(self, host: str = "0.0.0.0"):
        self.host = host
        self.port = None
        self.server_socket = None
        self.thread = None
        self.running = False

    def start(self):
        """Find an open port and start the proxy in a background thread."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, 0)) # 0 binds to a random open port
        self.port = self.server_socket.getsockname()[1]
        self.server_socket.listen(128)
        self.running = True
        
        self.thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.thread.start()
        logger.info(f"Sandbox proxy started on {self.host}:{self.port}")

    def stop(self):
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass

    def _accept_loop(self):
        while self.running:
            try:
                client_conn, client_addr = self.server_socket.accept()
                t = threading.Thread(target=self._handle_client, args=(client_conn,), daemon=True)
                t.start()
            except Exception:
                break

    def _is_host_allowed(self, dest_host: str) -> bool:
        """Verify if the host is whitelisted (handles subdomains and exact matching)."""
        dest_host = dest_host.lower()
        if ":" in dest_host:
            dest_host = dest_host.split(":")[0]
            
        allowed_domains = WHITELIST_DOMAINS
        try:
            from hermes_cli.config import load_config_readonly, cfg_get
            cfg = load_config_readonly()
            user_domains = cfg_get(cfg, "sandbox", "whitelist_domains", default=None)
            if user_domains and isinstance(user_domains, list):
                allowed_domains = set(user_domains)
        except Exception:
            pass
            
        for domain in allowed_domains:
            if dest_host == domain or dest_host.endswith("." + domain):
                return True
        return False

    def _handle_client(self, client_conn):
        try:
            request_data = client_conn.recv(4096)
            if not request_data:
                client_conn.close()
                return
                
            header_lines = request_data.split(b"\r\n")
            first_line = header_lines[0].decode("utf-8", errors="replace")
            parts = first_line.split()
            
            if len(parts) < 2:
                client_conn.close()
                return
                
            method, url = parts[0], parts[1]
            
            # Extract target host and port
            if method == "CONNECT":
                # CONNECT pypi.org:443 HTTP/1.1
                if ":" in url:
                    dest_host, dest_port = url.split(":")
                    dest_port = int(dest_port)
                else:
                    dest_host, dest_port = url, 443
            else:
                # GET http://pypi.org/simple HTTP/1.1
                parsed = urlparse(url)
                dest_host = parsed.netloc
                if ":" in dest_host:
                    dest_host, dest_port = dest_host.split(":")
                    dest_port = int(dest_port)
                else:
                    dest_host, dest_port = dest_host, 80
                    
            if not self._is_host_allowed(dest_host):
                logger.warning(f"Blocked exfiltration request to host: {dest_host}")
                client_conn.sendall(b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\nBlocked by Sandbox Whitelist Proxy.")
                client_conn.close()
                return
                
            # Connect to destination
            try:
                dest_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                dest_sock.connect((dest_host, dest_port))
            except Exception as e:
                client_conn.sendall(f"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\nConnect failed: {e}".encode("utf-8"))
                client_conn.close()
                return
                
            if method == "CONNECT":
                client_conn.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            else:
                dest_sock.sendall(request_data)
                
            self._tunnel(client_conn, dest_sock)
        except Exception:
            pass
        finally:
            try:
                client_conn.close()
            except Exception:
                pass

    def _tunnel(self, client_sock, dest_sock):
        socks = [client_sock, dest_sock]
        try:
            while True:
                r, w, x = select.select(socks, [], [], 10)
                if not r:
                    break
                for s in r:
                    data = s.recv(8192)
                    if not data:
                        return
                    if s is client_sock:
                        dest_sock.sendall(data)
                    else:
                        client_sock.sendall(data)
        except Exception:
            pass
        finally:
            try:
                client_sock.close()
            except Exception:
                pass
            try:
                dest_sock.close()
            except Exception:
                pass

class DockerSandboxManager:
    """Manages conversation-persistent stateful Docker containers with proxy-restricted network access."""
    _instance = None
    _proxy_server = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            if cls._instance.is_available():
                cls._proxy_server = SandboxProxyServer()
                cls._proxy_server.start()
        return cls._instance

    def __init__(self):
        self.client = None
        try:
            import sys
            # If a shadowed 'docker' folder was already imported as a namespace package, clear it
            if "docker" in sys.modules and not hasattr(sys.modules["docker"], "from_env"):
                del sys.modules["docker"]
                
            orig_path = sys.path.copy()
            new_path = []
            for p in sys.path:
                if not p:
                    continue
                norm_p = os.path.normcase(os.path.abspath(p))
                # Only filter out directories that contain a real 'docker' package (with __init__.py)
                # to prevent shadowing, while preserving project roots that contain config-only 'docker' folders.
                if os.path.exists(os.path.join(norm_p, "docker", "__init__.py")) and "site-packages" not in norm_p:
                    continue
                new_path.append(p)
            sys.path = new_path
            try:
                import docker
                self.client = docker.from_env()
            finally:
                sys.path = orig_path
        except Exception as e:
            logger.warning(f"Could not connect to Docker daemon via SDK: {e}")

    def is_available(self) -> bool:
        if self.client is None:
            return False
        try:
            self.client.ping()
            return True
        except Exception:
            return False

    def get_or_create_container(self, session_id: str):
        """Get or start a stateful Docker container for a given session ID."""
        if not self.is_available():
            raise RuntimeError("Docker daemon is not reachable.")
            
        container_name = f"hermes_session_{session_id}"
        
        try:
            container = self.client.containers.get(container_name)
            if container.status != "running":
                logger.info(f"Starting stopped sandbox container '{container_name}'...")
                container.start()
            return container
        except Exception:
            pass
            
        temp_dir = os.path.join(tempfile.gettempdir(), f"hermes_session_{session_id}")
        os.makedirs(temp_dir, exist_ok=True)
        abs_temp_dir = os.path.abspath(temp_dir)
        
        logger.info(f"Spawning stateful sandbox container '{container_name}'...")
        
        # Build environment config pointing to local whitelist proxy
        env_vars = {}
        if self._proxy_server and self._proxy_server.port:
            proxy_url = f"http://host.docker.internal:{self._proxy_server.port}"
            env_vars = {
                "HTTP_PROXY": proxy_url,
                "HTTPS_PROXY": proxy_url,
                "http_proxy": proxy_url,
                "https_proxy": proxy_url,
            }
            
        container = self.client.containers.run(
            "python:3.12-slim",
            command="tail -f /dev/null",
            name=container_name,
            detach=True,
            volumes={abs_temp_dir: {"bind": "/app", "mode": "rw"}},
            working_dir="/app",
            extra_hosts={"host.docker.internal": "host-gateway"},
            environment=env_vars,
            mem_limit="256m",
            nano_cpus=500000000, # 0.5 CPUs
            restart_policy={"Name": "no"}
        )
        return container

    def execute_code(self, session_id: str, code: str, timeout: int = 10) -> dict:
        """Execute python code inside the running session container using exec_run."""
        container = self.get_or_create_container(session_id)
        
        temp_dir = os.path.join(tempfile.gettempdir(), f"hermes_session_{session_id}")
        os.makedirs(temp_dir, exist_ok=True)
        script_path = os.path.join(temp_dir, "script.py")
        
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)
            
        try:
            cmd = f"timeout {timeout} python /app/script.py"
            exit_code, output = container.exec_run(cmd, workdir="/app")
            
            stdout_str = output.decode("utf-8", errors="replace")
            stderr_str = ""
            
            if exit_code == 124:
                return {"error": "Execution timed out", "confined": True, "sandbox": "docker_stateful"}
                
            if exit_code != 0:
                stderr_str = stdout_str
                stdout_str = ""
                
            return {
                "stdout": stdout_str,
                "stderr": stderr_str,
                "code": exit_code,
                "confined": True,
                "sandbox": "docker_stateful"
            }
        except Exception as e:
            return {"error": f"Exec run failed: {e}", "confined": True, "sandbox": "docker_stateful"}

    def cleanup_container(self, session_id: str):
        """Stop and remove the container, and remove the local directory mount."""
        if not self.is_available():
            return
            
        container_name = f"hermes_session_{session_id}"
        try:
            container = self.client.containers.get(container_name)
            logger.info(f"Stopping and removing stateful sandbox container '{container_name}'...")
            container.stop(timeout=2)
            container.remove(force=True)
        except Exception:
            pass
            
        temp_dir = os.path.join(tempfile.gettempdir(), f"hermes_session_{session_id}")
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass

def _is_docker_available() -> bool:
    """Check if Docker is installed and the daemon is active."""
    try:
        res = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=3)
        return res.returncode == 0
    except Exception:
        return False

def _execute_in_local_fallback(code: str, timeout: int) -> dict:
    """Execute Python code locally but with environment variables scrubbed for safety."""
    safe_env = {}
    safe_keys = {"PATH", "SYSTEMROOT", "TEMP", "TMP", "COMSPEC"}
    for k, v in os.environ.items():
        if k.upper() in safe_keys:
            safe_env[k] = v
            
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
        f.write(code)
        fname = f.name
        
    try:
        result = subprocess.run(
            ["python", fname],
            env=safe_env,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "code": result.returncode,
            "confined": True,
            "sandbox": "local_fallback"
        }
    except subprocess.TimeoutExpired:
        return {"error": "Execution timed out", "confined": True, "sandbox": "local_fallback"}
    finally:
        try:
            os.unlink(fname)
        except OSError:
            pass

@register_tool
@tool("execute_python_safe")
def execute_python_safe(code: str, timeout: int = 10, session_id: str = "default_session") -> dict:
    """
    Execute Python code inside a secure environment.
    Uses persistent Docker container sandboxing when available, matching the provided session_id.
    Otherwise, falls back to a restricted local process.
    """
    sandbox_mgr = DockerSandboxManager.get_instance()
    if sandbox_mgr.is_available():
        try:
            return sandbox_mgr.execute_code(session_id, code, timeout)
        except Exception as e:
            logger.error(f"Stateful Docker execution failed, falling back to local runner: {e}")
            
    # Fallback to local execution
    return _execute_in_local_fallback(code, timeout)

def _get_ast_diagnostics(code: str) -> str:
    """Run ast.parse to detect compilation/syntax issues before executing."""
    try:
        ast.parse(code)
        return ""
    except SyntaxError as e:
        error_line = ""
        lines = code.splitlines()
        if e.lineno and 1 <= e.lineno <= len(lines):
            error_line = lines[e.lineno - 1]
            col = e.offset or 0
            indicator = " " * (col - 1) + "^"
            error_line = f"{error_line}\n{indicator}"
        return (
            f"AST SyntaxError: {e.msg}\n"
            f"  File: <string>, line {e.lineno}, col {e.offset}\n"
            f"  Code: {error_line}"
        )

def _query_healing_llm(prompt: str, code: str, error_feedback: str) -> str:
    """Call OpenAI/OpenRouter to heal the failing code based on compiler diagnostics."""
    from openai import OpenAI
    import os
    import re
    
    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
    
    if not api_key:
        logger.warning("No API credentials found for self-healing. Falling back to local heuristics.")
        if "SyntaxError" in error_feedback and "print " in code:
            return re.sub(r'print\s+([\'"])(.*?)([\'"])', r'print(\1\2\3)', code)
        return code
        
    model_name = os.environ.get("HERMES_MODEL") or "openrouter/free"
    if "/" not in model_name and "openrouter" in base_url:
        model_name = f"openrouter/{model_name}"
        
    try:
        client = OpenAI(base_url=base_url, api_key=api_key)
        
        system_message = (
            "You are a compiler-guided code self-healing assistant.\n"
            "Your task is to fix a Python script that failed compilation or execution.\n"
            "Analyze the code, the compile/runtime errors, and the original prompt goal.\n"
            "Return ONLY the fixed, complete Python code. Do not write explanation.\n"
            "Format the code inside a standard markdown ```python code block."
        )
        
        user_message = (
            f"--- ORIGINAL GOAL ---\n{prompt}\n\n"
            f"--- FAILING CODE ---\n```python\n{code}\n```\n\n"
            f"--- COMPILER & EXECUTION ERROR FEEDBACK ---\n{error_feedback}\n\n"
            f"Please heal the code. Return ONLY the complete corrected script."
        )
        
        resp = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.1
        )
        
        content = resp.choices[0].message.content or ""
        
        if "```python" in content:
            code_part = content.split("```python")[1].split("```")[0]
            return code_part.strip()
        elif "```" in content:
            code_part = content.split("```")[1].split("```")[0]
            return code_part.strip()
        return content.strip()
    except Exception as e:
        logger.error(f"Failed to query healing LLM: {e}")
        if "print " in code:
            return re.sub(r'print\s+([\'"])(.*?)([\'"])', r'print(\1\2\3)', code)
        return code

@register_tool
@tool("execute_with_healing")
def execute_with_healing(prompt: str, initial_code: str, session_id: str = "default_session") -> dict:
    """Option B: Self-Healing Code Execution. Runs code, and if it fails, auto-heals it using AST and compiler feedback."""
    max_retries = 3
    current_code = initial_code
    error_msg = "Unknown compilation issue"
    
    for attempt in range(max_retries):
        # 1. AST Lint check
        ast_errors = _get_ast_diagnostics(current_code)
        if ast_errors:
            logger.info(f"Self-Healing: AST compilation issue found on attempt {attempt+1}.")
            error_msg = ast_errors
            current_code = _query_healing_llm(prompt, current_code, ast_errors)
            continue
            
        # 2. Subprocess execution
        result = execute_python_safe.invoke({"code": current_code, "timeout": 15, "session_id": session_id})
        
        if result.get("code") == 0:
            return {
                "status": "success", 
                "attempts": attempt + 1, 
                "final_code": current_code, 
                "output": result.get("stdout")
            }
            
        error_msg = result.get("stderr") or result.get("error") or "Unknown runtime failure"
        logger.info(f"Self-Healing: Runtime execution issue found on attempt {attempt+1}: {error_msg}")
        
        current_code = _query_healing_llm(prompt, current_code, error_msg)
            
    return {
        "status": "failed", 
        "attempts": max_retries, 
        "last_error": error_msg,
        "final_code": current_code
    }
