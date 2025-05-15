#!/usr/bin/env python3
"""
Raw AAC Extraction Recovery Technique

This script attempts to recover damaged MP4 files by extracting raw AAC audio frames,
filtering them, and rebuilding a valid AAC stream. It then combines with video if available.

Usage:
    python technique4_raw_aac_extraction.py damaged.mp4 reference.mp4 output.mp4
"""

import os
import sys
import subprocess
import tempfile
import logging
import shutil
import struct
from typing import List, Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('technique4_raw_aac_extraction')

# AAC ADTS Header constants
ADTS_SYNC_WORD = 0xFFF0  # 12 bits

def run_command(cmd: List[str]) -> Tuple[bool, str, str]:
    """Run a command and return success status and output."""
    try:
        logger.debug(f"Running command: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        stdout, stderr = process.communicate()
        success = process.returncode == 0
        return success, stdout, stderr
    except Exception as e:
        logger.error(f"Command failed: {e}")
        return False, "", str(e)

def check_ffmpeg_available() -> bool:
    """Check if FFmpeg is available."""
    success, _, _ = run_command(['ffmpeg', '-version'])
    return success

def extract_raw_audio_data(input_file: str, temp_dir: str) -> Optional[str]:
    """Extract raw audio data from the damaged MP4."""
    raw_audio_path = os.path.join(temp_dir, "raw_audio.bin")
    
    # First try FFmpeg to extract the audio stream
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-vn',  # No video
        '-c:a', 'copy',  # Copy without re-encoding
        '-f', 'data',  # Raw data format
        raw_audio_path
    ]
    
    success, _, stderr = run_command(cmd)
    
    if not success or not os.path.exists(raw_audio_path) or os.path.getsize(raw_audio_path) == 0:
        logger.warning("Failed to extract audio with FFmpeg, trying binary extraction...")
        
        # If FFmpeg fails, try binary extraction of AAC frames
        try:
            with open(input_file, 'rb') as f_in, open(raw_audio_path, 'wb') as f_out:
                # Read the file in chunks
                chunk_size = 1024 * 1024  # 1MB chunks
                data = f_in.read(chunk_size)
                
                # Variables to track potential AAC frames
                sync_count = 0
                total_bytes = 0
                
                while data:
                    # Process chunk byte by byte
                    for i in range(len(data) - 1):
                        # Check for ADTS sync word (0xFFF0 to 0xFFFF)
                        # First 12 bits should be 1's
                        if (data[i] == 0xFF) and ((data[i+1] & 0xF0) == 0xF0):
                            # Found potential AAC frame header
                            if i + 7 <= len(data):  # ADTS header is 7 bytes
                                # Extract frame length from header
                                frame_length = ((data[i+3] & 0x03) << 11) | (data[i+4] << 3) | ((data[i+5] & 0xE0) >> 5)
                                
                                if frame_length > 7 and i + frame_length <= len(data):
                                    # Write the entire frame
                                    f_out.write(data[i:i+frame_length])
                                    total_bytes += frame_length
                                    sync_count += 1
                    
                    # Read next chunk
                    data = f_in.read(chunk_size)
                
                logger.info(f"Binary extraction found {sync_count} potential AAC frames ({total_bytes} bytes)")
                
                if total_bytes == 0:
                    return None
                
        except Exception as e:
            logger.error(f"Binary extraction failed: {e}")
            return None
    
    # Check if we have any data
    if os.path.exists(raw_audio_path) and os.path.getsize(raw_audio_path) > 0:
        return raw_audio_path
    else:
        return None

def is_valid_aac_frame(data: bytes, offset: int) -> Tuple[bool, int]:
    """
    Check if data at offset is a valid AAC frame and return its length.
    Returns: (is_valid, frame_length)
    """
    # Need at least 7 bytes for ADTS header
    if offset + 7 > len(data):
        return False, 0
    
    # Check sync word (first 12 bits must be 1's)
    if data[offset] != 0xFF or (data[offset+1] & 0xF0) != 0xF0:
        return False, 0
    
    # Extract frame length from header
    frame_length = ((data[offset+3] & 0x03) << 11) | (data[offset+4] << 3) | ((data[offset+5] & 0xE0) >> 5)
    
    # Validate frame length
    if frame_length < 7 or offset + frame_length > len(data):
        return False, 0
    
    # For stricter validation, check:
    # 1. Profile (2 bits at data[offset+2] >> 6)
    # 2. Sampling frequency (4 bits at ((data[offset+2] & 0x3C) >> 2))
    # 3. Channel config (3 bits at ((data[offset+2] & 0x01) << 2) | (data[offset+3] >> 6))
    
    return True, frame_length

