#!/usr/bin/env python3
"""
Raw NAL Extraction Technique (Technique 3)

This technique extracts H.264 NAL units directly from the file using
binary pattern matching, bypassing the container structure completely.

Usage:
    python technique3_raw_nal_extraction.py damaged.mp4 reference.mp4 output.mp4
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

def extract_h264_nal_units(input_file: str, output_file: str) -> bool:
    """Extract H.264 NAL units directly from file using binary pattern matching."""
    print("\nExtracting H.264 NAL units directly from file...")
    
    try:
        # NAL unit start code patterns
        nal_start_codes = [
            b'\x00\x00\x01',       # 3-byte start code
            b'\x00\x00\x00\x01'    # 4-byte start code
        ]
        
        # Open input file in binary mode
        with open(input_file, 'rb') as f:
            data = f.read()
        
        print(f"File size: {len(data)} bytes")
        
        # Initialize output buffer
        output_data = bytearray()
        
        # Look for the first NAL unit
        start_pos = -1
        for code in nal_start_codes:
            pos = data.find(code)
            if pos != -1:
                start_pos = pos
                break
        
        if start_pos == -1:
            print("❌ No H.264 NAL units found in file")
            return False
        
        print(f"First NAL unit found at position {start_pos}")
        
        # Extract all NAL units
        nal_count = 0
        
        # Build a lookup table for faster searches 
        # (this is what professional recovery tools often do)
        positions = []
        
        for code in nal_start_codes:
            pos = 0
            while True:
                pos = data.find(code, pos)
                if pos == -1:
                    break
                positions.append((pos, len(code)))
                pos += len(code)
        
        # Sort positions by their occurrence in the file
        positions.sort(key=lambda x: x[0])
        
        # Extract each NAL unit
        for i in range(len(positions)):
            start_pos = positions[i][0]
            code_len = positions[i][1]
            
            # Determine end position (next NAL unit or end of file)
            if i < len(positions) - 1:
                end_pos = positions[i+1][0]
            else:
                end_pos = len(data)
            
            # Extract NAL unit
            nal_unit = data[start_pos:end_pos]
            
            # Basic validation of NAL unit 
            # (check if it's large enough to be a valid unit and has valid type)
            if len(nal_unit) >= code_len + 1:
                nal_type = (nal_unit[code_len] & 0x1F)  # Extract NAL type from first byte after start code
                
                # Only include important NAL types (1=slice, 5=IDR, 7=SPS, 8=PPS)
                # This is a basic filter to exclude potential false positives
                if nal_type in [1, 5, 7, 8] and len(nal_unit) > 10:
                    output_data.extend(nal_unit)
                    nal_count += 1
        
        print(f"Extracted {nal_count} NAL units")
        
        # Write extracted data to output file
        if nal_count > 10:  # Only proceed if we found enough NAL units
            with open(output_file, 'wb') as f:
                f.write(output_data)
            
            print(f"✓ Successfully extracted H.264 NAL units to {output_file}")
            return True
        else:
            print("❌ Not enough valid NAL units found")
            return False
        
    except Exception as e:
        logger.error(f"Error extracting NAL units: {str(e)}")
        print(f"Error extracting NAL units: {str(e)}")
        return False

def extract_aac_frames(input_file: str, output_file: str) -> bool:
    """Extract AAC audio frames directly from file using binary pattern matching."""
    print("\nExtracting AAC audio frames directly from file...")
    
    try:
        # AAC frame markers
        aac_frame_markers = [
            b'\xFF\xF1',  # ADTS frame marker with Layer 1
            b'\xFF\xF9'   # ADTS frame marker with Layer 1 + CRC
        ]
        
        # Open input file in binary mode
        with open(input_file, 'rb') as f:
            data = f.read()
        
        # Initialize output buffer
        output_data = bytearray()
        
        # Look for AAC frames
        frame_count = 0
        for marker in aac_frame_markers:
            pos = 0
            while True:
                pos = data.find(marker, pos)
                if pos == -1:
                    break
                
                # Basic validation: Check if we have enough bytes for a header
                if pos + 7 < len(data):
                    # Extract ADTS header (7 bytes)
                    header = data[pos:pos+7]
                    
                    # Parse frame length from header 
                    # Length is a 13-bit field starting at bit 30
                    frame_length = ((header[3] & 0x03) << 11) | (header[4] << 3) | (header[5] >> 5)
                    
                    # Basic sanity check on frame length (must be reasonable)
                    if 7 < frame_length < 2048:
                        # Check if we have enough data for the full frame
                        if pos + frame_length <= len(data):
                            # Extract the full frame including header
                            frame = data[pos:pos+frame_length]
                            output_data.extend(frame)
                            frame_count += 1
                
                # Move past this marker
                pos += 2
        
        print(f"Extracted {frame_count} AAC frames")
        
        # Write extracted data to output file if we found enough frames
        if frame_count > 10:
            with open(output_file, 'wb') as f:
                f.write(output_data)
            
            print(f"✓ Successfully extracted AAC frames to {output_file}")
            return True
        else:
            print("❌ Not enough valid AAC frames found")
            return False
        
    except Exception as e:
        logger.error(f"Error extracting AAC frames: {str(e)}")
        print(f"Error extracting AAC frames: {str(e)}")
        return False

def rebuild_from_raw_streams(video_path: str, audio_path: str, ref_params: Dict[str, Any], output_file: str) -> bool:
    """Rebuild MP4 file from raw H.264 and AAC streams."""
    print("\nRebuilding MP4 file from raw streams...")
    
    try:
        # Check if we have video (required)
        has_video = os.path.exists(video_path) and os.path.getsize(video_path) > 1000
        if not has_video:
            print("❌ No valid video stream available")
            return False
        
        # Check if we have audio (optional)
        has_audio = os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000
        
        # Get reference parameters
        ref_width = ref_params['video'].get('width', 1280)
        ref_height = ref_params['video'].get('height', 720)
        ref_frame_rate = ref_params['video'].get('frame_rate', 30)
        
        # Build FFmpeg command to create MP4 from raw streams
        cmd = [
            'ffmpeg',
            # Force input format for video stream
            '-f', 'h264',
            # Force framerate
            '-framerate', str(ref_frame_rate),
            # Input video stream
            '-i', video_path
        ]
        
        # Add audio if available
        if has_audio:
            cmd.extend([
                # Force input format for audio stream
                '-f', 'aac',
                # Input audio stream
                '-i', audio_path
            ])
        
        # Add output options
        cmd.extend([
            # Video codec settings
            '-c:v', 'libx264',
            '-preset', 'slow',  # Higher quality transcoding
            # Force resolution from reference
            '-s', f"{ref_width}x{ref_height}",
            # Force keyframes
            '-g', '30',
            '-keyint_min', '30',
            # Map video stream
            '-map', '0:v'
        ])
        
        # Add audio mapping if available
        if has_audio:
            cmd.extend([
                # Audio codec settings
                '-c:a', 'aac',
                '-b:a', '128k',
                # Audio parameters from reference
                '-ac', str(ref_params['audio'].get('channels', 2)),
                '-ar', str(ref_params['audio'].get('sample_rate', 44100)),
                # Map audio stream
                '-map', '1:a'
            ])
        
        # Add output file options
        cmd.extend([
            # Optimize for streaming
            '-movflags', 'faststart',
            # Output file
            output_file
        ])
        
        # Execute FFmpeg command
        print("Executing FFmpeg to rebuild MP4...")
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Check if rebuild was successful
        if result.returncode == 0 and os.path.exists(output_file) and os.path.getsize(output_file) > 10000:
            print("✓ Successfully rebuilt MP4 file from raw streams")
            
            # Verify the file
            if check_mp4_file(output_file):
                print("✓ Rebuilt file validation successful")
                return True
            else:
                print("❌ Rebuilt file validation failed")
                if os.path.exists(output_file):
                    os.remove(output_file)
                return False
        else:
            print("❌ Failed to rebuild MP4 file")
            print(f"FFmpeg error: {result.stderr}")
            return False
        
    except Exception as e:
        logger.error(f"Error rebuilding MP4: {str(e)}")
        print(f"Error rebuilding MP4: {str(e)}")
        return False

def repair_file(input_file: str, reference_file: str, output_file: str) -> bool:
    """Repair a damaged MP4 file using raw NAL extraction technique."""
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
        
        # Extract raw H.264 NAL units
        temp_video = os.path.join(temp_dir, "extracted_video.h264")
        if not extract_h264_nal_units(input_file, temp_video):
            print("❌ Failed to extract H.264 NAL units")
            return False
        
        # Extract AAC frames (optional)
        temp_audio = os.path.join(temp_dir, "extracted_audio.aac")
        has_audio = extract_aac_frames(input_file, temp_audio)
        
        # Rebuild MP4 from raw streams
        if not rebuild_from_raw_streams(temp_video, temp_audio if has_audio else "", ref_params, output_file):
            print("❌ Failed to rebuild MP4 from raw streams")
            return False
        
        print("\n✓ Successfully repaired file using raw NAL extraction technique")
        return True
            
    except Exception as e:
        logger.error(f"Error during raw NAL extraction repair: {str(e)}")
        print(f"Error during raw NAL extraction repair: {str(e)}")
        return False
        
    finally:
        # Clean up
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Raw NAL Extraction Recovery Technique')
    parser.add_argument('input_file', help='Path to the damaged MP4 file')
    parser.add_argument('reference_file', help='Path to a working reference MP4 file')
    parser.add_argument('output_file', help='Path where the repaired file will be saved')
    
    args = parser.parse_args()
    
    # Print header
    print("\n" + "="*60)
    print(" "*15 + "RAW NAL EXTRACTION TECHNIQUE")
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
        print("\nRaw NAL extraction technique failed to repair the file.")
        sys.exit(1)

if __name__ == "__main__":
    main()