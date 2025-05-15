# MP4 Repair Toolkit - Project Structure

## Directory Structure

```
mp4-recovery-toolkit/
├── .github/
│   ├── dependabot.yml
│   └── workflows/
│       └── test.yml
├── tests/
│   ├── good.mp4 (generated)
│   ├── truncated.mp4 (generated)
│   └── corrupted_data.mp4 (generated)
├── .gitignore
├── LICENSE
├── README.md
├── CONTRIBUTING.md
├── PROJECT_STRUCTURE.md
├── Dockerfile
├── mp4_recovery_master.py
├── mp4_info.py
├── recover.bat
├── recover.sh
└── test.bat
└── test.sh
```

## Overview of Files

### Core Files

- `mp4_recovery_master.py` - Main Python script that handles the MP4 recovery process
- `mp4_info.py` - Utility script to extract and display MP4 file parameters

### Platform-Independent Execution Scripts

- `recover.sh` - Universal Unix shell script for Linux and macOS users
- `recover.bat` - Windows batch file for running the tool on Windows systems

### Docker Configuration

- `Dockerfile` - Container configuration for Docker-based deployment

### Utility Scripts

- `test.sh` (`test.bat`) - Comprehensive test script to verify tool functionality

### Documentation

- `README.md` - Project overview, features, and usage instructions
- `CONTRIBUTING.md` - Guidelines for contributors to the project
- `LICENSE` - MIT License file
- `PROJECT_STRUCTURE.md` - This file, explaining the project organization

### CI/CD Configuration

- `.github/workflows/test.yml` - GitHub Actions workflow for automated testing
- `.github/dependabot.yml` - Configuration for automatic dependency updates
- `.gitignore` - Configuration to exclude test files and temporary directories

## Platform Compatibility

The toolkit is designed to be cross-platform compatible:

1. **Docker-based execution** (all platforms with Docker installed):
   - Build once, run anywhere with Docker
   - Uses the same container regardless of host OS

2. **Windows-specific execution**:
   - `recover.bat` provides a user-friendly interface for Windows users
   - Handles Windows path conversions and Docker volume mapping

3. **Unix-based execution** (Linux/macOS):
   - `recover.sh` provides a shell script interface
   - Uses color coding for better readability in terminal

## Usage Patterns

### Direct Python Usage

For users with Python and FFmpeg installed locally:
```
python mp4_recover_master.py input.mp4 reference.mp4 output.mp4
```

### Containerized Usage

For users with Docker installed:

Windows:
```
recover.bat repair input.mp4 reference.mp4 output.mp4
```

Linux/macOS:
```
./recover.sh repair input.mp4 reference.mp4 output.mp4
```

### Batch Processing

Windows:
```
recover.bat batch C:\damaged_videos C:\reference.mp4 C:\repaired
```

Linux/macOS:
```
./recover.sh batch ./damaged_videos ./reference.mp4 ./repaired
```

## Development Environment

The project is designed to be developed and tested in any environment with:
- Python 3.6+
- FFmpeg
- Docker (optional, for containerized testing)

CI/CD pipelines are configured to test on Linux, but the code is designed to be cross-platform compatible.