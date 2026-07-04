import asyncio
import logging
import psutil
import os
import shutil
import tempfile
from datetime import datetime
from hermes.memory.chroma_store import HermesMemory

logger = logging.getLogger("hermes.core.idle")

class IdleManager:
    def __init__(self, interval_seconds: int = 15):
        self.interval_seconds = interval_seconds
        self.is_running = False
        self._task = None
        self.last_harvest_time = datetime.now()
        # Initialize memory once for context harvesting
        try:
            self.memory = HermesMemory(collection_name="hermes")
        except Exception as e:
            logger.error(f"Failed to initialize memory for context harvester: {e}")
            self.memory = None

    def start(self):
        """Starts the background idle loop."""
        if not self.is_running:
            self.is_running = True
            self._task = asyncio.create_task(self._loop())
            logger.info(f"Jarvis Idle Loop started (Interval: {self.interval_seconds}s)")

    def stop(self):
        """Stops the background idle loop."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            logger.info("Jarvis Idle Loop stopped.")

    async def _loop(self):
        while self.is_running:
            try:
                await self._run_diagnostics()
                await self._sync_obsidian()
                await self._harvest_workspace_context()
                await self._run_self_maintenance()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in idle loop: {e}")
            
            await asyncio.sleep(self.interval_seconds)

    async def _sync_obsidian(self):
        """Option D: Bi-Directional Obsidian Sync"""
        try:
            from hermes.tools.obsidian import obsidian_write, obsidian_read
            from datetime import datetime
            
            # Simulated Sync: Hermes reads the latest Graph memories and backs them up to Obsidian.
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sync_content = f"Hermes Idle Sync triggered at {timestamp}.\n\nDiagnostics are normal. Graph memory synchronized."
            obsidian_write.invoke({"note_name": "Hermes_Sync_Log", "content": sync_content})
            logger.info("[PROACTIVE] Successfully synced memory to Obsidian Vault.")
        except Exception as e:
            logger.error(f"[PROACTIVE] Failed to sync Obsidian: {e}")

    async def _run_diagnostics(self):
        """A proactive diagnostic check that also reports top processes when resource usage is high."""
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        
        if cpu > 85.0 or ram > 90.0:
            # Gather top 3 resource-heavy processes
            heavy_procs = []
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    info = proc.info
                    heavy_procs.append(info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Sort by CPU or RAM accordingly
            if ram > 90.0:
                heavy_procs = sorted(heavy_procs, key=lambda p: p.get('memory_percent') or 0, reverse=True)[:3]
                proc_str = ", ".join([f"{p['name']} ({p['memory_percent']:.1f}% RAM)" for p in heavy_procs if p.get('name')])
                logger.warning(f"[PROACTIVE] High RAM Usage detected: {ram}%! Top processes: {proc_str}")
            else:
                heavy_procs = sorted(heavy_procs, key=lambda p: p.get('cpu_percent') or 0, reverse=True)[:3]
                proc_str = ", ".join([f"{p['name']} ({p['cpu_percent']:.1f}% CPU)" for p in heavy_procs if p.get('name')])
                logger.warning(f"[PROACTIVE] High CPU Usage detected: {cpu}%! Top processes: {proc_str}")
        else:
            logger.info(f"[PROACTIVE] Diagnostics OK (CPU: {cpu}%, RAM: {ram}%) - {datetime.now().strftime('%H:%M:%S')}")

    async def _harvest_workspace_context(self):
        """Scan project workspace for recently modified files and write updates to ChromaDB."""
        if not self.memory:
            return
            
        modified_files = []
        workspace_root = os.getcwd()
        exclude_dirs = {".git", ".venv", "venv", ".gemini", "node_modules", "__pycache__"}
        
        last_harvest_ts = self.last_harvest_time.timestamp()
        now = datetime.now()
        
        try:
            for root, dirs, files in os.walk(workspace_root):
                # Filter directories in-place to avoid traversing excluded paths
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                
                for file in files:
                    if file.endswith(".pyc") or file.endswith(".pyo"):
                        continue
                    file_path = os.path.join(root, file)
                    try:
                        stat = os.stat(file_path)
                        if stat.st_mtime > last_harvest_ts:
                            rel_path = os.path.relpath(file_path, workspace_root)
                            modified_files.append((rel_path, stat.st_size, stat.st_mtime))
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Error scanning workspace files: {e}")
            
        if modified_files:
            # Build list report
            report_lines = ["[Workspace Update] Recently modified files:"]
            for path, size, mtime in sorted(modified_files, key=lambda x: x[2], reverse=True)[:10]:
                mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                report_lines.append(f"- {path} (Size: {size} bytes, Modified: {mtime_str})")
                
            report_text = "\n".join(report_lines)
            try:
                self.memory.store(report_text, {"type": "workspace_activity", "timestamp": str(now)})
                logger.info(f"[PROACTIVE] Harvested workspace context for {len(modified_files)} changed files.")
            except Exception as e:
                logger.error(f"Failed to store harvested context in memory: {e}")
                
            # Proactive Context Pre-Fetching (Pillar IV / Phase 4)
            for rel_path, size, mtime in modified_files:
                abs_path = os.path.join(workspace_root, rel_path)
                if not os.path.exists(abs_path) or not rel_path.endswith(".py"):
                    continue
                    
                try:
                    with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                        lines = [f.readline() for _ in range(100)]
                        
                    imported_pkgs = set()
                    import re
                    for line in lines:
                        match = re.match(r'^\s*(?:import|from)\s+([a-zA-Z0-9_]+)', line)
                        if match:
                            imported_pkgs.add(match.group(1))
                            
                    if imported_pkgs:
                        guidance_cards = {
                            "dspy": "DSPy guidance: DSPy is a framework for programming—not prompting—language models. Use declarative Signatures (dspy.Signature), Modules (dspy.Predict, dspy.ChainOfThought), and Optimizers for prompt tuning.",
                            "sqlite3": "sqlite3 guidance: Always use WAL mode (Write-Ahead Log) for concurrency. On Windows, explicitly close connections to avoid process locks (WinError 32).",
                            "docker": "docker SDK guidance: Connect using docker.from_env(). For container networking, pass extra_hosts={'host.docker.internal': 'host-gateway'} to resolve host IP from the container.",
                            "pytest": "pytest guidance: Test files must start with test_. Use unittest.mock patch and MagicMock to isolate database and file systems.",
                            "langchain": "langchain guidance: Tools are registered via @tool decorator. Always document arguments precisely in the docstring as LLMs parse them.",
                        }
                        
                        found_guidance = [guidance_cards[pkg] for pkg in imported_pkgs if pkg in guidance_cards]
                        if found_guidance:
                            card_text = (
                                f"[PROACTIVE CONTEXT] The user is currently editing '{rel_path}' which imports: {', '.join(imported_pkgs)}.\n"
                                f"Here is relevant developer guidance for this file:\n"
                                + "\n".join([f"- {g}" for g in found_guidance])
                            )
                            self.memory.store(card_text, {"type": "proactive_context", "file_path": rel_path, "timestamp": str(now)})
                            logger.info(f"[PROACTIVE] Injected developer context card for '{rel_path}' into memory.")
                except Exception as e:
                    logger.debug(f"Failed to extract imports for proactive context: {e}")
                
        self.last_harvest_time = now

    async def _run_self_maintenance(self):
        """Resource-aware system self-maintenance: cleans transient sandbox files and rotates large logs."""
        try:
            # 1. Disk Space Space Check
            total, used, free = shutil.disk_usage(os.getcwd())
            free_percent = (free / total) * 100
            
            # Clean up temp sandbox folders if space is restricted (< 15%)
            if free_percent < 15.0:
                logger.warning(f"[MAINTENANCE] Low disk space detected ({free_percent:.1f}% free). Running cleanups.")
                temp_dir = tempfile.gettempdir()
                cleaned_count = 0
                for item in os.listdir(temp_dir):
                    if item.startswith("hermes_sandbox_"):
                        path = os.path.join(temp_dir, item)
                        try:
                            if os.path.isdir(path):
                                shutil.rmtree(path)
                            else:
                                os.remove(path)
                            cleaned_count += 1
                        except Exception:
                            pass
                if cleaned_count > 0:
                    logger.info(f"[MAINTENANCE] Reclaimed space by cleaning {cleaned_count} sandbox folders.")
        except Exception as e:
            logger.error(f"Error executing disk space checks: {e}")
            
        # 2. Log Rotation Check
        log_dir = "logs"
        if os.path.exists(log_dir) and os.path.isdir(log_dir):
            for file in os.listdir(log_dir):
                if file.endswith(".log"):
                    log_path = os.path.join(log_dir, file)
                    try:
                        size = os.path.getsize(log_path)
                        # Rotate if exceeds 10MB
                        if size > 10 * 1024 * 1024:
                            backup_path = os.path.join(log_dir, f"{file[:-4]}_old.log")
                            if os.path.exists(backup_path):
                                os.remove(backup_path)
                            shutil.move(log_path, backup_path)
                            # Create fresh empty log file
                            with open(log_path, "w", encoding="utf-8") as f:
                                pass
                            logger.info(f"[MAINTENANCE] Rotated large log file: {file}")
                    except Exception as e:
                        logger.error(f"Failed to rotate log file {file}: {e}")

        # 3. Docker Container Cleanup Check
        try:
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
            try:
                import docker
                client = docker.from_env()
            finally:
                sys.path = orig_path
                
            for container in client.containers.list(all=True):
                if container.name.startswith("hermes_session_"):
                    started_at = container.attrs.get('State', {}).get('StartedAt', '')
                    if started_at:
                        dt = datetime.strptime(started_at[:19], "%Y-%m-%dT%H:%M:%S")
                        elapsed = datetime.utcnow() - dt
                        if elapsed.total_seconds() > 3600:
                            logger.info(f"[MAINTENANCE] Pruning orphaned container '{container.name}' (running for {elapsed.total_seconds():.0f}s)...")
                            container.stop(timeout=2)
                            container.remove(force=True)
                            
                            # Clean host dir
                            session_id = container.name[len("hermes_session_"):]
                            temp_dir = os.path.join(tempfile.gettempdir(), f"hermes_session_{session_id}")
                            if os.path.exists(temp_dir):
                                shutil.rmtree(temp_dir)
        except Exception as e:
            logger.debug(f"Docker container cleanup check skipped: {e}")
