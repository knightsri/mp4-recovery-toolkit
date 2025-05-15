#!/usr/bin/env python3
"""
Multi-Segment Repair Technique (Technique 8)

This technique splits the damaged MP4 into segments, attempts to repair each,
and then concatenates the valid segments.

Usage:
    python technique8_multi_segment_repair.py damaged.mp4 reference.mp4 output.mp4
"""

import os
import sys
import subprocess
import shutil
import logging
import argparse
import glob

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mp4_recovery_technique8')

FFMPEG_CMD = 'ffmpeg'
FFPROBE_CMD = 'ffprobe'
SEGMENT_DURATION = 10  # seconds

def check_mp4_file(file_path: str) -> bool:
    """Check if an MP4 file is valid using FFmpeg."""
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
    temp_dir = os.path.join(os.path.dirname(output_file), f"{base_name}_technique8_temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    success = False
    repaired_segments_paths = []

    try:
        logger.info(f"Starting multi-segment repair for {input_file}")

        # 1. Split into segments
        segment_pattern = os.path.join(temp_dir, f"{base_name}_segment_%03d.mp4")
        split_cmd = [
            FFMPEG_CMD, '-i', input_file,
            '-c', 'copy', '-map', '0', '-segment_time', str(SEGMENT_DURATION),
            '-f', 'segment', '-reset_timestamps', '1',
            '-loglevel', 'error',
            segment_pattern
        ]
        logger.info(f"Splitting into segments: {' '.join(split_cmd)}")
        subprocess.run(split_cmd, check=False) # Don't check, as input might be corrupt

        segments = sorted(glob.glob(os.path.join(temp_dir, f"{base_name}_segment_*.mp4")))
        if not segments:
            logger.error("Failed to create any segments.")
            return False
        
        logger.info(f"Created {len(segments)} segments.")

        # 2. Attempt to repair/validate each segment
        for i, segment_path in enumerate(segments):
            repaired_segment_path = os.path.join(temp_dir, f"repaired_segment_{i:03d}.mp4")
            # A simple copy can often fix minor segment issues or validate them
            repair_cmd = [
                FFMPEG_CMD, '-i', segment_path, '-c', 'copy',
                '-loglevel', 'error',
                repaired_segment_path
            ]
            logger.info(f"Attempting to validate/repair segment: {segment_path}")
            result = subprocess.run(repair_cmd, check=False)
            
            if result.returncode == 0 and check_mp4_file(repaired_segment_path):
                logger.info(f"Segment {segment_path} repaired successfully to {repaired_segment_path}")
                repaired_segments_paths.append(repaired_segment_path)
            else:
                logger.warning(f"Failed to repair segment {segment_path} or it's invalid.")

        if not repaired_segments_paths:
            logger.error("No segments could be repaired.")
            return False

        logger.info(f"Successfully repaired {len(repaired_segments_paths)} segments.")

        # 3. Create a file list for concatenation
        concat_list_path = os.path.join(temp_dir, "concat_list.txt")
        with open(concat_list_path, 'w') as f:
            for seg_path in repaired_segments_paths:
                f.write(f"file '{os.path.abspath(seg_path)}'\n") # Use abspath for safety

        # 4. Concatenate repaired segments
        concat_cmd = [
            FFMPEG_CMD, '-f', 'concat', '-safe', '0', '-i', concat_list_path,
            '-c', 'copy', '-loglevel', 'error', output_file
        ]
        logger.info(f"Concatenating repaired segments: {' '.join(concat_cmd)}")
        result = subprocess.run(concat_cmd, check=True)

        if result.returncode == 0 and check_mp4_file(output_file):
            logger.info(f"File successfully repaired and concatenated to {output_file}")
            success = True
        else:
            logger.error(f"Failed to concatenate segments. FFmpeg stderr: {result.stderr}")
            if os.path.exists(output_file): os.remove(output_file) # Clean up failed attempt

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg command failed: {e.cmd}, stderr: {e.stderr}")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temp directory: {temp_dir}")
            
    return success

def main():
    parser = argparse.ArgumentParser(description='Multi-Segment MP4 Repair Technique 8')
    parser.add_argument('input_file', help='Path to the damaged MP4 file')
    parser.add_argument('reference_file', help='Path to a working reference MP4 file (used for guidance, not directly in this script yet)')
    parser.add_argument('output_file', help='Path where the repaired file will be saved')
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        logger.error(f"Input file not found: {args.input_file}")
        sys.exit(1)
    # Reference file not strictly used in this simple version but kept for consistency

    if repair_file(args.input_file, args.reference_file, args.output_file):
        logger.info("Multi-Segment Repair completed successfully.")
        sys.exit(0)
    else:
        logger.error("Multi-Segment Repair failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()