#!/usr/bin/env python3
"""
Variable Frame Rate to Constant Frame Rate Fix (Technique 13)

Attempts to stabilize playback by converting to a constant frame rate,
potentially fixing issues related to erratic timestamps. This involves re-encoding.

Usage:
    python technique13_vfr_to_cfr_fix.py damaged.mp4 reference.mp4 output.mp4
"""

import os
import sys
import subprocess
import shutil
import logging
import argparse
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mp4_recovery_technique13')

FFMPEG_CMD = 'ffmpeg'
FFPROBE_CMD = 'ffprobe'

def check_mp4_file(file_path: str) -> bool:
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return False
    try:
        cmd = [FFMPEG_CMD, '-v', 'error', '-i', file_path, '-f', 'null', '-']
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stderr.strip() == ''
    except Exception:
        return False

def get_target_framerate(reference_file: str, default_fps: str = "30") -> str:
    """Get target framerate from reference file, or use default."""
    try:
        cmd = [
            FFPROBE_CMD, '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=avg_frame_rate', '-of', 'csv=p=0',
            reference_file
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        avg_frame_rate_str = result.stdout.strip()
        if '/' in avg_frame_rate_str:
            num, den = map(int, avg_frame_rate_str.split('/'))
            if den != 0:
                return str(num / den)
        elif float(avg_frame_rate_str) > 0:
             return avg_frame_rate_str
    except Exception as e:
        logger.warning(f"Could not determine framerate from reference: {e}. Using default {default_fps} fps.")
    return default_fps


def repair_file(input_file: str, reference_file: str, output_file: str) -> bool:
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    # No temp dir strictly needed if direct re-encode, but good practice for intermediate steps
    
    logger.info(f"Starting VFR to CFR fix for {input_file}")
    
    target_fps = get_target_framerate(reference_file)
    logger.info(f"Target constant frame rate: {target_fps} fps (derived from reference or default)")

    # This technique inherently re-encodes video. Audio can be copied if intact.
    # Using -vsync cfr or -vf "fps=fps=<target_fps>"
    # -filter:v fps=fps=<target_fps> is generally preferred
    vfr_fix_cmd = [
        FFMPEG_CMD, '-y', '-i', input_file,
        '-vf', f"fps=fps={target_fps}", # Video filter to set CFR
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', # Standard re-encode params
        '-c:a', 'aac', # Or 'copy' if audio is likely okay, but re-encoding safer for timestamp issues
        '-ar', '48000', # Common audio sample rate
        '-movflags', '+faststart',
        '-loglevel', 'error',
        output_file
    ]
    # Alternative using -vsync:
    # vfr_fix_cmd_alt = [
    #     FFMPEG_CMD, '-y', '-i', input_file,
    #     '-vsync', 'cfr', '-r', target_fps, # Force CFR and set output rate
    #     '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
    #     '-c:a', 'copy', # Try copying audio first
    #     '-movflags', '+faststart',
    #     '-loglevel', 'error',
    #     output_file
    # ]

    logger.info(f"Attempting VFR to CFR conversion: {' '.join(vfr_fix_cmd)}")
    
    if os.path.exists(output_file): os.remove(output_file)

    try:
        result = subprocess.run(vfr_fix_cmd, check=True, capture_output=True, text=True)
        if result.returncode == 0 and check_mp4_file(output_file):
            logger.info(f"VFR to CFR conversion successful. Output: {output_file}")
            return True
        else:
            logger.error(f"VFR to CFR conversion produced invalid or no file. Stderr: {result.stderr.strip()}")
            if os.path.exists(output_file): os.remove(output_file)
            return False
    except subprocess.CalledProcessError as e:
        logger.error(f"VFR to CFR conversion command failed. Stderr: {e.stderr.strip()}")
    except Exception as e_gen:
        logger.error(f"General error during VFR to CFR conversion: {e_gen}")
    
    return False

def main():
    parser = argparse.ArgumentParser(description='VFR to CFR MP4 Repair Technique 13')
    parser.add_argument('input_file', help='Path to the damaged MP4 file')
    parser.add_argument('reference_file', help='Path to a working reference MP4 file for target framerate')
    parser.add_argument('output_file', help='Path where the repaired file will be saved')
    args = parser.parse_args()

    if not os.path.exists(args.input_file) or not os.path.exists(args.reference_file):
        logger.error(f"Input or reference file not found.")
        sys.exit(1)

    if repair_file(args.input_file, args.reference_file, args.output_file):
        logger.info("VFR to CFR fix completed successfully.")
        sys.exit(0)
    else:
        logger.error("VFR to CFR fix failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()