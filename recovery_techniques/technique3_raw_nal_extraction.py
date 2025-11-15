#!/usr/bin/env python3
"""
Raw NAL Unit Extraction Recovery Technique (Technique 3)

This script attempts to recover damaged MP4 files by extracting raw H.264 NAL units
from the video stream, filtering them, and rebuilding a valid H.264 stream.
It then remuxes the stream into a new MP4 container.

Usage:
    python technique3_raw_nal_extraction.py damaged.mp4 reference.mp4 output.mp4
"""

import os
import sys
import subprocess
import tempfile
import logging
import shutil
from typing import List, Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('technique3_raw_nal_extraction')

# H.264 NAL Unit Type Constants
NAL_UNIT_TYPE_SLICE = 1
NAL_UNIT_TYPE_DPA = 2
NAL_UNIT_TYPE_DPB = 3
NAL_UNIT_TYPE_DPC = 4
NAL_UNIT_TYPE_IDR = 5
NAL_UNIT_TYPE_SEI = 6
NAL_UNIT_TYPE_SPS = 7
NAL_UNIT_TYPE_PPS = 8
NAL_UNIT_TYPE_AUD = 9

# NAL Start Codes
NAL_START_CODE_3 = b'\x00\x00\x01'
NAL_START_CODE_4 = b'\x00\x00\x00\x01'


def run_command(cmd: List[str], timeout: int = 300) -> Tuple[bool, str, str]:
    """
    Run a command and return success status and output.

    Args:
        cmd: Command and arguments as list
        timeout: Maximum execution time in seconds

    Returns:
        Tuple of (success, stdout, stderr)
    """
    try:
        logger.debug(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False
        )
        success = result.returncode == 0
        return success, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s")
        return False, "", f"Timeout after {timeout}s"
    except Exception as e:
        logger.error(f"Command failed: {e}")
        return False, "", str(e)


def check_ffmpeg_available() -> bool:
    """Check if FFmpeg is available."""
    success, _, _ = run_command(['ffmpeg', '-version'], timeout=10)
    return success


def extract_raw_h264_stream(input_file: str, temp_dir: str) -> Optional[str]:
    """
    Extract raw H.264 stream from the damaged MP4.

    Args:
        input_file: Path to damaged MP4 file
        temp_dir: Temporary directory for intermediate files

    Returns:
        Path to extracted H.264 file, or None on failure
    """
    h264_path = os.path.join(temp_dir, "raw_video.h264")

    # Try to extract video stream with FFmpeg
    cmd = [
        'ffmpeg',
        '-y',  # Overwrite without asking
        '-i', input_file,
        '-an',  # No audio
        '-vcodec', 'copy',  # Copy without re-encoding
        '-bsf:v', 'h264_mp4toannexb',  # Convert to Annex B format
        '-f', 'h264',  # Raw H.264 format
        h264_path
    ]

    logger.info("Extracting raw H.264 stream with FFmpeg...")
    success, stdout, stderr = run_command(cmd)

    if success and os.path.exists(h264_path) and os.path.getsize(h264_path) > 1000:
        logger.info(f"Successfully extracted {os.path.getsize(h264_path)} bytes of H.264 data")
        return h264_path
    else:
        logger.warning("FFmpeg extraction failed or produced insufficient data")
        if stderr:
            logger.debug(f"FFmpeg stderr: {stderr}")

        # Try binary extraction as fallback
        return extract_nal_units_binary(input_file, temp_dir)


