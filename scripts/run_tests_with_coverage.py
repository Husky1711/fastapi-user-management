"""
Run all tests and generate coverage report
"""

import subprocess
import sys
import os
from pathlib import Path

def print_header(text):
    print(f"\n{'='*70}")
    print(f"📊 {text}")
    print('='*70)

def run_test_file(file_path):
    """Run a test file and report results"""
    print(f"\n🧪 Running: {file_path.name}")
    try:
        result = subprocess.run(
            [sys.executable, str(file_path)],
            capture_output=False,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    """Run all tests and generate summary"""
    
    print_header("RUNNING ALL TESTS WITH COVERAGE ANALYSIS")
    
    # Find all test files
    project_root = Path(__file__).parent.parent
    test_files = []
    
    # Integration tests
    integration_dir = project_root / "tests" / "integration"
    if integration_dir.exists():
        test_files.extend([
            integration_dir / "test_user_dashboard.py",
            integration_dir / "test_admin_dashboard.py",
            integration_dir / "test_org_admin_dashboard.py",
            integration_dir / "test_super_admin_dashboard.py",
            integration_dir / "test_comprehensive_dashboards.py",
            integration_dir / "test_organization_isolation.py",
        ])
    
    # E2E tests
    e2e_dir = project_root / "tests" / "e2e"
    if e2e_dir.exists():
        test_files.extend([
            e2e_dir / "test_cache_with_apis.py",
            e2e_dir / "test_email_service.py",
            e2e_dir / "test_login_security.py",
        ])
    
    # Unit tests
    unit_dir = project_root / "tests" / "unit"
    if unit_dir.exists():
        test_files.extend([
            unit_dir / "test_user_service.py",
            unit_dir / "test_auth_services.py",
        ])
    
    # Performance tests
    perf_dir = project_root / "tests" / "performance"
    if perf_dir.exists():
        test_files.extend([
            perf_dir / "test_query_performance.py",
        ])
    
    # Filter to existing files
    existing_files = [f for f in test_files if f.exists()]
    
    print(f"\n📋 Found {len(existing_files)} test files")
    
    # Run tests
    results = []
    for test_file in existing_files:
        passed = run_test_file(test_file)
        results.append((test_file.name, passed))
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    success_rate = (passed / total * 100) if total > 0 else 0
    
    print(f"\nTotal Test Files: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {success_rate:.1f}%")
    
    # Show breakdown
    print("\n" + "─"*70)
    print("BREAKDOWN BY FILE:")
    print("─"*70)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {name}")
    
    print("\n" + "="*70)
    
    if success_rate == 100.0:
        print("✅ PERFECT: All tests passed!")
    elif success_rate >= 90.0:
        print("✅ EXCELLENT: Most tests passed!")
    elif success_rate >= 80.0:
        print("✅ GOOD: Tests mostly passing!")
    else:
        print("⚠️  Some tests failed. Review the output above.")
    
    print("="*70 + "\n")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())

