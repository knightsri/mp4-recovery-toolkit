#!/usr/bin/env python3
"""
Frame By Frame Recovery Technique

This script attempts to recover damaged MP4 files by extracting individual frames,
saving them as images, and then rebuilding a new video from these frames.

Usage:
    python technique7_frame_by_frame.py damaged.mp4 reference.mp4 output.mp4
"""

import os
import sys
import subprocess
import tempfile
import logging
import shutil
import glob
from typing import List, Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('technique7_frame_by_frame')

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

def get_video_info(input_file: str) -> dict:
    """Get video information using FFprobe."""
    info = {
        'duration': 0,
        'width': 0,
        'height': 0,
        'fps': 0,
        'has_audio': False,
        'video_codec': None,
        'audio_codec': None
    }
    
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        input_file
    ]
    
    success, stdout, _ = run_command(cmd)
    
    if success and stdout:
        import json
        try:
            data = json.loads(stdout)
            
            # Get general format info
            if 'format' in data:
                info['duration'] = float(data['format'].get('duration', 0))
            
            # Get stream info
            if 'streams' in data:
                for stream in data['streams']:
                    if stream.get('codec_type') == 'video':
                        info['width'] = stream.get('width', 0)
                        info['height'] = stream.get('height', 0)
                        info['video_codec'] = stream.get('codec_name')
                        
                        # Calculate FPS
                        frame_rate = stream.get('r_frame_rate', '').split('/')
                        if len(frame_rate) == 2 and frame_rate[1] != '0':
                            info['fps'] = float(frame_rate[0]) / float(frame_rate[1])
                    
                    elif stream.get('codec_type') == 'audio':
                        info['has_audio'] = True
                        info['audio_codec'] = stream.get('codec_name')
        
        except Exception as e:
            logger.error(f"Error parsing FFprobe output: {e}")
    
    return info

def extract_frames(input_file: str, frames_dir: str, reference_info: dict) -> int:
    """
    Extract frames from the damaged video.
    Returns the number of frames extracted.
    """
    # Create frames directory
    os.makedirs(frames_dir, exist_ok=True)
    
    # Use FFmpeg to extract frames
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-vsync', '0',  # Prevent frame dropping
        '-q:v', '1',    # Highest quality
        os.path.join(frames_dir, 'frame_%06d.png')
    ]
    
    success, _, stderr = run_command(cmd)
    
    if not success:
        # If standard extraction fails, try with error concealment
        logger.info("Standard frame extraction failed, trying with error concealment...")
        
        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-vsync', '0',
            '-err_detect', 'ignore_err',
            '-qscale:v', '1',
            os.path.join(frames_dir, 'frame_%06d.png')
        ]
        
        success, _, stderr = run_command(cmd)
    
    # Count number of extracted frames
    frame_files = glob.glob(os.path.join(frames_dir, 'frame_*.png'))
    num_frames = len(frame_files)
    
    logger.info(f"Extracted {num_frames} frames")
    
    if num_frames == 0:
        # If no frames could be extracted, try a more aggressive byte-by-byte approach
        logger.info("No frames extracted, trying raw frame extraction...")
        
        # Try to find the start of the first I-frame
        try:
            with open(input_file, 'rb') as f:
                data = f.read()
            
            # Search for common H.264 start codes
            # NAL unit start code: 0x00000001 or 0x000001
            i_frame_start = -1
            
            # Look for H.264 start code followed by I-frame NAL unit type
            for i in range(len(data) - 5):
                # Check for 4-byte start code: 0x00000001
                if (data[i] == 0 and data[i+1] == 0 and 
                    data[i+2] == 0 and data[i+3] == 1):
                    # NAL unit type is in the lower 5 bits of the first byte after start code
                    nal_type = data[i+4] & 0x1F
                    if nal_type == 5:  # IDR slice (I-frame)
                        i_frame_start = i
                        break
                
                # Check for 3-byte start code: 0x000001
                elif (i < len(data) - 4 and data[i] == 0 and 
                      data[i+1] == 0 and data[i+2] == 1):
                    nal_type = data[i+3] & 0x1F
                    if nal_type == 5:  # IDR slice (I-frame)
                        i_frame_start = i
                        break
            
            if i_frame_start >= 0:
                # Extract from this point to try and get some frames
                raw_h264_path = os.path.join(frames_dir, 'raw_stream.h264')
                with open(raw_h264_path, 'wb') as out_f:
                    out_f.write(data[i_frame_start:])
                
                # Try to extract frames from this raw data
                cmd = [
                    'ffmpeg',
                    '-i', raw_h264_path,
                    '-vsync', '0',
                    '-qscale:v', '1',
                    os.path.join(frames_dir, 'frame_%06d.png')
                ]
                
                run_command(cmd)
                
                # Count frames again
                frame_files = glob.glob(os.path.join(frames_dir, 'frame_*.png'))
                num_frames = len(frame_files)
                
                logger.info(f"Raw extraction resulted in {num_frames} frames")
        
        except Exception as e:
            logger.error(f"Raw frame extraction error: {e}")
    
    return num_frames

