# MP4 Recovery Toolkit: Project Roadmap & Future Features

This project aims to be a comprehensive suite for repairing corrupted MP4 files. The current Python framework orchestrates various repair techniques, primarily leveraging FFmpeg. The long-term vision includes developing a core C/C++ library for deep, low-level atom manipulation, callable from Python.

## I. Core Python Framework Enhancements

1.  **Advanced Output Validation (`mp4_recovery_master.py`)**
    * [ ] **Implement Comprehensive `is_output_truly_valid` function:**
        * [ ] Compare output duration against reference (with tolerance).
        * [ ] Compare output file size against reference and original (with tolerance, considering if re-encoding occurred).
        * [ ] Verify presence and basic parameters of video/audio streams (codec, resolution, sample rate) against reference.
        * [ ] Check for excessive errors reported by `ffmpeg -v error -i output.mp4 -f null -`.
        * [ ] (Optional) Decode sample frames/audio segments to check for playability.
    * [ ] Ensure all technique scripts use a robust self-validation check before exiting successfully.
    * [ ] Allow `mp4_recovery_master.py` to continue to the next technique if a prior technique "succeeds" (exit 0) but fails the `is_output_truly_valid` check.

2.  **Enhanced Logging & Reporting (`mp4_recovery_master.py` & all techniques)**
    * [ ] Standardize logging format across all technique scripts.
    * [ ] Introduce different log levels (DEBUG, INFO, WARNING, ERROR) configurable via CLI.
    * [ ] Option for a consolidated HTML or JSON report summarizing which techniques were tried, their success/failure, ffprobe output of repaired files, and validation results.
    * [ ] Verbose mode for more detailed FFmpeg/script output.

3.  **User Experience & Configuration (`recover.bat`, `mp4_recovery_master.py`)**
    * [ ] Configuration file (e.g., `config.ini` or `config.json`) for:
        * Paths to FFmpeg/FFprobe (if not in system PATH and not using Docker).
        * Default parameters for `is_output_truly_valid` (e.g., duration tolerance factors).
        * Enable/disable specific techniques by default or define a custom order.
    * [ ] Interactive mode (CLI): Allow user to select techniques or provide input for certain repairs (e.g., A/V offset value if auto-detection is ambiguous).
    * [ ] GUI Wrapper (Major Future Goal): A simple cross-platform GUI (e.g., Tkinter, PyQt, Kivy, or web-based with Eel/Flask/FastAPI) to make the tool more accessible.

4.  **Modularity & Extensibility**
    * [ ] Create a shared Python utility module (`mp4_utils.py`?) for common functions like `get_media_info`, `is_output_truly_valid` (or its core components), `run_ffmpeg_command`, etc., to be used by technique scripts and the master script.
    * [ ] Refine the technique plugin system to make adding new Python or C/C++ backed techniques easier (e.g., auto-discovery of technique scripts).

## II. Development of Core C/C++ Repair Library (`libmp4repair_core`)

This is the most significant long-term effort, aiming to replace conceptual Python techniques with robust, performant C/C++ implementations.

1.  **Project Setup (C/C++)**
    * [ ] Choose C or C++ (C++ recommended for managing complexity with classes).
    * [ ] Set up a build system (CMake recommended for cross-platform compatibility).
    * [ ] Define a clear C API for Python bindings (even if primarily used by C++ internally).

2.  **BMFF Atom Parsing Engine (C/C++)**
    * [ ] Implement robust parsing for all common ISO BMFF atoms and FullBoxes (size, type, version, flags).
    * [ ] Handle 32-bit and 64-bit atom sizes correctly.
    * [ ] Build an in-memory tree representation of the MP4 file structure.
    * [ ] Develop parsers for the *payloads* of critical atoms:
        * [ ] `ftyp`
        * [ ] `mvhd`, `tkhd`, `mdhd` (timescales, durations, track IDs, matrices, language, etc.)
        * [ ] `hdlr`
        * [ ] `stbl` (Sample Table Box - this is the most complex and critical)
            * [ ] `stsd` (Sample Description Box - including parsing `avcC` for H.264, `hvcC` for HEVC, `esds` for AAC, etc.)
            * [ ] `stts` (Time-to-Sample Box)
            * [ ] `ctts` (Composition Time-to-Sample Box - for B-frames)
            * [ ] `stsc` (Sample-to-Chunk Box)
            * [ ] `stsz` / `stz2` (Sample Size Box)
            * [ ] `stco` / `co64` (Chunk Offset Box)
            * [ ] `stss` / `sync` (Sync Sample Box - for keyframes)
        * [ ] `elst` (Edit List Box)
        * [ ] `free`, `skip`, `wide` (Handle and preserve/recreate as needed)
        * [ ] `udta`, `meta` (and their sub-atoms like `ilst` for iTunes tags)

3.  **Structural Validation Engine (C/C++)**
    * [ ] Implement functions to validate the parsed atom tree:
        * Atom size consistency (children fit within parent, atoms fit within file).
        * Presence of mandatory atoms for a playable file.
        * `stco`/`co64` offsets point within `mdat` bounds and are ordered correctly.
        * Consistency between `stsz` sample counts, `stts` duration entries, and `stsc` chunking.
        * Cross-track consistency (e.g., overall movie duration vs. sum of track durations, considering edits).
        * `stsd` entries match the actual codec type found in `mdat`.