def extract_nal_units_binary(input_file: str, temp_dir: str) -> Optional[str]:
    """
    Binary extraction of NAL units from file by searching for start codes.

    Args:
        input_file: Path to damaged MP4 file
        temp_dir: Temporary directory for intermediate files

    Returns:
        Path to extracted NAL units file, or None on failure
    """
    h264_path = os.path.join(temp_dir, "binary_extracted.h264")

    logger.info("Attempting binary NAL unit extraction...")

    try:
        with open(input_file, 'rb') as f_in, open(h264_path, 'wb') as f_out:
            # Read file in chunks
            chunk_size = 1024 * 1024  # 1MB chunks
            nal_count = 0
            total_bytes = 0
            buffer = b''

            while True:
                chunk = f_in.read(chunk_size)
                if not chunk:
                    break

                buffer += chunk

                # Search for NAL start codes
                offset = 0
                while offset < len(buffer) - 4:
                    # Check for 4-byte start code
                    if buffer[offset:offset+4] == NAL_START_CODE_4:
                        # Find next start code to determine NAL unit length
                        next_start = find_next_start_code(buffer, offset + 4)
                        if next_start > 0:
                            nal_unit = buffer[offset:next_start]
                            f_out.write(nal_unit)
                            nal_count += 1
                            total_bytes += len(nal_unit)
                            offset = next_start
                        else:
                            offset += 4
                    # Check for 3-byte start code
                    elif buffer[offset:offset+3] == NAL_START_CODE_3:
                        next_start = find_next_start_code(buffer, offset + 3)
                        if next_start > 0:
                            nal_unit = buffer[offset:next_start]
                            f_out.write(nal_unit)
                            nal_count += 1
                            total_bytes += len(nal_unit)
                            offset = next_start
                        else:
                            offset += 3
                    else:
                        offset += 1

                # Keep last few bytes in buffer for next iteration
                buffer = buffer[max(0, len(buffer) - 1024):]

        logger.info(f"Binary extraction found {nal_count} NAL units ({total_bytes} bytes)")

        if total_bytes > 1000:
            return h264_path
        else:
            logger.warning("Binary extraction produced insufficient data")
            return None

    except Exception as e:
        logger.error(f"Binary extraction failed: {e}")
        return None


def find_next_start_code(buffer: bytes, start_offset: int) -> int:
    """
    Find the next NAL start code in buffer.

    Args:
        buffer: Byte buffer to search
        start_offset: Offset to start searching from

    Returns:
        Offset of next start code, or -1 if not found
    """
    offset = start_offset
    max_search = min(len(buffer), start_offset + 100000)  # Limit search distance

    while offset < max_search - 4:
        if buffer[offset:offset+4] == NAL_START_CODE_4:
            return offset
        elif buffer[offset:offset+3] == NAL_START_CODE_3:
            return offset
        offset += 1

    return -1


def get_nal_unit_type(nal_unit: bytes) -> int:
    """
    Extract NAL unit type from NAL unit data.

    Args:
        nal_unit: NAL unit bytes (including start code)

    Returns:
        NAL unit type (0-31)
    """
    # Skip start code
    if nal_unit[:4] == NAL_START_CODE_4:
        header_byte = nal_unit[4] if len(nal_unit) > 4 else 0
    elif nal_unit[:3] == NAL_START_CODE_3:
        header_byte = nal_unit[3] if len(nal_unit) > 3 else 0
    else:
        return 0

    # NAL unit type is in bits 0-4 of first byte after start code
    return header_byte & 0x1F


def validate_h264_stream(h264_path: str) -> bool:
    """
    Validate that H.264 stream has required parameter sets.

    Args:
        h264_path: Path to H.264 file

    Returns:
        True if stream appears valid
    """
    try:
        with open(h264_path, 'rb') as f:
            data = f.read(min(1024 * 1024, os.path.getsize(h264_path)))  # Read first 1MB

        has_sps = False
        has_pps = False
        has_idr = False

        offset = 0
        while offset < len(data) - 4:
            if data[offset:offset+4] == NAL_START_CODE_4:
                nal_type = data[offset+4] & 0x1F if offset+4 < len(data) else 0
                if nal_type == NAL_UNIT_TYPE_SPS:
                    has_sps = True
                elif nal_type == NAL_UNIT_TYPE_PPS:
                    has_pps = True
                elif nal_type == NAL_UNIT_TYPE_IDR:
                    has_idr = True
                offset += 4
            elif data[offset:offset+3] == NAL_START_CODE_3:
                nal_type = data[offset+3] & 0x1F if offset+3 < len(data) else 0
                if nal_type == NAL_UNIT_TYPE_SPS:
                    has_sps = True
                elif nal_type == NAL_UNIT_TYPE_PPS:
                    has_pps = True
                elif nal_type == NAL_UNIT_TYPE_IDR:
                    has_idr = True
                offset += 3
            else:
                offset += 1

        logger.info(f"Stream validation: SPS={has_sps}, PPS={has_pps}, IDR={has_idr}")
        return has_sps and has_pps

    except Exception as e:
        logger.error(f"Stream validation failed: {e}")
        return False


