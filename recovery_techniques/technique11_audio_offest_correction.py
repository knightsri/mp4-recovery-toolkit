#!/usr/bin/env python3
"""
Audio Offset Correction Technique (Technique 11)

Attempts to correct audio/video synchronization issues by applying an offset.
This version will try a few common offsets. A more advanced version might
attempt to calculate the offset or allow user input.

Usage:
    python technique11_audio_offset_correction.py damaged.mp4 reference.mp4 output.mp4
"""

import os
import sys
import subprocess
import shutil
import logging
import argparse
import json # For ffprobe
from typing import List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mp4_recovery_technique11')

FFMPEG_CMD = 'ffmpeg'
FFPROBE_CMD = 'ffprobe'

# Define a list of common offsets to try (in seconds)
# Positive values delay audio, negative values advance audio relative to video
# Or use itsoffset on video to achieve the opposite effect
COMMON_OFFSETS = [0.0, 0.1, -0.1, 0.25, -0.25, 0.5, -0.5, 1.0, -1.0]

def check_mp4_file(file_path: str) -> bool:
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return False
    try:
        cmd = [FFMPEG_CMD, '-v', 'error', '-i', file_path, '-f', 'null', '-']
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stderr.strip() == ''
    except Exception:
        return False

def repair_file(input_file: str, reference_file: str, output_file: str) -> bool:
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    temp_dir = os.path.join(os.path.dirname(output_file), f"{base_name}_technique11_temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    logger.info(f"Starting audio offset correction for {input_file}")

    # First, try a direct copy to see if the file is somewhat processable
    # This also gives us a base for applying offsets if the input is too broken for direct offset application
    initial_remux_path = os.path.join(temp_dir, "initial_remux.mp4")
    remux_cmd_initial = [
        FFMPEG_CMD, '-y', '-i', input_file, 
        '-c', 'copy', '-map', '0', # Try to copy all streams
        '-avoid_negative_ts', 'make_zero', # Try to fix negative timestamps
        '-fflags', '+genpts', # Generate PTS if missing
        '-loglevel', 'error', 
        initial_remux_path
    ]
    logger.info(f"Attempting initial remux: {' '.join(remux_cmd_initial)}")
    subprocess.run(remux_cmd_initial, check=False)

    source_for_offset = input_file
    if os.path.exists(initial_remux_path) and os.path.getsize(initial_remux_path) > 1000:
        logger.info("Using initially remuxed file as source for offset attempts.")
        source_for_offset = initial_remux_path
    else:
        logger.warning("Initial remux failed or produced tiny file. Using original damaged file for offset attempts.")


    for i, offset in enumerate(COMMON_OFFSETS):
        attempt_output_file = os.path.join(temp_dir, f"offset_attempt_{i}.mp4")
        if os.path.exists(attempt_output_file):
            os.remove(attempt_output_file)

        # Apply offset: itsoffset on the audio input, or video input for opposite effect
        # Here, we'll apply to audio. A positive offset delays audio.
        # If using filter: -filter_complex "[0:a]asetpts=PTS+{offset}/TB[a_offsetted]" -map "[a_offsetted]"
        # Simpler with itsoffset (input option):
        
        # We need to know which input is audio. Let's assume the first audio stream.
        # This is simplified. A robust solution would use ffprobe to identify audio streams.
        
        offset_cmd = [
            FFMPEG_CMD, '-y',
            '-i', source_for_offset, # Video input
            '-itsoffset', str(offset), '-i', source_for_offset, # Audio input, offset
            '-c:v', 'copy',
            '-c:a', 'aac', # Re-encoding audio might be necessary withasetpts, but copy with itsoffset should work
            '-map', '0:v:0?', # Map first video stream from first input
            '-map', '1:a:0?', # Map first audio stream from second (offset) input
            '-avoid_negative_ts', 'make_zero',
            '-movflags', '+faststart',
            '-loglevel', 'error',
            attempt_output_file
        ]
        # A slightly safer way, trying to preserve original audio codec if possible and handling missing streams
        # This requires ffprobe to determine stream layout or making assumptions
        # For simplicity in this example, we use the above.
        # A more robust command for general cases:
        # ffmpeg -i input.mp4 -itsoffset <offset_seconds> -i input.mp4 \
        # -map 0:v? -map 1:a? -c:v copy -c:a copy output.mp4

        logger.info(f"Attempting offset {offset}s for audio: {' '.join(offset_cmd)}")
        try:
            result = subprocess.run(offset_cmd, check=True, capture_output=True, text=True)
            if result.returncode == 0 and check_mp4_file(attempt_output_file):
                logger.info(f"Offset {offset}s attempt successful. Output at {attempt_output_file}")
                shutil.copy2(attempt_output_file, output_file)
                logger.info(f"Copied successful result to {output_file}")
                if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
                return True
            else:
                logger.warning(f"Offset {offset}s attempt produced invalid or no file. Stderr: {result.stderr.strip()}")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Offset {offset}s command failed. Stderr: {e.stderr.strip()}")
        except Exception as e_gen:
            logger.error(f"General error during offset {offset}s: {e_gen}")


    logger.error("All audio offset attempts failed.")
    if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
    return False

def main():
    parser = argparse.ArgumentParser(description='Audio Offset Correction MP4 Repair Technique 11')
    parser.add_argument('input_file', help='Path to the damaged MP4 file')
    parser.add_argument('reference_file', help='Path to a working reference MP4 file (not directly used in this version)')
    parser.add_argument('output_file', help='Path where the repaired file will be saved')
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        logger.error(f"Input file not found: {args.input_file}")
        sys.exit(1)

    if repair_file(args.input_file, args.reference_file, args.output_file):
        logger.info("Audio Offset Correction completed successfully.")
        sys.exit(0)
    else:
        logger.error("Audio Offset Correction failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()