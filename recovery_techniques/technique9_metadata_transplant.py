#!/usr/bin/env python3
"""
Metadata Transplant Technique (Technique 9)

Extracts raw streams from the damaged MP4 and remuxes them using metadata
derived from a reference file.

Usage:
    python technique9_metadata_transplant.py damaged.mp4 reference.mp4 output.mp4
"""

import os
import sys
import subprocess
import shutil
import logging
import argparse
import json
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mp4_recovery_technique9')

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

def get_reference_metadata(reference_file: str) -> Optional[Dict[str, Any]]:
    """Extracts key metadata from the reference file using ffprobe."""
    try:
        cmd = [
            FFPROBE_CMD, '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', reference_file
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        info = json.loads(result.stdout)
        
        metadata = {
            'duration': info.get('format', {}).get('duration', '60'), # Default 60s if not found
            'video_stream': None,
            'audio_stream': None
        }
        for stream in info.get('streams', []):
            if stream.get('codec_type') == 'video' and not metadata['video_stream']:
                metadata['video_stream'] = {
                    'codec_name': stream.get('codec_name', 'h264'),
                    'avg_frame_rate': stream.get('avg_frame_rate', '30/1'),
                    'time_base': stream.get('time_base', '1/30000'),
                    'language': stream.get('tags', {}).get('language', 'und')
                }
            elif stream.get('codec_type') == 'audio' and not metadata['audio_stream']:
                 metadata['audio_stream'] = {
                    'codec_name': stream.get('codec_name', 'aac'),
                    'sample_rate': stream.get('sample_rate', '48000'),
                    'channels': stream.get('channels', 2),
                    'channel_layout': stream.get('channel_layout', 'stereo'),
                    'time_base': stream.get('time_base', '1/48000'),
                    'language': stream.get('tags', {}).get('language', 'und')
                }
        return metadata
    except Exception as e:
        logger.error(f"Failed to get metadata from reference file {reference_file}: {e}")
        return None


def repair_file(input_file: str, reference_file: str, output_file: str) -> bool:
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    temp_dir = os.path.join(os.path.dirname(output_file), f"{base_name}_technique9_temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    raw_video_path = os.path.join(temp_dir, "video.h264") # Assuming H.264
    raw_audio_path = os.path.join(temp_dir, "audio.aac")  # Assuming AAC
    success = False

    try:
        logger.info(f"Starting metadata transplant for {input_file} using {reference_file}")

        ref_meta = get_reference_metadata(reference_file)
        if not ref_meta:
            return False

        # 1. Extract raw video stream
        extract_video_cmd = [
            FFMPEG_CMD, '-i', input_file, '-c:v', 'copy', 
            '-bsf:v', 'h264_mp4toannexb', # Common for H.264
            '-an', '-f', 'h264', '-loglevel', 'error', raw_video_path
        ]
        logger.info(f"Extracting raw video: {' '.join(extract_video_cmd)}")
        subprocess.run(extract_video_cmd, check=False) # Allow failure if stream is bad

        # 2. Extract raw audio stream
        extract_audio_cmd = [
            FFMPEG_CMD, '-i', input_file, '-c:a', 'copy', 
            '-vn', '-f', 'adts', '-loglevel', 'error', raw_audio_path # ADTS for AAC
        ]
        logger.info(f"Extracting raw audio: {' '.join(extract_audio_cmd)}")
        subprocess.run(extract_audio_cmd, check=False)

        has_video = os.path.exists(raw_video_path) and os.path.getsize(raw_video_path) > 0
        has_audio = os.path.exists(raw_audio_path) and os.path.getsize(raw_audio_path) > 0

        if not has_video and not has_audio:
            logger.error("Failed to extract any raw streams.")
            return False
        
        logger.info(f"Raw video extracted: {has_video}, Raw audio extracted: {has_audio}")

        # 3. Remux with metadata from reference file
        remux_cmd = [FFMPEG_CMD]
        input_streams_count = 0
        
        if has_video and ref_meta.get('video_stream'):
            video_ref = ref_meta['video_stream']
            # Use framerate from reference if possible
            try:
                num, den = map(int, video_ref['avg_frame_rate'].split('/'))
                framerate = str(num / den if den != 0 else 30)
            except:
                framerate = "30" # Default
            remux_cmd.extend(['-r', framerate, '-i', raw_video_path])
            input_streams_count +=1
            
        if has_audio and ref_meta.get('audio_stream'):
            remux_cmd.extend(['-i', raw_audio_path])
            input_streams_count +=1
        
        if input_streams_count == 0:
            logger.error("No streams to remux based on reference metadata.")
            return False

        # Codec copy
        remux_cmd.extend(['-c', 'copy'])

        # Mapping
        map_args = []
        current_map_idx = 0
        if has_video and ref_meta.get('video_stream'):
            map_args.extend([f'-map', f'{current_map_idx}:v:0'])
            current_map_idx += 1
        if has_audio and ref_meta.get('audio_stream'):
             map_args.extend([f'-map', f'{current_map_idx}:a:0'])
        remux_cmd.extend(map_args)
        
        # Other metadata
        remux_cmd.extend(['-movflags', '+faststart'])
        if ref_meta.get('duration'):
             remux_cmd.extend(['-t', str(ref_meta['duration'])])
        
        if has_video and ref_meta.get('video_stream') and ref_meta['video_stream'].get('language') != 'und':
            remux_cmd.extend([f'-metadata:s:v:0', f"language={ref_meta['video_stream']['language']}"])
        if has_audio and ref_meta.get('audio_stream') and ref_meta['audio_stream'].get('language') != 'und':
             remux_cmd.extend([f'-metadata:s:a:0', f"language={ref_meta['audio_stream']['language']}"])
        
        remux_cmd.extend(['-loglevel', 'error', output_file])
        
        if os.path.exists(output_file): os.remove(output_file) # Clean before trying
        logger.info(f"Attempting remux with transplanted metadata: {' '.join(remux_cmd)}")
        result = subprocess.run(remux_cmd, check=True)

        if result.returncode == 0 and check_mp4_file(output_file):
            logger.info(f"File successfully repaired with transplanted metadata: {output_file}")
            success = True
        else:
            logger.error(f"Failed to remux with transplanted metadata. FFmpeg stderr: {result.stderr}")

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
    parser = argparse.ArgumentParser(description='Metadata Transplant MP4 Repair Technique 9')
    parser.add_argument('input_file', help='Path to the damaged MP4 file')
    parser.add_argument('reference_file', help='Path to a working reference MP4 file')
    parser.add_argument('output_file', help='Path where the repaired file will be saved')
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        logger.error(f"Input file not found: {args.input_file}")
        sys.exit(1)
    if not os.path.exists(args.reference_file):
        logger.error(f"Reference file not found: {args.reference_file}")
        sys.exit(1)

    if repair_file(args.input_file, args.reference_file, args.output_file):
        logger.info("Metadata Transplant completed successfully.")
        sys.exit(0)
    else:
        logger.error("Metadata Transplant failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()