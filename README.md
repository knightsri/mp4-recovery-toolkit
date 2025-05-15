# MP4 Recovery Toolkit

A comprehensive cross-platform toolkit to check and repair damaged MP4 video files.

![Python](https://img.shields.io/badge/Python-3.6+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)

## Overview

The MP4 Recovery Toolkit analyzes and repairs corrupted MP4 video files by using a working reference MP4 file as a guide. It intelligently identifies issues in the damaged file and employs various repair strategies to preserve as much of the original content as possible.

## Features

- Check if an MP4 file is valid
- Repair damaged MP4 files using a reference MP4 file
- Detailed parameter analysis and issue identification
- Preservation of original parameters when possible
- Multiple repair strategies based on detected issues
- Detailed progress reporting
- Cross-platform support: Windows, Linux, and macOS
- Docker containerization for consistent execution

## Parameters Preserved During Repair

The tool attempts to preserve the following parameters from the input file when possible:

| Category | Parameters |
|----------|------------|
| **Video** | Codec, Bitrate, Frame Rate, Resolution, Scan Type |
| **Audio** | Codec, Bitrate, Sample Rate, Channels |
| **Container** | File structure, Metadata, Timecode, Index Information |
| **Other** | Interleaving |

## Requirements

- **Recommended**: Docker (any platform)
- **Alternative**: Python 3.6+ and FFmpeg/FFprobe

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/knightsri/mp4-recovery-toolkit.git
cd mp4-recovery-toolkit
```

### 2. Setup

**Windows:**
```
recover.bat setup
```

**Linux/macOS:**
```bash
chmod +x recover.sh
./recover.sh setup
```

## Usage

### Basic Commands

| Platform | Command Format |
|----------|----------------|
| **Windows** | `recover.bat COMMAND [OPTIONS]` |
| **Linux/macOS** | `./recover.sh COMMAND [OPTIONS]` |

Available commands:
- `setup` - Build the Docker image
- `repair` - Repair a single file
- `info` - Analyze an MP4 file
- `batch` - Process multiple files
- `--help` - Show help message

### Examples

#### Repairing a Single File

**Windows:**
```
recover.bat repair C:\path\to\damaged.mp4 C:\path\to\reference.mp4 C:\path\to\output.mp4
```

**Linux/macOS:**
```bash
./recover.sh repair /path/to/damaged.mp4 /path/to/reference.mp4 /path/to/output.mp4
```

#### Analyzing an MP4 File

**Windows:**
```
recover.bat info C:\path\to\video.mp4 --detailed
```

**Linux/macOS:**
```bash
./recover.sh info /path/to/video.mp4 --detailed
```

#### Batch Processing

**Windows:**
```
recover.bat batch C:\damaged_videos C:\reference.mp4 C:\repaired_videos
```

**Linux/macOS:**
```bash
./recover.sh batch /path/damaged_videos /path/reference.mp4 /path/repaired_videos
```

### Direct Docker Usage (Any Platform)

```bash
# Build the image
docker build -t mp4-recovery-toolkit .

# Repair a file
docker run --rm -v /path/to/videos:/data mp4-recovery-toolkit /data/damaged.mp4 /data/reference.mp4 /data/repaired.mp4

# Analyze a file
docker run --rm -v /path/to/videos:/data --entrypoint python mp4-recovery-toolkit /app/mp4_info.py /data/video.mp4
```

## Testing

Run the test script to verify functionality:

**Windows:**
```
test.bat
```

**Linux/macOS:**
```bash
./test.sh
```

## How It Works

1. **Parameter Analysis**: Extract parameters from both the input and reference files
2. **Issue Identification**: Identify specific issues in the input file
3. **Strategy Selection**: Select the most appropriate recovery strategy
4. **Multi-Method Repair**: Apply various recovery methods in sequence until successful
5. **Verification**: Verify the repaired file is valid

## Repair Strategies

The toolkit employs four main repair strategies:

1. **Remux**: When the container is damaged but streams are intact
2. **Transcode**: When streams are damaged but the container is intact
3. **Rebuild**: When critical issues are detected requiring a full rebuild
4. **Hybrid**: A combination of approaches for complex corruption cases

## Common Corruption Issues Addressed

- Truncated files (incomplete downloads)
- Header corruption (damaged metadata)
- Missing atoms (particularly the crucial 'moov' atom)
- Internal data corruption (damaged frames)
- Stream/container mismatch

## Troubleshooting

### Common Issues

1. **Docker Permission Issues**: Ensure you have proper Docker access:
   ```bash
   # On Linux
   sudo usermod -aG docker $USER
   # Then log out and back in
   ```

2. **MP4 File Not Recognized**: Ensure the file extension is .mp4:
   ```bash
   # Rename a file properly
   mv myvideo myvideo.mp4
   ```

3. **Repair Failed**: Try with a better reference file that's more similar to your damaged file.

### Getting Help

For detailed help:

```bash
# Windows
recover.bat --help

# Linux/macOS
./recover.sh --help
```

## Project Structure

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for details on the organization of this repository.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.