4.  **Repair Algorithms (C/C++) - Replacing Conceptual Python Techniques**
    * [ ] **True Atom Structure Repair (replaces/enhances current Technique 5 & 16/17 Python parts):**
        * [ ] Correct invalid atom sizes based on content or sibling atoms.
        * [ ] Remove orphan atoms or atoms with zero valid children (if safe).
        * [ ] Re-order atoms (e.g., `moov` before `mdat`), meticulously updating all affected chunk offsets in `stco`/`co64`.
    * [ ] **MOOV Atom Reconstruction (replaces/enhances current Technique 6 Python part):**
        * [ ] Use reference file's `moov` for track structure, codecs, timescales as a template.
        * [ ] Implement robust elementary stream parsing (H.264/HEVC NAL units, AAC ADTS/LATM frames, etc.) from the `mdat` of the damaged file.
        * [ ] Rebuild `stsz` (sample sizes) from scanned media data.
        * [ ] Rebuild `stco`/`co64` (chunk offsets) based on new `mdat` layout and scanned samples.
        * [ ] Rebuild `stts` (sample durations) using reference frame rate or by analyzing NAL unit types / audio frame headers.
        * [ ] Rebuild `stsc` (sample to chunk), possibly starting with 1 sample per chunk.
        * [ ] Reconstruct `stsd` using info from reference and potentially from SPS/PPS/VPS NAL units found at the start of the `mdat`.
    * [ ] **Frame-by-Frame Rebuild Logic (replaces/enhances Technique 7 Python part):**
        * [ ] More advanced `mdat` scanning to identify individual decodable frames/samples and their types (I, P, B for video).
        * [ ] Attempt to re-order out-of-order frames if DTS/PTS can be recovered or inferred.
        * [ ] Write a new MP4 by constructing atoms frame by frame, calculating all table entries.
    * [ ] **SPS/PPS/VPS Handling (enhances Technique 12):**
        * [ ] Detect missing/corrupt `avcC`/`hvcC`/`vpcC` in `stsd`.
        * [ ] Extract parameter sets from reference file's `stsd` or from the start of the `mdat` stream.
        * [ ] Rebuild/inject correct parameter set atoms into the `stsd`.

5.  **Atom Writing Engine (C/C++)**
    * [ ] Implement functions to serialize the (repaired) in-memory atom tree back into a valid MP4 file stream, correctly calculating all parent atom sizes based on their children.

6.  **Python Bindings (`ctypes`, `pybind11`, or `SWIG`)**
    * [ ] Expose key C/C++ repair functions to Python (e.g., `repair_file_with_strategy_X`).
    * [ ] Handle data marshalling between Python (e.g., file paths as strings) and C/C++ (e.g., `const char*`, data structures representing atoms or file state).

## III. Enhancements to Specific FFmpeg-Based Techniques

While the C/C++ core is developed, existing FFmpeg techniques can be improved:

1.  **Technique 2 (Advanced FFmpeg), 10 (Hybrid FFmpeg):**
    * [ ] Dynamically generate more FFmpeg command variations based on `ffprobe` analysis of the corrupted file and reference file (e.g., if audio codec is Opus, use relevant Opus flags; if HEVC, use HEVC-specific bitstream filters).
    * [ ] Parameterize common options (e.g., CRF values, presets for re-encoding steps) in a config file or via CLI.
2.  **Technique 3 & 4 (Raw Stream Extraction):**
    * [ ] Add support for more video codecs (H.265/HEVC, VP9) and audio codecs (Opus, FLAC).
    * [ ] Improve heuristics for identifying start/end of raw streams if `mdat` is not clearly defined or is interspersed with other data.
3.  **Technique 8 (Multi-Segment Repair):**
    * [ ] More intelligent segment splitting (e.g., use `ffprobe` to try to identify keyframe intervals and split on those boundaries if possible).
    * [ ] More robust validation of individual repaired segments before concatenation, using the advanced `is_output_truly_valid` logic.
4.  **Technique 9 (Metadata Transplant):**
    * [ ] More granular metadata copying (e.g., specific track metadata like handler names, color space information from `colr` atom, chapter markers if present in reference).
5.  **Technique 11 (Audio Offset):**
    * [ ] Attempt to auto-detect A/V sync issues using cross-correlation of audio/video activity or by analyzing embedded timestamps (if partially readable and trustworthy).
    * [ ] Allow user to specify offset in milliseconds or frames if auto-detection fails.
6.  **Technique 13 (VFR to CFR):**
    * [ ] Offer options for interpolation methods when converting frame rates (e.g., frame dropping, blending).
    * [ ] Detect VFR source more reliably using `ffprobe` and only apply if necessary.

## IV. Testing and Documentation

1.  **Comprehensive Test Suite:**
    * [ ] Curate a diverse set of corrupted MP4 files (different codecs, various corruption types: missing moov, bad offsets, truncated mdat, header corruption, etc., from different recording sources).
    * [ ] Automated tests for each technique, comparing output against expected results (if known) or validating output quality using a scoring system based on `is_output_truly_valid` metrics.
2.  **Detailed Documentation:**
    * [ ] Update `README.md` with detailed explanations of each technique's methodology, specific FFmpeg commands used (if applicable), limitations, and when it's most effective.
    * [ ] Document the C/C++ library API if/when developed.
    * [ ] User guides for `recover.bat` and `mp4_recovery_master.py`, including troubleshooting common issues.
    * [ ] Contribution guidelines for others who might want to help extend the toolkit.

## V. Docker Enhancements

1.  **Smaller Image (Multi-stage builds):** If C/C++ components are compiled, use multi-stage Docker builds to keep the final image lean, containing only runtime dependencies and the Python scripts.
2.  **Non-Root User:** Configure the Docker container to run processes as a non-root user for better security practices.
3.  **Platform Builds:** Consider providing Docker images for different architectures (e.g., amd64, arm64) if there's demand.