#!/usr/bin/env python3
"""
Manual PyPI Publishing Helper Script

This script helps with the manual PyPI publishing process for fapilog.
It validates the build, checks credentials, and provides step-by-step guidance.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


def run_command(cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result


def check_prerequisites() -> bool:
    """Check if all prerequisites are met."""
    print("🔍 Checking prerequisites...")

    # Check if we're in the right directory
    if not Path("pyproject.toml").exists():
        print(
            "❌ Error: pyproject.toml not found. Run this script from the project root."
        )
        return False

    # Check if build is available
    try:
        run_command([sys.executable, "-m", "build", "--version"])
        print("✅ Build tool available")
    except subprocess.CalledProcessError:
        print("❌ Error: Build tool not available. Install with: pip install build")
        return False

    # Check if twine is available
    try:
        run_command([sys.executable, "-m", "twine", "--version"])
        print("✅ Twine available")
    except subprocess.CalledProcessError:
        print("❌ Error: Twine not available. Install with: pip install twine")
        return False

    return True


def build_package() -> bool:
    """Build the package."""
    print("\n🔨 Building package...")

    # Clean previous builds
    if Path("dist").exists():
        print("Cleaning previous builds...")
        run_command(["rm", "-rf", "dist"])

    # Build package
    try:
        run_command([sys.executable, "-m", "build"])
        print("✅ Package built successfully")
        return True
    except subprocess.CalledProcessError:
        print("❌ Build failed")
        return False


def check_build_artifacts() -> bool:
    """Check that build artifacts are valid."""
    print("\n🔍 Checking build artifacts...")

    dist_path = Path("dist")
    if not dist_path.exists():
        print("❌ Error: dist/ directory not found")
        return False

    artifacts = list(dist_path.glob("*.whl")) + list(dist_path.glob("*.tar.gz"))
    if not artifacts:
        print("❌ Error: No build artifacts found in dist/")
        return False

    print(f"Found artifacts: {[a.name for a in artifacts]}")

    # Check artifacts with twine
    try:
        run_command([sys.executable, "-m", "twine", "check", "dist/*"])
        print("✅ Build artifacts are valid")
        return True
    except subprocess.CalledProcessError:
        print("❌ Build artifacts failed validation")
        return False


def check_pypirc() -> Optional[Dict[str, str]]:
    """Check if ~/.pypirc is configured."""
    pypirc_path = Path.home() / ".pypirc"
    if not pypirc_path.exists():
        return None

    print(f"📁 Found ~/.pypirc at {pypirc_path}")

    # Check file permissions
    stat = pypirc_path.stat()
    if stat.st_mode & 0o777 != 0o600:
        print("⚠️  Warning: ~/.pypirc should have permissions 600")
        print("   Run: chmod 600 ~/.pypirc")

    return {"pypirc": str(pypirc_path)}


def check_environment_variables() -> Dict[str, str]:
    """Check for environment variables."""
    env_vars = {}

    if "TWINE_USERNAME" in os.environ:
        env_vars["TWINE_USERNAME"] = os.environ["TWINE_USERNAME"]
        print("✅ TWINE_USERNAME set")

    if "TWINE_PASSWORD" in os.environ:
        env_vars["TWINE_PASSWORD"] = "***"  # Don't show actual password
        print("✅ TWINE_PASSWORD set")

    return env_vars


def get_package_info() -> Dict[str, str]:
    """Extract package information from pyproject.toml."""
    try:
        import tomllib

        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)

        project = data.get("project", {})
        return {
            "name": project.get("name", "unknown"),
            "version": project.get("version", "unknown"),
            "description": project.get("description", "unknown"),
        }
    except Exception as e:
        print(f"❌ Error reading pyproject.toml: {e}")
        return {}


def main():
    """Main function."""
    print("🚀 fapilog PyPI Publishing Helper")
    print("=" * 50)

    # Check prerequisites
    if not check_prerequisites():
        sys.exit(1)

    # Get package info
    package_info = get_package_info()
    if package_info:
        print(f"\n📦 Package: {package_info['name']} v{package_info['version']}")
        print(f"📝 Description: {package_info['description']}")

    # Build package
    if not build_package():
        sys.exit(1)

    # Check build artifacts
    if not check_build_artifacts():
        sys.exit(1)

    # Check credentials
    print("\n🔐 Checking credentials...")
    pypirc = check_pypirc()
    env_vars = check_environment_variables()

    if not pypirc and not env_vars:
        print("⚠️  No credentials found")
        print("   Set up credentials using one of these methods:")
        print("   1. Create ~/.pypirc file")
        print("   2. Set TWINE_USERNAME and TWINE_PASSWORD environment variables")
        print("   3. Use interactive mode (less secure)")

    # Provide next steps
    print("\n📋 Next Steps:")
    print("1. Test upload to TestPyPI:")
    print("   python -m twine upload --repository testpypi dist/*")
    print("")
    print("2. Install from TestPyPI to verify:")
    print("   pip install -i https://test.pypi.org/simple/ fapilog")
    print("")
    print("3. Upload to PyPI:")
    print("   python -m twine upload dist/*")
    print("")
    print("4. Create Git tag:")
    print(
        f'   git tag -a v{package_info.get("version", "0.1.0")} -m "Release v{package_info.get("version", "0.1.0")}"'
    )
    print("   git push origin --tags")
    print("")
    print("📖 For detailed instructions, see RELEASING.md")


if __name__ == "__main__":
    main()
