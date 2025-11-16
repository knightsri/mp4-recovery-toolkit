# CLAUDE.md - Project Context for AI Assistants

## Project Overview

**MP4 Recovery Toolkit** is a comprehensive cross-platform toolkit for checking, analyzing, and repairing damaged MP4 video files. The system uses a working reference MP4 file as a guide to intelligently identify and fix corruption issues through multiple recovery strategies.

## Core Goals

1. **Repair Corrupted MP4 Files**: Recover as much content as possible from damaged files
2. **Cross-Platform Support**: Work seamlessly on Windows, Linux, and macOS
3. **Docker-First Approach**: Provide consistent execution environment across platforms
4. **Parameter Preservation**: Maintain original video/audio parameters when possible
5. **Multiple Recovery Strategies**: Apply various techniques based on corruption type
6. **User-Friendly Interface**: Simple CLI wrapper scripts for non-technical users

## Technical Architecture

### Tech Stack

- **Language**: Python 3.9+ (standard library only)
- **Core Dependency**: FFmpeg 4.3.x (includes ffprobe)
- **Containerization**: Docker
- **Platform Support**: Windows (batch), Linux/macOS (bash)
- **Version**: 1.3.0

### Key Components

1. **mp4_recovery_master.py**: Orchestration script that runs 17 different recovery techniques sequentially
2. **mp4_info.py**: Analysis tool for extracting detailed MP4 file information
3. **recovery_techniques/**: 17 Python modules implementing different repair strategies
4. **recover.sh / recover.bat**: Cross-platform wrapper scripts
5. **Dockerfile**: Containerized environment with FFmpeg and Python

### Recovery Techniques (17 total)

1. Standard Remux
2. Advanced FFmpeg
3. Raw NAL Extraction (H.264)
4. Raw AAC Extraction
5. Atom Structure Repair
6. MOOV Atom Reconstruction
7. Frame-by-Frame Rebuild
8. Multi-Segment Repair
9. Metadata Transplant
10. Hybrid Approach
11. Audio Offset Correction
12. SPS/PPS Injection
13. VFR to CFR Fix
14. Recover from Raw Disk Image
15. FFprobe Deep Analysis Repair
16. BMFF Atom Editor
17. Deep Atom Repair

## Design Constraints

### Security Requirements

- **CRITICAL**: Never use `eval` in shell scripts (command injection vulnerability)
- **HIGH**: Validate all user-provided file paths (prevent path traversal)
- **HIGH**: Docker containers should run as non-root user
- **MEDIUM**: Input validation for all file paths and technique numbers

### Code Quality Standards

- Use Python standard library only (no external dependencies currently)
- All file operations must handle errors gracefully
- Exit codes: 0 = success, non-zero = failure
- Techniques must self-validate output before claiming success
- No hardcoded paths or magic numbers (extract to constants)

### Platform Requirements

- Must work identically on Windows, Linux, and macOS
- Prefer Docker execution for consistency
- Fallback to native Python + FFmpeg if Docker unavailable
- File paths must use platform-appropriate separators

### Performance Considerations

- Techniques run sequentially (first success wins)
- Batch mode currently processes files one at a time
- Temporary files should be cleaned up properly
- Large file support (handle files bigger than available RAM)

## Known Issues & Priorities

### Critical/High Priority

1. **Command injection in recover.sh** (lines 210, 299, 457) - use array-based construction
2. **Missing output validation** - implement `is_output_truly_valid()` function
3. **Path traversal vulnerability** - add validation across all scripts
4. **Docker runs as root** - add non-root user (mp4user already partially implemented)

### Medium Priority

1. **Inconsistent error handling** - avoid broad exception catching
2. **Hardcoded values** - extract to configuration file
3. **Code duplication** - create shared utility module (mp4_utils.py)
4. **Placeholder author info** - needs removal or proper attribution

### Future Enhancements (see TODO.md)

1. **C/C++ Core Library**: Replace Python techniques with performant C/C++ library for deep atom manipulation
2. **Configuration File**: Support config.ini/config.json for user customization
3. **GUI**: Web or desktop GUI wrapper for accessibility
4. **Advanced Validation**: Compare duration, size, stream parameters against reference
5. **Parallel Batch Processing**: Process multiple files concurrently

## Development Guidelines

### When Adding Features

- Maintain backward compatibility with existing CLI interface
- Add new techniques as separate numbered modules in recovery_techniques/
- Update mp4_recovery_master.py to include new technique in sequence
- Test on all three platforms (Windows, Linux, macOS)
- Update README.md and PROJECT_STRUCTURE.md

### When Fixing Bugs

- Prioritize security issues first (command injection, path traversal)
- Improve error messages with contextual information
- Add proper input validation
- Use specific exception handling (avoid bare except)
- Test edge cases (empty files, missing files, huge files)

### Code Style

- Python: Follow PEP 8 conventions
- Shell: Use shellcheck-compliant patterns
- Comments: Explain WHY, not WHAT
- Error messages: Include file paths and specific failure reasons
- Exit codes: Use consistent meanings across all scripts

### Testing Approach

- Curate diverse corruption test cases (missing moov, bad offsets, truncated files)
- Test with different codecs (H.264, H.265, AAC, Opus)
- Validate output quality, not just successful exit codes
- Test with various file sizes (small, medium, large)
- Test all three platform wrappers

## Common Corruption Scenarios

The toolkit is designed to handle:

- **Truncated files**: Incomplete downloads or recordings
- **Header corruption**: Damaged ftyp/moov atoms
- **Missing MOOV atom**: Critical metadata missing
- **Bad chunk offsets**: stco/co64 pointing to wrong locations
- **Internal data corruption**: Damaged frames in mdat
- **Audio/Video desync**: Incorrect timing information
- **Missing parameter sets**: Missing SPS/PPS/VPS for video codecs

## Decision-Making Framework

### When Choosing Repair Strategy

1. Start with least destructive (remux) before transcoding
2. Preserve original codecs and parameters when possible
3. Use reference file structure as template, not content replacement
4. Validate output quality before claiming success
5. Try multiple techniques - first success wins

### When Handling Errors

1. Log detailed error context (file paths, FFmpeg output)
2. Don't fail silently - always inform user of issues
3. Clean up temporary files even on failure
4. Provide actionable error messages
5. Continue to next technique on failure (in master script)

### When Making Breaking Changes

1. Update version number in Dockerfile
2. Document migration path in README
3. Consider backward compatibility
4. Update all platform wrappers (both .bat and .sh)
5. Test on all platforms before merging

## File Organization

```
mp4-recovery-toolkit/
├── mp4_recovery_master.py       # Main orchestration script
├── mp4_info.py                  # File analysis tool
├── recover.sh / recover.bat     # Platform wrappers
├── Dockerfile                   # Container definition
├── requirements.txt             # Python dependencies (currently empty)
├── recovery_techniques/         # 17 repair technique modules
├── README.md                    # User documentation
├── TODO.md                      # Future roadmap
├── CODE_REVIEW_FINDINGS.md      # Known issues
└── CONTRIBUTING.md              # Contribution guidelines
```

## Important Commands

```bash
# Build Docker image
docker build -t mp4-recovery-toolkit .

# Repair file
./recover.sh repair input.mp4 reference.mp4 output.mp4

# Analyze file
./recover.sh info video.mp4 --detailed

# Batch processing
./recover.sh batch /input/dir reference.mp4 /output/dir

# List techniques
./recover.sh --list
```

## Dependencies & Versions

- Python: 3.9.18 (pinned in Dockerfile)
- FFmpeg: 4.3.* (pinned in Dockerfile)
- Docker: Any recent version
- OS: Windows 10+, Linux (any modern distro), macOS 10.14+

## Future Direction

The long-term vision includes:

1. **libmp4repair_core**: C/C++ library for low-level BMFF atom manipulation
2. **Python Bindings**: Expose C/C++ functions via ctypes/pybind11
3. **GUI Wrapper**: Tkinter/PyQt/web-based interface
4. **Enhanced Validation**: Deep quality checks on repaired output
5. **Configuration System**: User-customizable repair strategies
6. **Parallel Processing**: Concurrent batch file processing

## Context for AI Assistants

When working on this project:

- **Prioritize security**: Validate all inputs, avoid command injection
- **Maintain cross-platform compatibility**: Test Windows and Unix paths
- **Keep it simple**: Standard library only unless absolutely necessary
- **Document thoroughly**: Complex FFmpeg operations need explanation
- **Validate outputs**: Don't trust exit codes alone
- **Think modular**: New features should be self-contained modules
- **Consider Docker-first**: Primary deployment method
- **Preserve user data**: Never destructively modify input files
