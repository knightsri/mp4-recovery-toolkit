#!/usr/bin/env python3
"""
Standard Remux Technique (Technique 1)

This is the basic approach to extract video and audio streams from a damaged MP4
and remux them into a new container with parameters from a reference file.

Usage:
    python technique1_standard_remux.py damaged.mp4 reference.mp4 output.mp4
"""

import os
import sys
import subprocess
import shutil
import logging
import json
import argparse
from typing import Optional, Dict, Any, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mp4_recovery')

def extract_streams(input_file: str, temp_dir: str) -> Tuple[bool, bool, str, str]:
    """Extract video and audio streams from input file."""
    print("\nExtracting streams using standard method...")
    
    temp_video = os.path.join(temp_dir, "video.h264")
    temp_audio = os.path.join(temp_dir, "audio.aac")
    
    # Try to extract video stream
    video_cmd = [
        'ffmpeg',
        '-i', input_file,
        '-c:v', 'copy',
        '-an',
        '-f', 'h264',
        temp_video
    ]
    
    print("Extracting video stream...")
    subprocess.run(
        video_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # Try to extract audio stream
    audio_cmd = [
        'ffmpeg',
        '-i', input_file,
        '-c:a', 'copy',
        '-vn',
        temp_audio
    ]
    
    print("Extracting audio stream...")
    subprocess.run(
        audio_cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    
    # Check what was extracted
    has_video = os.path.exists(temp_video) and os.path.getsize(temp_video) > 1000
    has_audio = os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 1000
    
    if has_video:
        print("✓ Successfully extracted video stream")
    else:
        print("✗ Failed to extract video stream")
        
    if has_audio:
        print("✓ Successfully extracted audio stream")
    else:
        print("✗ Failed to extract audio stream")
    
    return has_video, has_audio, temp_video, temp_audio

def extract_params(file_path: str) -> Optional[Dict[str, Any]]:
    """Extract key parameters from an MP4 file."""
    try:
        # Get file info using FFprobe
        cmd = [
            'ffprobe', 
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format', 
            '-show_streams', 
            file_path
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            return None
        
        # Parse the JSON output
        info = json.loads(result.stdout)
        
        # Initialize parameter dict
        params = {"video": {}, "audio": {}, "container": {}}
        
        # Extract container parameters
        if 'format' in info:
            format_info = info['format']
            params['container'] = {
                'format_name': format_info.get('format_name', 'unknown'),
                'duration': format_info.get('duration', 'unknown'),
                'bit_rate': format_info.get('bit_rate', 'unknown'),
                'size': format_info.get('size', 'unknown')
            }
        
        # Extract stream parameters
        if 'streams' in info:
            for stream in info['streams']:
                # Video stream parameters
                if stream.get('codec_type') == 'video':
                    frame_rate = '30'
                    if 'r_frame_rate' in stream:
                        try:
                            nums = stream['r_frame_rate'].split('/')
                            if len(nums) == 2 and int(nums[1]) != 0:
                                frame_rate = str(float(int(nums[0]) / int(nums[1])))
                        except:
                            pass
                            
                    params['video'] = {
                        'codec': stream.get('codec_name', 'h264'),
                        'width': stream.get('width', 1280),
                        'height': stream.get('height', 720),
                        'frame_rate': frame_rate
                    }
                
                # Audio stream parameters
                elif stream.get('codec_type') == 'audio':
                    params['audio'] = {
                        'codec': stream.get('codec_name', 'aac'),
                        'channels': stream.get('channels', 2),
                        'sample_rate': stream.get('sample_rate', 44100)
                    }
        
        return params
            
    except Exception as e:
        logger.error(f"Error extracting parameters: {str(e)}")
        return None

def check_mp4_file(file_path: str) -> bool:
    """Check if an MP4 file is valid using FFmpeg."""
    if not os.path.exists(file_path):
        return False
    
    try:
        cmd = [
            'ffmpeg', 
            '-v', 'error', 
            '-i', file_path, 
            '-f', 'null', 
            '-'
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        return result.stderr.strip() == ''
            
    except Exception:
        return False

def repair_file(input_file: str, reference_file: str, output_file: str) -> bool:
    """Repair a damaged MP4 file using standard remuxing technique."""
    try:
        # Create temp directory
        temp_dir = os.path.join(os.path.dirname(output_file), "temp_recovery")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Extract parameters from reference file
        print("Extracting parameters from reference file...")
        ref_params = extract_params(reference_file)
        if not ref_params:
            print("Failed to extract parameters from reference file")
            return False
        
        # Extract streams from input file
        has_video, has_audio, temp_video, temp_audio = extract_streams(input_file, temp_dir)
        
        # We need at least video to proceed
        if not has_video:
            print("\n❌ Standard remuxing failed - could not extract video stream")
            return False
        
        # Get reference parameters for rebuilding
        ref_width = ref_params['video'].get('width', 1280)
        ref_height = ref_params['video'].get('height', 720)
        ref_frame_rate = ref_params['video'].get('frame_rate', 30)
        
        # Rebuild the file
        print("\nRemuxing streams into new container...")
        
        # Start building ffmpeg command
        cmd = ['ffmpeg']
        
        # Add input files
        cmd.extend(['-i', temp_video])
        if has_audio:
            cmd.extend(['-i', temp_audio])
        
        # Add video encoding options
        cmd.extend([
            '-c:v', 'libx264',
            '-s', f"{ref_width}x{ref_height}",
            '-r', str(ref_frame_rate),
            '-map', '0:v'
        ])
        
        # Add audio if available
        if has_audio:
            cmd.extend([
                '-c:a', 'aac',
                '-ac', str(ref_params['audio'].get('channels', 2)),
                '-ar', str(ref_params['audio'].get('sample_rate', 44100)),
                '-map', '1:a'
            ])
        
        # Finalize command
        cmd.extend([
            '-movflags', 'faststart',
            output_file
        ])
        
        # Execute ffmpeg command
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        if result.returncode == 0 and os.path.exists(output_file):
            print("✓ Successfully rebuilt file using standard remuxing")
            
            # Verify the repaired file
            print("\nVerifying repaired file...")
            if check_mp4_file(output_file):
                print("✓ Repaired file is valid")
                return True
            else:
                print("✗ Remuxed file validation failed")
                if os.path.exists(output_file):
                    os.remove(output_file)
                return False
        else:
            print("✗ Remuxing failed")
            return False
            
    except Exception as e:
        logger.error(f"Error during standard remux: {str(e)}")
        print(f"Error during standard remux: {str(e)}")
        return False
        
    finally:
        # Clean up
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Standard Remux Recovery Technique')
    parser.add_argument('input_file', help='Path to the damaged MP4 file')
    parser.add_argument('reference_file', help='Path to a working reference MP4 file')
    parser.add_argument('output_file', help='Path where the repaired file will be saved')
    
    args = parser.parse_args()
    
    # Print header
    print("\n" + "="*60)
    print(" "*15 + "STANDARD REMUX TECHNIQUE")
    print("="*60 + "\n")
    
    # Check input files
    if not os.path.exists(args.input_file):
        print(f"Error: Input file does not exist: {args.input_file}")
        sys.exit(1)
    
    if not os.path.exists(args.reference_file):
        print(f"Error: Reference file does not exist: {args.reference_file}")
        sys.exit(1)
    
    # Create output directory if needed
    output_dir = os.path.dirname(args.output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Run repair
    if repair_file(args.input_file, args.reference_file, args.output_file):
        print("\n" + "="*60)
        print(" "*20 + "SUCCESS")
        print("="*60)
        print(f"\nRepaired file saved to: {args.output_file}")
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print(" "*20 + "FAILED")
        print("="*60)
        print("\nStandard remux technique failed to repair the file.")
        sys.exit(1)

if __name__ == "__main__":
    main()