def extract_audio(input_file: str, temp_dir: str) -> Optional[str]:
    """Extract audio stream from the damaged file."""
    audio_path = os.path.join(temp_dir, "audio.aac")
    
    # Try to extract audio
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-vn',  # No video
        '-c:a', 'copy',  # Copy without re-encoding
        '-f', 'adts',
        audio_path
    ]
    
    success, _, _ = run_command(cmd)
    
    if success and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
        logger.info("Successfully extracted audio")
        return audio_path
    
    # If direct copy fails, try re-encoding
    logger.info("Direct audio extraction failed, trying re-encoding...")
    
    cmd = [
        'ffmpeg',
        '-i', input_file,
        '-vn',
        '-c:a', 'aac',  # Re-encode to AAC
        '-b:a', '128k',  # Decent quality
        audio_path
    ]
    
    success, _, _ = run_command(cmd)
    
    if success and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
        logger.info("Successfully extracted audio with re-encoding")
        return audio_path
    
    logger.warning("Failed to extract audio")
    return None

def rebuild_video(frames_dir: str, audio_path: Optional[str], output_file: str, reference_info: dict) -> bool:
    """Rebuild the video from extracted frames and audio."""
    # Get target FPS from reference or default to 30
    fps = reference_info.get('fps', 30)
    if fps <= 0:
        fps = 30
    
    # Path pattern for frames
    frames_pattern = os.path.join(frames_dir, 'frame_%06d.png')
    
    # Base command for video building
    cmd = [
        'ffmpeg',
        '-framerate', str(fps),
        '-i', frames_pattern
    ]
    
    # Add audio if available
    if audio_path:
        cmd.extend(['-i', audio_path])
    
    # Output settings
    cmd.extend([
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-preset', 'medium',
        '-crf', '23',  # Good quality/size balance
    ])
    
    # Add audio mapping if available
    if audio_path:
        cmd.extend([
            '-c:a', 'aac',
            '-b:a', '128k',
            '-map', '0:v',
            '-map', '1:a',
            '-shortest'  # End when shortest input ends
        ])
    
    # Add output path
    cmd.append(output_file)
    
    success, _, stderr = run_command(cmd)
    
    if not success:
        logger.error(f"Failed to rebuild video: {stderr}")
        return False
    
    return True

def main(input_file: str, reference_file: str, output_file: str) -> bool:
    """Main function to recover video by extracting and rebuilding frames."""
    if not check_ffmpeg_available():
        logger.error("FFmpeg is required but not found")
        return False
    
    try:
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info("Starting frame-by-frame recovery...")
            
            # Step 1: Get reference video information
            reference_info = get_video_info(reference_file)
            logger.info(f"Reference info: {reference_info}")
            
            # Step 2: Extract frames from damaged video
            frames_dir = os.path.join(temp_dir, "frames")
            num_frames = extract_frames(input_file, frames_dir, reference_info)
            
            if num_frames == 0:
                logger.error("Failed to extract any frames")
                return False
            
            # Step 3: Extract audio if possible
            audio_path = extract_audio(input_file, temp_dir)
            
            # Step 4: Rebuild video from frames and audio
            if rebuild_video(frames_dir, audio_path, output_file, reference_info):
                logger.info(f"Successfully rebuilt video with {num_frames} frames")
                return True
            else:
                logger.error("Failed to rebuild video")
                return False
                
    except Exception as e:
        logger.error(f"Recovery failed: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python technique7_frame_by_frame.py damaged.mp4 reference.mp4 output.mp4")
        sys.exit(1)
    
    input_file = sys.argv[1]
    reference_file = sys.argv[2]
    output_file = sys.argv[3]
    
    if main(input_file, reference_file, output_file):
        sys.exit(0)
    else:
        sys.exit(1)