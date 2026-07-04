import sys
import os
import asyncio

# Prepend project root to sys.path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from tests.test_spawner_dag import main as test_spawner_main
from tests.test_code_exec_sandbox import main as test_sandbox_main
from tests.test_cognitive_memory import main as test_memory_main
from tests.test_proactive_daemon import main as test_daemon_main
from tests.test_self_healing import main as test_healing_main
from tests.test_evolution_mutation import main as test_evolution_main

async def run_all():
    print("==================================================")
    print("🧪 RUNNING ALL SIX MODULE UNIT TESTS 🧪")
    print("==================================================")
    
    # 1. Spawner DAG
    try:
        await test_spawner_main()
    except Exception as e:
        print(f"❌ Spawner DAG Test Failed: {e}")
        
    # 2. Code Exec Sandbox
    try:
        test_sandbox_main()
    except Exception as e:
        print(f"❌ Code Exec Sandbox Test Failed: {e}")
        
    # 3. Cognitive Memory
    try:
        await test_memory_main()
    except Exception as e:
        print(f"❌ Cognitive Memory Test Failed: {e}")
        
    # 4. Proactive Daemon
    try:
        await test_daemon_main()
    except Exception as e:
        print(f"❌ Proactive Daemon Test Failed: {e}")
        
    # 5. Self Healing
    try:
        test_healing_main()
    except Exception as e:
        print(f"❌ Self Healing Test Failed: {e}")
        
    # 6. Evolution Mutation
    try:
        test_evolution_main()
    except Exception as e:
        print(f"❌ Evolution Mutation Test Failed: {e}")
        
    # 7. Stateful Sandbox
    try:
        from tests.test_stateful_sandbox import main as test_stateful_sandbox_main
        test_stateful_sandbox_main()
    except Exception as e:
        print(f"❌ Stateful Sandbox Test Failed: {e}")
        
    # 8. RLUC Corrections
    try:
        from tests.test_rluc_corrections import main as test_rluc_corrections_main
        test_rluc_corrections_main()
    except Exception as e:
        print(f"❌ RLUC Corrections Test Failed: {e}")
        
    # 9. Fine-Grained Proxy Sandbox
    try:
        from tests.test_proxy_sandbox import main as test_proxy_sandbox_main
        test_proxy_sandbox_main()
    except Exception as e:
        print(f"❌ Proxy Sandbox Test Failed: {e}")
        
    # 10. Proactive OS Daemon (Phase 4)
    try:
        from tests.test_proactive_daemon import main as test_proactive_daemon_main
        await test_proactive_daemon_main()
    except Exception as e:
        print(f"❌ Proactive OS Daemon Test Failed: {e}")

    # Helper function to run unittest TestCases programmatically
    import unittest
    def run_suite(case_cls):
        suite = unittest.TestLoader().loadTestsFromTestCase(case_cls)
        runner = unittest.TextTestRunner(verbosity=1, stream=sys.stdout)
        res = runner.run(suite)
        if not res.wasSuccessful():
            raise Exception(f"Failures: {len(res.failures)}, Errors: {len(res.errors)}")

    # 11. Autonomous Research Cron Blueprint
    print("\n--- Running Research Blueprint Tests ---")
    try:
        from tests.test_research_blueprint import TestResearchBlueprint
        run_suite(TestResearchBlueprint)
        print("Research Blueprint Tests: PASSED 🎉")
    except Exception as e:
        print(f"❌ Research Blueprint Test Failed: {e}")

    # 12. Skill Curator Lifecycle Manager
    print("\n--- Running Skill Curator Tests ---")
    try:
        from tests.test_skill_curator import TestSkillCurator
        run_suite(TestSkillCurator)
        print("Skill Curator Tests: PASSED 🎉")
    except Exception as e:
        print(f"❌ Skill Curator Test Failed: {e}")

    # 13. SOUL.md Personality Engine
    print("\n--- Running SOUL Engine Tests ---")
    try:
        from tests.test_soul_engine import TestSoulEngine
        run_suite(TestSoulEngine)
        print("SOUL Engine Tests: PASSED 🎉")
    except Exception as e:
        print(f"❌ SOUL Engine Test Failed: {e}")

    # 14. Hybrid Cognitive Memory Store
    print("\n--- Running Hybrid Memory Store Tests ---")
    try:
        from tests.test_hybrid_store import TestHybridMemoryStore
        run_suite(TestHybridMemoryStore)
        print("Hybrid Memory Store Tests: PASSED 🎉")
    except Exception as e:
        print(f"❌ Hybrid Memory Store Test Failed: {e}")

    # 15. JARVIS Phase 1 Security & Soul Hot-switching Upgrades
    print("\n--- Running JARVIS Phase 1 Tests ---")
    try:
        from tests.test_phase1 import TestPhase1Upgrades
        run_suite(TestPhase1Upgrades)
        print("JARVIS Phase 1 Tests: PASSED 🎉")
    except Exception as e:
        print(f"❌ JARVIS Phase 1 Test Failed: {e}")
        
    print("==================================================")
    print("✅ RUN COMPLETED ✅")
    print("==================================================")

if __name__ == "__main__":
    asyncio.run(run_all())
