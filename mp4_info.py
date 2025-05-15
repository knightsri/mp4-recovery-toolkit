#!/usr/bin/env python3
"""
MP4 Parameter Extraction Tool

This utility extracts and displays the key parameters of an MP4 file 
to help with diagnostics and comparison between files.

Author: Your Name
License: MIT
GitHub: https://github.com/yourusername/mp4-repair-tool

Usage:
    python mp4_info.py <mp4_file>
"""

import sys
import os
import subprocess
import json
import argparse
from typing import Optional, Dict, Any

def extract_mp4_parameters(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Extract key parameters from an MP4 file.
    
    Args:
        file_path: Path to the MP4 file
    
    Returns:
        dict: Parameters extracted from the file, or None if extraction failed
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            print(f"Error: File does not exist: {file_path}")
            return None
            
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
            print(f"Failed to extract parameters from {file_path}")
            return None
        
        # Parse the JSON output
        info = json.loads(result.stdout)
        
        # Initialize parameter dict
        params = {
            "video": {},
            "audio": {},
            "container": {},
            "other": {}
        }
        
        # Extract container-level parameters
        if 'format' in info:
            format_info = info['format']
            params['container'] = {
                'format_name': format_info.get('format_name', 'unknown'),
                'duration': format_info.get('duration', 'unknown'),
                'bit_rate': format_info.get('bit_rate', 'unknown'),
                'size': format_info.get('size', 'unknown'),
                'tags': format_info.get('tags', {})
            }
        
        # Extract stream parameters
        if 'streams' in info:
            for stream in info['streams']:
                # Video stream parameters
                if stream.get('codec_type') == 'video':
                    params['video'] = {
                        'codec': stream.get('codec_name', 'unknown'),
                        'profile': stream.get('profile', 'unknown'),
                        'bit_rate': stream.get('bit_rate', 'unknown'),
                        'frame_rate': stream.get('r_frame_rate', 'unknown'),
                        'width': stream.get('width', 0),
                        'height': stream.get('height', 0),
                        'pixel_format': stream.get('pix_fmt', 'unknown'),
                        'scan_type': 'progressive' if stream.get('field_order', '') == 'progressive' else 'interlaced',
                        'color_space': stream.get('color_space', 'unknown'),
                        'color_range': stream.get('color_range', 'unknown'),
                        'level': stream.get('level', 'unknown')
                    }
                
                # Audio stream parameters
                elif stream.get('codec_type') == 'audio':
                    params['audio'] = {
                        'codec': stream.get('codec_name', 'unknown'),
                        'bit_rate': stream.get('bit_rate', 'unknown'),
                        'sample_rate': stream.get('sample_rate', 'unknown'),
                        'channels': stream.get('channels', 0),
                        'channel_layout': stream.get('channel_layout', 'unknown'),
                        'sample_fmt': stream.get('sample_fmt', 'unknown')
                    }
        
        # Get additional container structure info using a more specialized command
        box_cmd = [
            'ffprobe', 
            '-v', 'trace', 
            '-select_streams', 'v',
            '-show_entries', 'stream=index,codec_name:stream_tags=',
            file_path
        ]
        
        box_result = subprocess.run(
            box_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Parse the output to extract box structure info
        box_trace = box_result.stderr
        
        # Look for atom structure in the trace output
        atom_info = []
        for line in box_trace.split('\n'):
            if 'atom ' in line and '(' in line and 'size=' in line:
                atom_info.append(line.strip())
        
        # Store atom structure info
        params['container']['atom_structure'] = atom_info[:20]  # Just store first 20 entries
        
        return params
            
    except Exception as e:
        print(f"Error extracting parameters from {file_path}: {str(e)}")
        return None

def display_parameters(params: Dict[str, Any], detailed: bool = False):
    """
    Display the extracted parameters in a formatted way.
    
    Args:
        params: Dictionary of parameters
        detailed: Whether to show detailed information
    """
    # Function to convert bits to readable format
    def format_bitrate(bitrate):
        if bitrate == 'unknown':
            return 'unknown'
        try:
            bitrate = int(bitrate)
            if bitrate > 1000000:
                return f"{bitrate/1000000:.2f} Mbps"
            else:
                return f"{bitrate/1000:.2f} kbps"
        except:
            return bitrate
    
    # Function to convert bytes to readable format
    def format_size(size):
        if size == 'unknown':
            return 'unknown'
        try:
            size = int(size)
            if size > 1073741824:  # 1 GB
                return f"{size/1073741824:.2f} GB"
            elif size > 1048576:  # 1 MB
                return f"{size/1048576:.2f} MB"
            elif size > 1024:  # 1 KB
                return f"{size/1024:.2f} KB"
            else:
                return f"{size} bytes"
        except:
            return size
    
    print("\n===== MP4 FILE INFORMATION =====")
    print(f"Container Format: {params['container'].get('format_name', 'unknown')}")
    print(f"File Size: {format_size(params['container'].get('size', 'unknown'))}")
    print(f"Duration: {params['container'].get('duration', 'unknown')} seconds")
    print(f"Overall Bitrate: {format_bitrate(params['container'].get('bit_rate', 'unknown'))}")
    
    print("\n----- Video Stream -----")
    if params['video']:
        v = params['video']
        print(f"Codec: {v.get('codec', 'unknown')}")
        print(f"Profile: {v.get('profile', 'unknown')}")
        print(f"Resolution: {v.get('width', 'unknown')}x{v.get('height', 'unknown')}")
        print(f"Frame Rate: {v.get('frame_rate', 'unknown')}")
        print(f"Bitrate: {format_bitrate(v.get('bit_rate', 'unknown'))}")
        print(f"Pixel Format: {v.get('pixel_format', 'unknown')}")
        print(f"Scan Type: {v.get('scan_type', 'unknown')}")
        
        if detailed:
            print(f"Color Space: {v.get('color_space', 'unknown')}")
            print(f"Color Range: {v.get('color_range', 'unknown')}")
            print(f"Level: {v.get('level', 'unknown')}")
    else:
        print("No video stream found")
    
    print("\n----- Audio Stream -----")
    if params['audio']:
        a = params['audio']
        print(f"Codec: {a.get('codec', 'unknown')}")
        print(f"Sample Rate: {a.get('sample_rate', 'unknown')} Hz")
        print(f"Channels: {a.get('channels', 'unknown')}")
        print(f"Channel Layout: {a.get('channel_layout', 'unknown')}")
        print(f"Bitrate: {format_bitrate(a.get('bit_rate', 'unknown'))}")
        
        if detailed:
            print(f"Sample Format: {a.get('sample_fmt', 'unknown')}")
    else:
        print("No audio stream found")
    
    if detailed:
        print("\n----- Container Structure -----")
        print("First 10 atoms/boxes:")
        atom_structure = params['container'].get('atom_structure', [])
        for i, atom in enumerate(atom_structure[:10]):
            print(f"  {i+1}. {atom}")
        
        print("\n----- Metadata Tags -----")
        tags = params['container'].get('tags', {})
        if tags:
            for key, value in tags.items():
                print(f"{key}: {value}")
        else:
            print("No metadata tags found")

def main():
    """Main function to parse arguments and display MP4 information."""
    parser = argparse.ArgumentParser(description='MP4 Parameter Extraction Tool')
    parser.add_argument('mp4_file', help='Path to the MP4 file to analyze')
    parser.add_argument('-d', '--detailed', action='store_true', help='Show detailed information')
    
    args = parser.parse_args()
    
    # Check if FFprobe is available
    try:
        subprocess.run(['ffprobe', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("Error: FFprobe not found. Please install FFmpeg and FFprobe.")
        sys.exit(1)
    
    # Extract and display parameters
    params = extract_mp4_parameters(args.mp4_file)
    if params:
        display_parameters(params, args.detailed)
    else:
        print(f"Failed to extract parameters from {args.mp4_file}")
        sys.exit(1)

if __name__ == "__main__":
    main()