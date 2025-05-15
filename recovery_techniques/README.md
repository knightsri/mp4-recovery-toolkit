# MP4 Recovery Suite

This folder contains specialized recovery techniques for damaged MP4 files.
The scripts primarily leverage FFmpeg and FFprobe for their operations.

## Available Recovery Techniques

Each technique attempts to repair a corrupted MP4 file (`damaged.mp4`), potentially using a `reference.mp4` (a healthy file recorded with the same device/settings) for guidance, and outputs the result to `output.mp4`.

1.  **`technique1_standard_remux.py`** - Basic stream extraction and remuxing using FFmpeg's stream copy (`-c copy`). Aims to fix container-level issues without re-encoding.
2.  **`technique2_advanced_ffmpeg.py`** - Employs multiple advanced FFmpeg parameter combinations, trying various error handling and stream processing options to recover data.
3.  **`technique3_raw_nal_extraction.py`** - Focuses on extracting raw H.264 Network Abstraction Layer (NAL) units from the video stream, which can then be remuxed into a new MP4 container.
4.  **`technique4_raw_aac_extraction.py`** - Extracts raw Advanced Audio Coding (AAC) frames from the audio stream, suitable for remuxing, potentially with video from other techniques.
5.  **`technique5_atom_structure_repair.py`** - (Conceptual) Aims to parse the MP4's atom/box structure, identify inconsistencies (e.g., incorrect sizes, missing atoms), and attempt to repair them. Requires a detailed MP4/ISO BMFF parsing library.
6.  **`technique6_moov_atom_reconstruction.py`** - (Conceptual) Focuses on rebuilding the critical `moov` atom (which contains index and metadata) if it's missing or severely corrupted, often using a reference file to guide the reconstruction of tracks, sample tables, etc. Requires a detailed MP4/ISO BMFF parsing and writing library.
7.  **`technique7_frame_by_frame.py`** - (Conceptual) Involves extracting individual decodable frames (video) and audio packets, and then attempting to reassemble them into a new, valid MP4 sequence with correct timing. Very complex.
8.  **`technique8_multi_segment_repair.py`** - Splits the damaged file into smaller time-based segments. It then attempts to repair or validate each segment individually and concatenates the successfully processed segments.
9.  **`technique9_metadata_transplant.py`** - Extracts raw video and audio streams from the damaged file and then remuxes them into a new MP4 container, applying metadata (like track layout, timescales, duration, language tags) derived from the `reference.mp4`.
10. **`technique10_hybrid_approach.py`** - Executes a predefined series of FFmpeg command chains, where each chain combines different repair flags, re-encoding strategies, or stream manipulation steps to tackle complex corruptions.
11. **`technique11_audio_offset_correction.py`** - Addresses audio/video synchronization problems by applying various common time offsets to the audio stream (or video) using FFmpeg, attempting to find a corrected sync.
12. **`technique12_sps_pps_injection.py`** - (Simplified FFmpeg approach) If H.264 Sequence Parameter Sets (SPS) or Picture Parameter Sets (PPS) are missing or corrupt in the video stream (often stored in the `avcC` box), this technique attempts to extract them from a reference file and prepend them to an extracted raw H.264 stream before remuxing.
13. **`technique13_vfr_to_cfr_fix.py`** - Converts videos that might have Variable Frame Rate (VFR) issues or erratic timestamps to a Constant Frame Rate (CFR) using FFmpeg. This involves re-encoding the video stream and can help stabilize playback. The target frame rate is ideally derived from the reference file.
14. **`technique14_recover_from_raw_disk_image.py`** - (Conceptual Placeholder) Represents an advanced forensic technique. It would involve scanning a raw disk image (not a file) for MP4 file signatures (like 'ftyp', 'moov') to carve out potential file fragments. This does not directly produce a playable MP4 but rather data chunks for further analysis.
15. **`technique15_ffprobe_deep_analysis_repair.py`** - (Conceptual Placeholder) Involves using `ffprobe` to perform a deep analysis of the damaged file (streams, packets, errors). Based on the detected issues, it would heuristically apply specific FFmpeg repair commands.
16. **`technique16_bmff_atom_editor.py`** - (Conceptual Placeholder) Represents a low-level ISO Base Media File Format (BMFF) atom/box editor. This would allow programmatic parsing, inspection, modification (e.g., fixing incorrect atom sizes, rebuilding sample tables), and rewriting of the MP4 file structure. This is the foundation for robust implementations of techniques 5 and 6.

## Master Recovery Script

-   **`mp4_recovery_master.py`** - Orchestrates the recovery process. It iterates through all defined techniques (or a specific one if requested) in sequence, attempting to repair the damaged MP4 file until one of the techniques succeeds.

## Batch Script

-   **`recover.bat`** (for Windows) - A convenience batch script that wraps `mp4_recovery_master.py`. It handles basic environment checks (Python availability) and argument parsing, allowing users to run the recovery process easily from the command line.

## Usage

All technique scripts are generally located in the `recovery_techniques/` subdirectory.

**Using the Master Script (Recommended):**

The master script will try all techniques in order until one is successful.

```bash
python mp4_recovery_master.py damaged.mp4 reference.mp4 output.mp4
```

Or run individual techniques directly:

```bash
python techniques/standard_remux.py damaged.mp4 reference.mp4 output.mp4
```

## Requirements

- Python 3.6+
- FFmpeg and FFprobe
- Additional Python packages (see requirements.txt)