def filter_and_rebuild_aac(raw_data_path: str, temp_dir: str) -> Optional[str]:
    """Filter raw data and rebuild a valid AAC stream."""
    filtered_path = os.path.join(temp_dir, "filtered.aac")
    
    try:
        # Read the raw data
        with open(raw_data_path, 'rb') as f:
            data = f.read()
        
        # Scan for valid AAC frames
        offset = 0
        valid_frames = []
        
        while offset < len(data):
            is_valid, frame_length = is_valid_aac_frame(data, offset)
            
            if is_valid:
                valid_frames.append((offset, frame_length))
                offset += frame_length
            else:
                offset += 1
        
        logger.info(f"Found {len(valid_frames)} valid AAC frames")
        
        # Write valid frames to new file
        with open(filtered_path, 'wb') as f_out:
            for frame_offset, frame_length in valid_frames:
                f_out.write(data[frame_offset:frame_offset+frame_length])
        
        # Check if we have any data
        if os.path.getsize(filtered_path) > 0:
            return filtered_path
        else:
            return None
            
    except Exception as e:
        logger.error(f"Error filtering AAC data: {e}")
        return None

def extract_video_stream(input_file: str, temp_dir: str) -> Optional[str]:
    """Try to extract video stream from the damaged file."""
    video_path = os.path.join(temp_dir, "video.h264")
    
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-an',  # No audio
        '-c:v', 'copy',  # Copy without re-encoding
        '-f', 'h264',  # Raw H.264 format
        video_path
    ]
    
    success, _, _ = run_command(cmd)
    
    if success and os.path.exists(video_path) and os.path.getsize(video_path) > 0:
        return video_path
    else:
        return None

def create_output_with_streams(audio_path: str, video_path: Optional[str], output_file: str) -> bool:
    """Create output MP4 with recovered streams."""
    cmd = ['ffmpeg']
    
    # Add video if available
    if video_path:
        cmd.extend([
            '-i', video_path,
            '-i', audio_path,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-map', '0:v',
            '-map', '1:a',
            '-shortest',
            output_file
        ])
    else:
        # Audio only
        cmd.extend([
            '-i', audio_path,
            '-c:a', 'aac',
            output_file
        ])
    
    success, _, stderr = run_command(cmd)
    return success

def main(input_file: str, reference_file: str, output_file: str) -> bool:
    """Main function to recover AAC audio from damaged MP4."""
    if not check_ffmpeg_available():
        logger.error("FFmpeg is required but not found")
        return False
    
    try:
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info("Starting raw AAC extraction...")
            
            # Step 1: Extract raw audio data
            raw_audio_path = extract_raw_audio_data(input_file, temp_dir)
            if not raw_audio_path:
                logger.error("Failed to extract any audio data")
                return False
            
            # Step 2: Filter and rebuild AAC stream
            filtered_aac_path = filter_and_rebuild_aac(raw_audio_path, temp_dir)
            if not filtered_aac_path:
                logger.error("Failed to create valid AAC stream")
                return False
            
            # Step 3: Try to extract video
            video_path = extract_video_stream(input_file, temp_dir)
            if video_path:
                logger.info("Video stream extracted successfully")
            else:
                logger.warning("No valid video stream found, creating audio-only output")
            
            # Step 4: Create output file
            if create_output_with_streams(filtered_aac_path, video_path, output_file):
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
        print("Usage: python technique4_raw_aac_extraction.py damaged.mp4 reference.mp4 output.mp4")
        sys.exit(1)
    
    input_file = sys.argv[1]
    reference_file = sys.argv[2]
    output_file = sys.argv[3]
    
    if main(input_file, reference_file, output_file):
        sys.exit(0)
    else:
        sys.exit(1)