from __future__ import annotations
import sys
import subprocess
import importlib

def _ensure_dependencies():
    """Check for required packages and auto-install them if missing."""
    # Map: 'python_import_name' -> 'pip_package_name'
    required = {
        "cryptography": "cryptography",
        # If you ever get a ModuleNotFoundError for another package, just add it here!
        # Example: "psutil": "psutil", 
    }
    
    missing = []
    for module_name, package_name in required.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(package_name)
            
    if missing:
        print(f"⚠️ Missing dependencies detected: {', '.join(missing)}")
        print("Attempting to auto-install via pip...")
        try:
            # sys.executable ensures we install into the exact Python environment/venv currently running
            subprocess.check_call([sys.executable, "-m", "pip", "install", *missing, "--quiet"])
            print("✅ Dependencies installed successfully.\n")
        except subprocess.CalledProcessError:
            print(f"❌ Failed to auto-install dependencies.")
            print(f"Please install them manually: pip install {' '.join(missing)}")
            sys.exit(1)

# 1. Run dependency check FIRST, before importing any internal modules
# This prevents crashes in crypto.py if cryptography is missing.
_ensure_dependencies()

# Import the high-level packers and verifier
from .build import build_pfs, build_pfs_stream_single_file
from .inspect import read_pfs_info, inspect_pfs_image, extract_pfs_image
from .types import BuildStats, PFSImageInfo, PFSImageInspection, PFSExtractionResult, BuildError
from .pack_folder import pack_folder
from .pack_file import pack_file
from .pack_batch import pack_batch
from .create_exfat import create_exfat_image
from .pack_verify import verify_pfs

__all__ = [
    "build_pfs", "build_pfs_stream_single_file", 
    "read_pfs_info", "inspect_pfs_image", "extract_pfs_image",
    "BuildStats", "PFSImageInfo", "PFSImageInspection", "PFSExtractionResult", "BuildError",
    "pack_folder", "pack_file", "pack_batch", "create_exfat_image", "verify_pfs"
]