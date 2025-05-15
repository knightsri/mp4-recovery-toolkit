#!/usr/bin/env python3
"""
MP4 Atom Structure Repair (Technique 5 - FFmpeg based)

This script attempts to recover damaged MP4 files by leveraging FFmpeg's
capabilities to fix container-level structural issues. It tries several
FFmpeg command variations aimed at re-wrapping streams, fixing index
issues that FFmpeg can handle, and ensuring the output container is well-formed.

This approach does not perform deep Python-based atom parsing or editing,
which is a more complex task (e.g., Technique 17).

Usage:
    python technique5_atom_structure_repair.py damaged.mp4 reference.mp4 output.mp4
"""

import os
import sys
import subprocess
import shutil
import logging
import argparse
import json # For check_output_validity
from typing import List, Tuple, Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('technique5_atom_structure_repair_ffmpeg')

FFMPEG_CMD = 'ffmpeg'
FFPROBE_CMD = 'ffprobe' # For check_output_validity

def check_output_validity(file_path: str, min_duration_sec: float = 1.0, reference_file: Optional[str] = None) -> bool:
    """
    Robust check for output file validity using ffprobe.
    Checks if it's a valid media file, has streams, and a minimum duration.
    Compares to reference duration if available.
    """
    if not os.path.exists(file_path) or os.path.getsize(file_path) < 1024: # Basic sanity for size
        logger.debug(f"Validity Check: File {file_path} is too small or does not exist.")
        return False
    try:
        # Get media info
        cmd_probe = [FFPROBE_CMD, '-v', 'error', '-show_format', '-show_streams', '-of', 'json', file_path]
        result_probe = subprocess.run(cmd_probe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if result_probe.returncode != 0 or not result_probe.stdout:
            logger.warning(f"Validity Check: ffprobe failed or no output for {file_path}. Stderr: {result_probe.stderr.strip()}")
            return False
        
        info = json.loads(result_probe.stdout)
        
        if not info.get('streams'):
            logger.warning(f"Validity Check: No streams found in {file_path}")
            return False
            
        duration_str = info.get('format', {}).get('duration')
        output_duration = 0.0
        if duration_str:
            try:
                output_duration = float(duration_str)
                if output_duration < min_duration_sec:
                    logger.warning(f"Validity Check: File {file_path} duration {output_duration:.2f}s < {min_duration_sec:.2f}s minimum.")
                    return False
            except ValueError:
                logger.warning(f"Validity Check: Could not parse duration '{duration_str}' for {file_path}")
                return False 
        else:
            logger.warning(f"Validity Check: No duration information in {file_path}")
            return False
        
        # Compare with reference duration if provided
        if reference_file and os.path.exists(reference_file):
            cmd_ref_probe = [FFPROBE_CMD, '-v', 'error', '-show_format', '-of', 'json', reference_file]
            result_ref_probe = subprocess.run(cmd_ref_probe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            if result_ref_probe.returncode == 0 and result_ref_probe.stdout:
                ref_info = json.loads(result_ref_probe.stdout)
                ref_duration_str = ref_info.get('format', {}).get('duration')
                if ref_duration_str:
                    try:
                        ref_duration = float(ref_duration_str)
                        # Expect output to be at least a small fraction of reference, e.g., 10%
                        if output_duration < ref_duration * 0.1 and ref_duration > min_duration_sec * 2 : # if ref is substantial
                             logger.warning(f"Validity Check: Output duration {output_duration:.2f}s is significantly less than reference {ref_duration:.2f}s.")
                             return False
                    except ValueError:
                        logger.warning(f"Validity Check: Could not parse reference duration '{ref_duration_str}'.")
            else:
                logger.warning(f"Validity Check: Could not probe reference file {reference_file} for duration comparison.")


        # Final ffmpeg check for critical errors on the output file itself
        cmd_ffmpeg_check = [FFMPEG_CMD, '-v', 'error', '-i', file_path, '-f', 'null', '-']
        result_ffmpeg_check = subprocess.run(cmd_ffmpeg_check, stderr=subprocess.PIPE, text=True, check=False, timeout=10) # Added timeout
        if result_ffmpeg_check.returncode != 0 or result_ffmpeg_check.stderr.strip() != '':
            logger.warning(f"Validity Check: FFmpeg reported errors or failed for '{file_path}':\n{result_ffmpeg_check.stderr.strip()}")
            return False
            
        logger.info(f"Validity Check: File {file_path} (duration: {output_duration:.2f}s) passed.")
        return True
    except subprocess.TimeoutExpired:
        logger.warning(f"Validity Check: FFmpeg timed out while checking '{file_path}'. File is likely problematic.")
        return False
    except json.JSONDecodeError:
        logger.warning(f"Validity Check: ffprobe output for {file_path} was not valid JSON.")
        return False
    except Exception as e_gen:
        logger.error(f"Validity Check: Unexpected error for {file_path}: {e_gen}", exc_info=True)
        return False


def attempt_ffmpeg_structural_repair(input_file: str, temp_output_file: str, reference_file: Optional[str] = None) -> bool:
    """
    Tries various FFmpeg commands that can help with structural issues.
    Outputs to temp_output_file. Returns True if a valid output is created.
    """
    # Prioritize commands that are less likely to alter streams if simple fixes work
    repair_commands_with_desc: List[Tuple[List[str], str]] = [
        (
            [FFMPEG_CMD, '-y', '-i', input_file, '-c', 'copy', '-movflags', '+faststart', '-map_metadata', '0', '-map_chapters', '0', temp_output_file],
            "Basic remux with faststart & metadata mapping"
        ),
        (
            [FFMPEG_CMD, '-y', '-err_detect', 'ignore_err', '-fflags', '+genpts+igndts', '-i', input_file, '-c', 'copy', '-movflags', '+faststart', '-map_metadata', '0', temp_output_file],
            "Remux ignoring specific errors and regenerating timestamps"
        ),
        ( # This attempts to rebuild some moov atom aspects, good for index issues
            [FFMPEG_CMD, '-y', '-i', input_file, '-c', 'copy', '-movflags', '+faststart+empty_moov+frag_keyframe', '-avoid_negative_ts', 'make_zero', '-map_metadata', '-1', temp_output_file],
            "Remux with advanced MOOV atom flags (empty_moov, frag_keyframe)"
        ),
        ( # Forcing input format can sometimes help ffmpeg parse a difficult file
            [FFMPEG_CMD, '-y', '-f', 'mp4', '-i', input_file, '-c', 'copy', '-movflags', '+faststart', temp_output_file],
            "Remux forcing MP4 input format"
        ),
        ( # A more aggressive error detection and discard
            [FFMPEG_CMD, '-y', '-err_detect', 'crccheck,bitstream,buffer,explode', '-fflags', '+discardcorrupt', '-i', input_file, '-c', 'copy', '-movflags', '+faststart', temp_output_file],
            "Remux with aggressive error detection and discard corrupt packets"
        )
    ]

    for i, (cmd_template, desc) in enumerate(repair_commands_with_desc):
        logger.info(f"Attempting FFmpeg structural repair method #{i+1}: {desc}")
        current_cmd = cmd_template[:-1] + ['-loglevel', 'error', cmd_template[-1]] # Add loglevel error

        if os.path.exists(temp_output_file):
            os.remove(temp_output_file)
        try:
            logger.debug(f"Executing: {' '.join(current_cmd)}")
            subprocess.run(current_cmd, check=True, capture_output=True, text=True, timeout=120) # 2 min timeout
            if check_output_validity(temp_output_file, reference_file=reference_file): # Pass reference for duration comparison
                logger.info(f"Method #{i+1} ('{desc}') successful. Valid output at {temp_output_file}")
                return True
            else:
                logger.warning(f"Method #{i+1} ('{desc}') completed, but output '{temp_output_file}' is invalid or empty.")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Method #{i+1} ('{desc}') failed. Command: {' '.join(e.cmd)}")
            if e.stderr: logger.warning(f"FFmpeg stderr:\n{e.stderr.strip()}")
        except subprocess.TimeoutExpired:
            logger.warning(f"Method #{i+1} ('{desc}') timed out. File may be too corrupt or complex for this command.")
        except Exception as e_gen:
            logger.error(f"General error during method #{i+1} ('{desc}'): {e_gen}", exc_info=True)

    logger.error("All FFmpeg-based structural repair methods for Technique 5 failed to produce a valid output.")
    return False

def main_repair_logic(input_file: str, reference_file: str, output_file_final_dest: str) -> bool:
    logger.info(f"Starting Technique 5: Atom Structure Repair (FFmpeg-based) for {input_file}")

    # Create a temporary file path in the same directory as the final output
    # This ensures the temp file is on the same filesystem, making shutil.move faster if used.
    temp_output_filename = f"temp_technique5_{os.path.basename(output_file_final_dest)}"
    temp_output_filepath = os.path.join(os.path.dirname(output_file_final_dest) or ".", temp_output_filename)

    if attempt_ffmpeg_structural_repair(input_file, temp_output_filepath, reference_file):
        logger.info(f"Technique 5 successful. Moving temporary file {temp_output_filepath} to final destination {output_file_final_dest}")
        try:
            shutil.move(temp_output_filepath, output_file_final_dest)
            return True
        except Exception as e:
            logger.error(f"Failed to move temp file {temp_output_filepath} to {output_file_final_dest}: {e}")
            # Attempt copy as fallback if move fails (e.g. different filesystems in some edge cases)
            try:
                shutil.copy2(temp_output_filepath, output_file_final_dest)
                os.remove(temp_output_filepath) # Clean up original temp
                return True
            except Exception as e_copy:
                logger.error(f"Fallback copy also failed for {temp_output_filepath} to {output_file_final_dest}: {e_copy}")
                if os.path.exists(temp_output_filepath): os.remove(temp_output_filepath) # Still try to clean temp
                return False # Could not finalize output
    else:
        logger.error(f"Technique 5 failed for {input_file}.")
        if os.path.exists(temp_output_filepath): # Clean up failed temp file
            try: os.remove(temp_output_filepath)
            except OSError: logger.warning(f"Could not remove failed temp output file: {temp_output_filepath}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='MP4 Atom Structure Repair (Technique 5 - FFmpeg-based)')
    parser.add_argument('input_file', help='Path to the damaged MP4 file')
    parser.add_argument('reference_file', help='Path to a working reference MP4 file for duration comparison')
    parser.add_argument('output_file', help='Path where the repaired file will be saved')
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        logger.critical(f"Input file not found: {args.input_file}")
        sys.exit(1)
    
    # Create output directory if it doesn't exist for the final output file
    output_dir_final = os.path.dirname(args.output_file)
    if output_dir_final and not os.path.exists(output_dir_final):
        try:
            os.makedirs(output_dir_final, exist_ok=True)
        except OSError as e:
            logger.critical(f"Could not create output directory {output_dir_final}: {e}")
            sys.exit(1)


    if main_repair_logic(args.input_file, args.reference_file, args.output_file):
        sys.exit(0)
    else:
        sys.exit(1)