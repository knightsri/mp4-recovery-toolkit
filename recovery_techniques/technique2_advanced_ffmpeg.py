#!/usr/bin/env python3
"""
Advanced FFmpeg Technique (Technique 2)

This technique tries multiple advanced FFmpeg parameter combinations to extract
and rebuild streams from a damaged MP4 file.

Usage:
    python technique2_advanced_ffmpeg.py damaged.mp4 reference.mp4 output.mp4
"""

import os
import sys
import subprocess
import shutil
import logging
import json
import argparse
from typing import Optional, Dict, Any, Tuple, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mp4_recovery')

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

def try_advanced_extract(input_file: str, temp_dir: str) -> Tuple[bool, bool, str, str]:
    """Try multiple advanced extraction methods."""
    print("\nAttempting multiple advanced extraction methods...")
    
    temp_video = os.path.join(temp_dir, "video.h264")
    temp_audio = os.path.join(temp_dir, "audio.aac")
    
    # Define multiple extraction methods with advanced parameters
    extraction_methods = [
        # Method 1: Error tolerant extraction with custom flags
        {
            'name': "Error tolerant extraction",
            'video_cmd': [
                'ffmpeg',
                '-err_detect', 'ignore_err',
                '-fflags', '+genpts+igndts+discardcorrupt',
                '-i', input_file,
                '-c:v', 'copy',
                '-an',
                '-f', 'h264',
                temp_video
            ],
            'audio_cmd': [
                'ffmpeg',
                '-err_detect', 'ignore_err',
                '-fflags', '+genpts+igndts+discardcorrupt',
                '-i', input_file,
                '-c:a', 'copy',
                '-vn',
                temp_audio
            ]
        },
        # Method 2: Skip initial damaged sections
        {
            'name': "Skip initial damaged sections",
            'video_cmd': [
                'ffmpeg',
                '-ss', '2',  # Skip first 2 seconds
                '-i', input_file,
                '-c:v', 'copy',
                '-an',
                '-f', 'h264',
                temp_video
            ],
            'audio_cmd': [
                'ffmpeg',
                '-ss', '2',
                '-i', input_file,
                '-c:a', 'copy',
                '-vn',
                temp_audio
            ]
        },
        # Method 3: Force frame rate interpretation
        {
            'name': "Force frame rate interpretation",
            'video_cmd': [
                'ffmpeg',
                '-framerate', '30',  # Force input framerate
                '-i', input_file,
                '-c:v', 'copy',
                '-an',
                '-f', 'h264',
                temp_video
            ],
            'audio_cmd': [
                'ffmpeg',
                '-i', input_file,
                '-c:a', 'copy',
                '-vn',
                temp_audio
            ]
        },
        # Method 4: Extract raw H.264 with bsf filters
        {
            'name': "Extract raw H.264 with bsf filters",
            'video_cmd': [
                'ffmpeg',
                '-i', input_file,
                '-c:v', 'copy',
                '-bsf:v', 'h264_mp4toannexb',
                '-an',
                '-f', 'h264',
                temp_video
            ],
            'audio_cmd': [
                'ffmpeg',
                '-i', input_file,
                '-c:a', 'copy',
                '-vn',
                temp_audio
            ]
        },
        # Method 5: Increase buffer sizes and max analyze duration
        {
            'name': "Increase buffer sizes",
            'video_cmd': [
                'ffmpeg',
                '-analyzeduration', '100M',
                '-probesize', '100M',
                '-i', input_file,
                '-c:v', 'copy',
                '-an',
                '-f', 'h264',
                temp_video
            ],
            'audio_cmd': [
                'ffmpeg',
                '-analyzeduration', '100M',
                '-probesize', '100M',
                '-i', input_file,
                '-c:a', 'copy',
                '-vn',
                temp_audio
            ]
        },
        # Method 6: Segment input and try to recover each segment
        {
            'name': "Segment input recovery",
            'video_cmd': [
                'ffmpeg',
                '-f', 'segment',
                '-segment_time', '10',
                '-reset_timestamps', '1',
                '-i', input_file,
                '-c:v', 'copy',
                '-an',
                '-f', 'h264',
                temp_video
            ],
            'audio_cmd': [
                'ffmpeg',
                '-f', 'segment',
                '-segment_time', '10',
                '-reset_timestamps', '1',
                '-i', input_file,
                '-c:a', 'copy',
                '-vn',
                temp_audio
            ]
        },
        # Method 7: Extract with pixel format conversion
        {
            'name': "Extract with pixel format conversion",
            'video_cmd': [
                'ffmpeg',
                '-i', input_file,
                '-pix_fmt', 'yuv420p',
                '-c:v', 'copy',
                '-an',
                '-f', 'h264',
                temp_video
            ],
            'audio_cmd': [
                'ffmpeg',
                '-i', input_file,
                '-c:a', 'copy',
                '-vn',
                temp_audio
            ]
        }
    ]
    
    # Try each method until one succeeds
    for i, method in enumerate(extraction_methods):
        print(f"\nMethod {i+1}: {method['name']}")
        
        # Clean any previous attempts
        if os.path.exists(temp_video):
            os.remove(temp_video)
        if os.path.exists(temp_audio):
            os.remove(temp_audio)
        
        # Try to extract video
        subprocess.run(
            method['video_cmd'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Try to extract audio
        subprocess.run(
            method['audio_cmd'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Check if we got anything
        has_video = os.path.exists(temp_video) and os.path.getsize(temp_video) > 1000
        has_audio = os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 1000
        
        if has_video:
            print(f"✓ Method {i+1} successfully extracted video")
            if has_audio:
                print(f"✓ Method {i+1} successfully extracted audio")
            else:
                print(f"✗ Method {i+1} failed to extract audio")
            
            return has_video, has_audio, temp_video, temp_audio
        else:
            print(f"✗ Method {i+1} failed to extract video")
    
    # If all methods failed, return failure
    return False, False, temp_video, temp_audio

def try_advanced_rebuild(video_path: str, audio_path: str, ref_params: Dict[str, Any], output_file: str) -> bool:
    """Try multiple advanced rebuilding methods."""
    print("\nAttempting multiple advanced rebuilding methods...")
    
    has_audio = os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000
    
    # Get reference parameters
    ref_width = ref_params['video'].get('width', 1280)
    ref_height = ref_params['video'].get('height', 720)
    ref_frame_rate = ref_params['video'].get('frame_rate', 30)
    
    # Define multiple rebuilding methods
    rebuild_methods = [
        # Method 1: Standard rebuild with specific codec parameters
        {
            'name': "Standard rebuild with specific codec parameters",
            'cmd': lambda: ['ffmpeg'] + 
                    ['-i', video_path] + 
                    (['-i', audio_path] if has_audio else []) +
                    ['-c:v', 'libx264',
                     '-preset', 'medium',
                     '-crf', '23',
                     '-s', f"{ref_width}x{ref_height}",
                     '-r', str(ref_frame_rate),
                     '-map', '0:v'] +
                    (['-c:a', 'aac', 
                      '-ac', str(ref_params['audio'].get('channels', 2)), 
                      '-ar', str(ref_params['audio'].get('sample_rate', 44100)),
                      '-map', '1:a'] if has_audio else []) +
                    ['-movflags', 'faststart',
                     output_file]
        },
        # Method 2: Force keyframes and GOP structure
        {
            'name': "Force keyframes and GOP structure",
            'cmd': lambda: ['ffmpeg'] + 
                    ['-i', video_path] + 
                    (['-i', audio_path] if has_audio else []) +
                    ['-c:v', 'libx264',
                     '-preset', 'slow',
                     '-g', '15',  # GOP size
                     '-keyint_min', '15',
                     '-force_key_frames', 'expr:gte(t,n_forced*1)',
                     '-s', f"{ref_width}x{ref_height}",
                     '-r', str(ref_frame_rate),
                     '-map', '0:v'] +
                    (['-c:a', 'aac', 
                      '-ac', str(ref_params['audio'].get('channels', 2)), 
                      '-ar', str(ref_params['audio'].get('sample_rate', 44100)),
                      '-map', '1:a'] if has_audio else []) +
                    ['-movflags', 'faststart+frag_keyframe',
                     output_file]
        },
        # Method 3: Transcode instead of copy with hardware acceleration
        {
            'name': "Transcode with hardware acceleration",
            'cmd': lambda: ['ffmpeg'] + 
                    ['-i', video_path] + 
                    (['-i', audio_path] if has_audio else []) +
                    ['-c:v', 'libx264',  # Try hardware accel if available
                     '-preset', 'faster',
                     '-s', f"{ref_width}x{ref_height}",
                     '-r', str(ref_frame_rate),
                     '-map', '0:v'] +
                    (['-c:a', 'aac', 
                      '-ac', str(ref_params['audio'].get('channels', 2)), 
                      '-ar', str(ref_params['audio'].get('sample_rate', 44100)),
                      '-map', '1:a'] if has_audio else []) +
                    ['-movflags', 'faststart',
                     output_file]
        },
        # Method 4: Add custom header and force specific pixel format
        {
            'name': "Add custom header and force specific pixel format",
            'cmd': lambda: ['ffmpeg'] + 
                    ['-i', video_path] + 
                    (['-i', audio_path] if has_audio else []) +
                    ['-c:v', 'libx264',
                     '-pix_fmt', 'yuv420p',
                     '-profile:v', 'baseline',
                     '-level', '3.0',
                     '-s', f"{ref_width}x{ref_height}",
                     '-r', str(ref_frame_rate),
                     '-map', '0:v'] +
                    (['-c:a', 'aac', 
                      '-ac', str(ref_params['audio'].get('channels', 2)), 
                      '-ar', str(ref_params['audio'].get('sample_rate', 44100)),
                      '-map', '1:a'] if has_audio else []) +
                    ['-movflags', 'faststart+frag_keyframe+empty_moov',
                     output_file]
        },
        # Method 5: Force input format and use specific bitrates
        {
            'name': "Force input format and use specific bitrates",
            'cmd': lambda: ['ffmpeg'] + 
                    ['-f', 'h264',
                     '-i', video_path] + 
                    (['-f', 'aac', '-i', audio_path] if has_audio else []) +
                    ['-c:v', 'libx264',
                     '-b:v', '2M',
                     '-maxrate', '4M',
                     '-bufsize', '4M',
                     '-s', f"{ref_width}x{ref_height}",
                     '-r', str(ref_frame_rate),
                     '-map', '0:v'] +
                    (['-c:a', 'aac', 
                      '-b:a', '128k',
                      '-ac', str(ref_params['audio'].get('channels', 2)), 
                      '-ar', str(ref_params['audio'].get('sample_rate', 44100)),
                      '-map', '1:a'] if has_audio else []) +
                    ['-movflags', 'faststart',
                     output_file]
        }
    ]
    
    # Try each method until one succeeds
    for i, method in enumerate(rebuild_methods):
        print(f"\nRebuild method {i+1}: {method['name']}")
        
        # If output file exists from previous attempt, remove it
        if os.path.exists(output_file):
            os.remove(output_file)
        
        # Build and execute command
        cmd = method['cmd']()
        subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        
        # Check if rebuild was successful
        if os.path.exists(output_file) and os.path.getsize(output_file) > 10000:
            # Verify the file is valid
            if check_mp4_file(output_file):
                print(f"✓ Rebuild method {i+1} successful")
                return True
            else:
                print(f"✗ Rebuild method {i+1} created a file but verification failed")
                os.remove(output_file)
        else:
            print(f"✗ Rebuild method {i+1} failed")
    
    # If all methods failed, return failure
    return False

def repair_file(input_file: str, reference_file: str, output_file: str) -> bool:
    """Repair a damaged MP4 file using advanced FFmpeg techniques."""
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
        
        # Try advanced extraction methods
        has_video, has_audio, temp_video, temp_audio = try_advanced_extract(input_file, temp_dir)
        
        # We need at least video to proceed
        if not has_video:
            print("\n❌ Advanced extraction failed - could not extract video stream with any method")
            return False
        
        # Try advanced rebuilding methods
        if try_advanced_rebuild(temp_video, temp_audio, ref_params, output_file):
            print("\n✓ Successfully repaired file using advanced FFmpeg techniques")
            return True
        else:
            print("\n❌ All advanced rebuilding methods failed")
            return False
            
    except Exception as e:
        logger.error(f"Error during advanced FFmpeg repair: {str(e)}")
        print(f"Error during advanced FFmpeg repair: {str(e)}")
        return False
        
    finally:
        # Clean up
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Advanced FFmpeg Recovery Technique')
    parser.add_argument('input_file', help='Path to the damaged MP4 file')
    parser.add_argument('reference_file', help='Path to a working reference MP4 file')
    parser.add_argument('output_file', help='Path where the repaired file will be saved')
    
    args = parser.parse_args()
    
    # Print header
    print("\n" + "="*60)
    print(" "*15 + "ADVANCED FFMPEG TECHNIQUE")
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
        print("\nAdvanced FFmpeg technique failed to repair the file.")
        sys.exit(1)

if __name__ == "__main__":
    main()