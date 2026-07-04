"""
Tests for Phase 1 Upgrades: Runtime Security & SOUL Hot-switching
==================================================================
"""

import os
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from hermes.tools.code_exec import _execute_in_local_fallback, SandboxProxyServer
from agent.prompt_builder import load_soul_md
from agent.system_prompt import build_system_prompt_parts


class TestPhase1Upgrades(unittest.TestCase):
    def test_environment_scrubbing(self):
        """Ensure sensitive environment variables do not leak into the execution sandbox."""
        # Inject sensitive keys into host environment
        os.environ["SECRET_API_KEY"] = "super-secret-token-value-1234"
        os.environ["DATABASE_PASSWORD"] = "my-secure-password"

        # Code that prints environment variables
        code = (
            "import os\n"
            "print('SECRET_API_KEY' in os.environ)\n"
            "print('DATABASE_PASSWORD' in os.environ)\n"
            "print('PATH' in os.environ or 'path' in os.environ)\n"
        )
        
        result = _execute_in_local_fallback(code, timeout=10)
        self.assertEqual(result.get("code"), 0)
        
        stdout_lines = result["stdout"].strip().splitlines()
        self.assertEqual(stdout_lines[0], "False") # SECRET_API_KEY should be scrubbed
        self.assertEqual(stdout_lines[1], "False") # DATABASE_PASSWORD should be scrubbed
        self.assertEqual(stdout_lines[2], "True")  # PATH should be preserved

    def test_proxy_dynamic_whitelist(self):
        """Ensure SandboxProxyServer evaluates domain whitelists dynamically from config."""
        proxy = SandboxProxyServer()
        
        # Test default whitelist domain
        self.assertTrue(proxy._is_host_allowed("pypi.org"))
        self.assertTrue(proxy._is_host_allowed("files.pythonhosted.org"))
        self.assertFalse(proxy._is_host_allowed("malicious-exfil-target.com"))

        # Mock a custom config setup overrides
        mock_cfg = {"sandbox": {"whitelist_domains": ["custom-safe-domain.com", "huggingface.co"]}}
        
        with patch("hermes_cli.config.load_config_readonly", return_value=mock_cfg):
            # Dynamic config should override static defaults
            self.assertTrue(proxy._is_host_allowed("custom-safe-domain.com"))
            self.assertTrue(proxy._is_host_allowed("huggingface.co"))
            self.assertFalse(proxy._is_host_allowed("pypi.org")) # Now restricted!

    def test_soul_md_dynamic_rendering(self):
        """Ensure load_soul_md dynamically fetches SOUL profiles when active_soul is set."""
        mock_agent = MagicMock()
        mock_agent.active_soul = "coding-mentor"
        
        content = load_soul_md(context_length=None, agent=mock_agent)
        self.assertIsNotNone(content)
        self.assertIn("=== AGENT SOUL PERSONALITY ACTIVE: CODING-MENTOR ===", content)
        self.assertIn("Patient Software Engineering Educator", content)

        # Swapping profile
        mock_agent.active_soul = "devops-operator"
        content_devops = load_soul_md(context_length=None, agent=mock_agent)
        self.assertIn("=== AGENT SOUL PERSONALITY ACTIVE: DEVOPS-OPERATOR ===", content_devops)
        self.assertIn("DevOps & Infrastructure Operator", content_devops)

        # Fallback to default
        mock_agent.active_soul = "default"
        # Mock no SOUL.md file exists in home dir to trigger engine default template fallback
        with patch("pathlib.Path.exists", return_value=False):
            content_default = load_soul_md(context_length=None, agent=mock_agent)
            self.assertIn("=== AGENT SOUL PERSONALITY ACTIVE: DEFAULT ===", content_default)
            self.assertIn("General Assistant", content_default)

if __name__ == "__main__":
    unittest.main()
