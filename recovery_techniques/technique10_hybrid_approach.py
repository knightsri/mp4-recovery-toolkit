#!/usr/bin/env python3
"""
Hybrid Approach Technique (Technique 10)

This technique tries a series of predefined FFmpeg command chains that combine
different repair and remuxing strategies.

Usage:
    python technique10_hybrid_approach.py damaged.mp4 reference.mp4 output.mp4
"""

import os
import sys
import subprocess
import shutil
import logging
import argparse
import json
from typing import Optional, Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mp4_recovery_technique10')

FFMPEG_CMD = 'ffmpeg'
FFPROBE_CMD = 'ffprobe'

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

def get_reference_params(reference_file: str) -> Optional[Dict[str, Any]]:
    """Extract key parameters from the reference file for re-encoding guidance."""
    try:
        cmd = [
            FFPROBE_CMD, '-v', 'quiet', '-print_format', 'json',
            '-show_streams', reference_file
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        info = json.loads(result.stdout)
        params = {"video": {}, "audio": {}}
        for stream in info.get('streams', []):
            if stream.get('codec_type') == 'video' and not params["video"]:
                frame_rate_str = stream.get('r_frame_rate', '30/1')
                try:
                    num, den = map(int, frame_rate_str.split('/'))
                    frame_rate = str(num / den if den != 0 else 30.0)
                except ValueError:
                    frame_rate = "30.0"
                params["video"] = {
                    'width': stream.get('width', 1280),
                    'height': stream.get('height', 720),
                    'frame_rate': frame_rate,
                    'codec': stream.get('codec_name', 'h264')
                }
            elif stream.get('codec_type') == 'audio' and not params["audio"]:
                params["audio"] = {
                    'codec': stream.get('codec_name', 'aac'),
                    'sample_rate': stream.get('sample_rate', '48000'),
                    'channels': stream.get('channels', 2)
                }
        return params
    except Exception as e:
        logger.warning(f"Could not get reference parameters from {reference_file}: {e}")
        return None


def repair_file(input_file: str, reference_file: str, output_file: str) -> bool:
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    temp_dir = os.path.join(os.path.dirname(output_file), f"{base_name}_technique10_temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    ref_params = get_reference_params(reference_file) or {} # Use empty dict if fails

    hybrid_chains = [
        {
            'name': "Force MP4 input, ignore errors, then faststart",
            'commands': [
                [FFMPEG_CMD, '-y', '-f', 'mp4', '-i', input_file, '-c', 'copy', '-ignore_unknown', '-err_detect', 'ignore_err', os.path.join(temp_dir, 'temp1.mp4')],
                [FFMPEG_CMD, '-y', '-i', os.path.join(temp_dir, 'temp1.mp4'), '-c', 'copy', '-movflags', '+faststart', output_file]
            ]
        },
        {
            'name': "Re-encode video (lossy) with reference params, copy audio",
            'commands': [
                [FFMPEG_CMD, '-y', '-i', input_file, '-vn', '-c:a', 'copy', os.path.join(temp_dir, 'temp_audio.aac')],
                [FFMPEG_CMD, '-y', '-i', input_file, '-an', 
                 '-c:v', 'libx264', # Could be made smarter to match ref_params['video'].get('codec')
                 '-s', f"{ref_params.get('video', {}).get('width', '1280')}x{ref_params.get('video', {}).get('height', '720')}",
                 '-r', str(ref_params.get('video', {}).get('frame_rate', '30')),
                 '-preset', 'medium', '-crf', '23',
                 os.path.join(temp_dir, 'temp_video.mp4')],
                [FFMPEG_CMD, '-y', '-i', os.path.join(temp_dir, 'temp_video.mp4'), 
                 '-i', os.path.join(temp_dir, 'temp_audio.aac'), 
                 '-c', 'copy', '-map', '0:v:0', '-map', '1:a:0?', # ? makes audio optional
                 output_file]
            ],
            'pre_check_files': [os.path.join(temp_dir, 'temp_audio.aac'), os.path.join(temp_dir, 'temp_video.mp4')] # Files to check after intermediate steps
        },
        {
            'name': "Attempt moov fix and selective stream mapping",
            'commands': [
                [FFMPEG_CMD, '-y', '-i', input_file, '-c', 'copy', '-movflags', 'use_metadata_tags', '-movflags', '+faststart', os.path.join(temp_dir, 'temp_moov_fix.mp4')],
                [FFMPEG_CMD, '-y', '-i', os.path.join(temp_dir, 'temp_moov_fix.mp4'), '-c', 'copy', '-map', '0:v?', '-map', '0:a?', output_file]
            ]
        },
        {
            'name': "Aggressive error detection flags and remux",
            'commands': [
                 [FFMPEG_CMD, '-y', '-err_detect', 'aggressive,explode', '-fflags', '+discardcorrupt+genpts', '-i', input_file, 
                  '-c:v', 'copy', '-c:a', 'copy', '-map', '0:v?', '-map', '0:a?', 
                  '-movflags', '+faststart', output_file]
            ]
        }
    ]

    success = False
    try:
        logger.info(f"Starting hybrid approach for {input_file}")
        for i, chain_info in enumerate(hybrid_chains):
            logger.info(f"\nTrying Hybrid Chain {i+1}: {chain_info['name']}")
            
            # Clean up output from previous chain attempt
            if os.path.exists(output_file): os.remove(output_file)
            # Clean temp files specific to this chain if defined
            for temp_f in chain_info.get('pre_check_files', []):
                if os.path.exists(temp_f): os.remove(temp_f)

            chain_success = True
            for cmd_idx, cmd in enumerate(chain_info['commands']):
                logger.debug(f"Executing: {' '.join(cmd)}")
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                if result.returncode != 0:
                    logger.warning(f"Command failed (Chain {i+1}, Step {cmd_idx+1}): {' '.join(cmd)}")
                    logger.warning(f"FFmpeg stderr: {result.stderr.strip()}")
                    chain_success = False
                    break # Move to next chain if a step fails
            
            if chain_success and check_mp4_file(output_file):
                logger.info(f"Hybrid Chain {i+1} succeeded. Repaired file at {output_file}")
                success = True
                break # Exit loop if a chain succeeds
            elif chain_success and not check_mp4_file(output_file):
                 logger.warning(f"Hybrid Chain {i+1} produced an output file, but it seems invalid.")
                 if os.path.exists(output_file): os.remove(output_file)


    except Exception as e:
        logger.error(f"An error occurred during hybrid approach: {str(e)}")
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temp directory: {temp_dir}")
            
    return success

def main():
    parser = argparse.ArgumentParser(description='Hybrid MP4 Repair Technique 10')
    parser.add_argument('input_file', help='Path to the damaged MP4 file')
    parser.add_argument('reference_file', help='Path to a working reference MP4 file')
    parser.add_argument('output_file', help='Path where the repaired file will be saved')
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        logger.error(f"Input file not found: {args.input_file}")
        sys.exit(1)
    if not os.path.exists(args.reference_file): # Though not heavily used, good for consistency
        logger.warning(f"Reference file not found: {args.reference_file}, some hybrid chains might be less effective.")


    if repair_file(args.input_file, args.reference_file, args.output_file):
        logger.info("Hybrid Approach completed successfully.")
        sys.exit(0)
    else:
        logger.error("Hybrid Approach failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()