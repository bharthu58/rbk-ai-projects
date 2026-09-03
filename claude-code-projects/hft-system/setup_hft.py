import os
from pathlib import Path

def create_hft_structure():
    """Initializes the High-Frequency Trading system directory structure."""
    project_root = Path("hft-system")
    
    # Define directories to create
    directories = [
        project_root / "src" / "parser",
        project_root / "src" / "utils",
        project_root / "data",
        project_root / "build",
    ]
    
    # Define files to create
    files = [
        project_root / "CMakeLists.txt",
        project_root / "src" / "main.cpp",
        project_root / "src" / "parser" / "itch_parser.h",
        project_root / "src" / "parser" / "itch_parser.cpp",
        project_root / "src" / "utils" / "file_reader.h",
        project_root / "src" / "utils" / "file_reader.cpp",
    ]
    
    # Create directories
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {directory}")
        
    # Create empty placeholder files
    for file_path in files:
        file_path.touch(exist_ok=True)
        print(f"Created file: {file_path}")

    print(f"\nProject '{project_root}' initialized successfully.")
    print("You can now begin adding logic to your C++ files.")

if __name__ == "__main__":
    create_hft_structure()