def extract_audio_stream(input_file: str, temp_dir: str) -> Optional[str]:
    """
    Try to extract audio stream from the damaged file.

    Args:
        input_file: Path to damaged MP4 file
        temp_dir: Temporary directory for intermediate files

    Returns:
        Path to extracted audio file, or None if no audio
    """
    audio_path = os.path.join(temp_dir, "audio.aac")

    cmd = [
        'ffmpeg',
        '-y',
        '-i', input_file,
        '-vn',  # No video
        '-acodec', 'copy',  # Copy without re-encoding
        audio_path
    ]

    logger.info("Attempting to extract audio stream...")
    success, _, _ = run_command(cmd)

    if success and os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000:
        logger.info("Audio stream extracted successfully")
        return audio_path
    else:
        logger.info("No valid audio stream found")
        return None


def remux_to_mp4(h264_path: str, audio_path: Optional[str], output_file: str,
                 reference_file: Optional[str] = None) -> bool:
    """
    Remux H.264 and audio streams into MP4 container.

    Args:
        h264_path: Path to H.264 file
        audio_path: Path to audio file (optional)
        output_file: Path for output MP4 file
        reference_file: Reference file for parameters (optional)

    Returns:
        True if remux successful
    """
    cmd = ['ffmpeg', '-y']

    # Add H.264 input
    cmd.extend(['-i', h264_path])

    # Add audio input if available
    if audio_path:
        cmd.extend(['-i', audio_path])

    # Video codec
    cmd.extend(['-c:v', 'copy'])

    # Audio codec
    if audio_path:
        cmd.extend(['-c:a', 'copy'])

    # Map streams
    cmd.extend(['-map', '0:v'])
    if audio_path:
        cmd.extend(['-map', '1:a'])

    # Output options
    cmd.extend([
        '-movflags', '+faststart',
        '-avoid_negative_ts', 'make_zero',
        output_file
    ])

    logger.info("Remuxing streams into MP4 container...")
    success, _, stderr = run_command(cmd)

    if success and os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
        logger.info(f"Successfully created output file: {output_file}")
        return True
    else:
        logger.error("Remux failed")
        if stderr:
            logger.debug(f"FFmpeg stderr: {stderr}")
        return False


def main(input_file: str, reference_file: str, output_file: str) -> bool:
    """
    Main function to recover video using raw NAL extraction.

    Args:
        input_file: Path to damaged MP4 file
        reference_file: Path to reference MP4 file
        output_file: Path for repaired output file

    Returns:
        True if recovery successful
    """
    if not check_ffmpeg_available():
        logger.error("FFmpeg is required but not found")
        return False

    try:
        # Create temporary directory
        with tempfile.TemporaryDirectory(prefix="technique3_") as temp_dir:
            logger.info("Starting raw NAL unit extraction...")

            # Step 1: Extract raw H.264 stream
            h264_path = extract_raw_h264_stream(input_file, temp_dir)
            if not h264_path:
                logger.error("Failed to extract H.264 stream")
                return False

            # Step 2: Validate H.264 stream
            if not validate_h264_stream(h264_path):
                logger.warning("H.264 stream may be incomplete (missing SPS/PPS)")
                # Continue anyway, FFmpeg may handle it

            # Step 3: Try to extract audio
            audio_path = extract_audio_stream(input_file, temp_dir)

            # Step 4: Remux into MP4
            if remux_to_mp4(h264_path, audio_path, output_file, reference_file):
                logger.info(f"Successfully created output file: {output_file}")
                return True
            else:
                logger.error("Failed to create output file")
                return False

    except Exception as e:
        logger.error(f"Recovery failed: {e}")
        return False


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python technique3_raw_nal_extraction.py damaged.mp4 reference.mp4 output.mp4")
        sys.exit(1)

    input_file = sys.argv[1]
    reference_file = sys.argv[2]
    output_file = sys.argv[3]

    if main(input_file, reference_file, output_file):
        sys.exit(0)
    else:
        sys.exit(1)
