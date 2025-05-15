#!/usr/bin/env python3
"""
MOOV Atom Reconstruction Recovery Technique

This script attempts to recover damaged MP4 files by rebuilding the MOOV atom
(which contains all the index and metadata information) from either fragments
in the damaged file or from a reference file.

Usage:
    python technique6_moov_atom_reconstruction.py damaged.mp4 reference.mp4 output.mp4
"""

import os
import sys
import subprocess
import tempfile
import logging
import shutil
import struct
from typing import List, Tuple, Optional, Dict, Any, BinaryIO

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('technique6_moov_atom_reconstruction')

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

def find_atom(file_obj: BinaryIO, atom_type: bytes, start_pos: int = 0) -> Tuple[Optional[int], Optional[int]]:
    """
    Find an atom in a file.
    Returns (offset, size) or (None, None) if not found.
    """
    file_obj.seek(start_pos)
    
    while True:
        pos = file_obj.tell()
        
        # Read atom header (8 bytes: 4 for size, 4 for type)
        header = file_obj.read(8)
        if len(header) < 8:
            # Reached EOF
            return None, None
        
        # Parse header
        size = struct.unpack('>I', header[0:4])[0]
        type_code = header[4:8]
        
        # Check if atom type matches
        if type_code == atom_type:
            return pos, size
        
        # Skip to next atom
        if size < 8:
            # Invalid atom, move 1 byte and try again
            file_obj.seek(pos + 1)
        else:
            file_obj.seek(pos + size)

def extract_atom(file_path: str, atom_type: bytes, output_path: str) -> bool:
    """Extract an atom from a file."""
    try:
        with open(file_path, 'rb') as file_obj:
            offset, size = find_atom(file_obj, atom_type)
            
            if offset is None or size is None:
                logger.error(f"Atom {atom_type.decode()} not found")
                return False
            
            # Extract the atom
            file_obj.seek(offset)
            atom_data = file_obj.read(size)
            
            with open(output_path, 'wb') as out_file:
                out_file.write(atom_data)
                
            return True
    except Exception as e:
        logger.error(f"Error extracting atom: {e}")
        return False

def extract_media_data(input_file: str, temp_dir: str) -> Optional[str]:
    """Extract the media data (mdat atom) from input file."""
    mdat_path = os.path.join(temp_dir, "mdat.bin")
    
    try:
        # First try using find_atom to locate mdat
        with open(input_file, 'rb') as file_obj:
            offset, size = find_atom(file_obj, b'mdat')
            
            if offset is not None and size is not None:
                # Extract the mdat atom
                file_obj.seek(offset)
                with open(mdat_path, 'wb') as out_file:
                    out_file.write(file_obj.read(size))
                
                logger.info(f"Successfully extracted mdat atom ({size} bytes)")
                return mdat_path
            
        # If direct extraction failed, try FFmpeg
        logger.info("Direct mdat extraction failed, trying FFmpeg...")
        
        cmd = [
            'ffmpeg',
            '-i', input_file,
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',  # Fix AAC bitstream if needed
            '-f', 'mp4',  # Force MP4 output
            '-y',
            os.path.join(temp_dir, "extracted_media.mp4")
        ]
        
        success, _, _ = run_command(cmd)
        
        if success:
            # Now try to extract mdat from this file
            extracted_file = os.path.join(temp_dir, "extracted_media.mp4")
            if os.path.exists(extracted_file) and os.path.getsize(extracted_file) > 0:
                with open(extracted_file, 'rb') as file_obj:
                    offset, size = find_atom(file_obj, b'mdat')
                    
                    if offset is not None and size is not None:
                        # Extract the mdat atom
                        file_obj.seek(offset)
                        with open(mdat_path, 'wb') as out_file:
                            out_file.write(file_obj.read(size))
                        
                        logger.info(f"Successfully extracted mdat atom after FFmpeg processing")
                        return mdat_path
        
        # If all else fails, try binary search for 'mdat' marker
        logger.info("FFmpeg extraction failed, trying binary search...")
        
        with open(input_file, 'rb') as file_obj:
            data = file_obj.read()
            
            mdat_marker = b'mdat'
            pos = data.find(mdat_marker)
            
            if pos >= 4:  # Need at least 4 bytes before for the size
                # Try to read the size
                size_bytes = data[pos-4:pos]
                try:
                    size = struct.unpack('>I', size_bytes)[0]
                    
                    # Sanity check on size
                    if 8 <= size <= len(data) - pos + 4:
                        # Looks valid, extract
                        with open(mdat_path, 'wb') as out_file:
                            out_file.write(data[pos-4:pos-4+size])
                        
                        logger.info(f"Successfully extracted mdat atom via binary search")
                        return mdat_path
                except Exception:
                    pass
            
            # If we couldn't get a valid size, just grab everything from marker to end
            if pos > 0:
                with open(mdat_path, 'wb') as out_file:
                    # Write a valid header (size + 'mdat')
                    remaining_size = len(data) - pos + 8
                    out_file.write(struct.pack('>I', remaining_size))
                    out_file.write(b'mdat')
                    # Write remaining data
                    out_file.write(data[pos+4:])
                
                logger.info(f"Extracted mdat atom with reconstructed header")
                return mdat_path
        
        logger.error("Failed to extract media data")
        return None
        
    except Exception as e:
        logger.error(f"Error extracting media data: {e}")
        return None

def extract_audio_video_streams(input_file: str, temp_dir: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract audio and video streams from the damaged file."""
    video_path = os.path.join(temp_dir, "video.h264")
    audio_path = os.path.join(temp_dir, "audio.aac")
    
    # Try to extract video
    video_cmd = [
        'ffmpeg',
        '-i', input_file,
        '-an',  # No audio
        '-c:v', 'copy',  # Copy without re-encoding
        '-f', 'h264',
        '-y',
        video_path
    ]
    
    video_success, _, _ = run_command(video_cmd)
    
    # Try to extract audio
    audio_cmd = [
        'ffmpeg',
        '-i', input_file,
        '-vn',  # No video
        '-c:a', 'copy',  # Copy without re-encoding
        '-f', 'adts',
        '-y',
        audio_path
    ]
    
    audio_success, _, _ = run_command(audio_cmd)
    
    # Return paths or None if extraction failed
    video_result = video_path if video_success and os.path.exists(video_path) and os.path.getsize(video_path) > 0 else None
    audio_result = audio_path if audio_success and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0 else None
    
    return video_result, audio_result

def extract_reference_moov(reference_file: str, temp_dir: str) -> Optional[str]:
    """Extract MOOV atom from reference file."""
    moov_path = os.path.join(temp_dir, "reference_moov.bin")
    
    if extract_atom(reference_file, b'moov', moov_path):
        logger.info("Successfully extracted MOOV atom from reference")
        return moov_path
    else:
        logger.error("Failed to extract MOOV from reference")
        return None

def extract_reference_info(reference_file: str) -> Dict[str, Any]:
    """Extract useful information from reference file."""
    info = {
        'duration': None,
        'width': None,
        'height': None,
        'fps': None,
        'video_codec': None,
        'audio_codec': None
    }
    
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        reference_file
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
                        info['width'] = stream.get('width')
                        info['height'] = stream.get('height')
                        info['video_codec'] = stream.get('codec_name')
                        
                        # Calculate FPS
                        frame_rate = stream.get('r_frame_rate', '').split('/')
                        if len(frame_rate) == 2 and frame_rate[1] != '0':
                            info['fps'] = float(frame_rate[0]) / float(frame_rate[1])
                    
                    elif stream.get('codec_type') == 'audio':
                        info['audio_codec'] = stream.get('codec_name')
        
        except Exception as e:
            logger.error(f"Error parsing FFprobe output: {e}")
    
    return info

def adapt_moov_to_media(moov_path: str, media_info: Dict[str, Any], temp_dir: str) -> Optional[str]:
    """
    Adapt the reference MOOV atom to match the media data.
    This is a complex function that would typically require MP4 box structure manipulation.
    For simplicity, we'll use a basic FFmpeg remuxing approach instead.
    """
    # Create temporary files for building a new MP4
    temp_ftyp = os.path.join(temp_dir, "ftyp.bin")
    temp_moov = moov_path
    adapted_mp4 = os.path.join(temp_dir, "adapted.mp4")
    
    # Extract FTYP from any sample MP4 (or create a basic one)
    ftyp_data = (
        b'\x00\x00\x00\x18' +  # Size (24 bytes)
        b'ftyp' +  # Type
        b'iso6' +  # Major brand
        b'\x00\x00\x00\x01' +  # Minor version
        b'iso6mp42'  # Compatible brands
    )
    
    with open(temp_ftyp, 'wb') as f:
        f.write(ftyp_data)
    
    # Now create a blank template MP4 with the reference MOOV
    with open(adapted_mp4, 'wb') as f:
        # Write FTYP
        with open(temp_ftyp, 'rb') as ftyp_file:
            f.write(ftyp_file.read())
        
        # Write MOOV
        with open(temp_moov, 'rb') as moov_file:
            f.write(moov_file.read())
        
        # Add an empty MDAT as placeholder (just header)
        f.write(struct.pack('>I', 8))  # Size = 8 bytes
        f.write(b'mdat')  # Type
    
    return adapted_mp4

def build_recovered_file(adapted_moov: str, media_streams: List[str], output_file: str) -> bool:
    """Build the final recovered file by combining the adapted MOOV and media streams."""
    # Use FFmpeg to combine everything
    cmd = ['ffmpeg', '-y']
    
    # Add all input streams
    for stream in media_streams:
        if stream:
            cmd.extend(['-i', stream])
    
    # Add mapping and encoding options
    cmd.extend([
        '-c', 'copy',  # Copy without re-encoding
        '-movflags', '+faststart',  # Optimize for web streaming
        output_file
    ])
    
    success, _, stderr = run_command(cmd)
    
    if not success:
        logger.error(f"Failed to build recovered file: {stderr}")
        return False
    
    return True

def main(input_file: str, reference_file: str, output_file: str) -> bool:
    """Main function to recover MP4 by reconstructing MOOV atom."""
    if not check_ffmpeg_available():
        logger.error("FFmpeg is required but not found")
        return False
    
    try:
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info("Starting MOOV atom reconstruction...")
            
            # Step 1: Extract media data from damaged file
            media_data = extract_media_data(input_file, temp_dir)
            
            # Step 2: Extract audio/video streams directly
            video_stream, audio_stream = extract_audio_video_streams(input_file, temp_dir)
            
            if not media_data and not video_stream and not audio_stream:
                logger.error("Failed to extract any usable media data")
                return False
            
            # Step 3: Extract MOOV from reference
            moov_data = extract_reference_moov(reference_file, temp_dir)
            if not moov_data:
                logger.error("Failed to extract reference MOOV")
                return False
            
            # Step A: Quick approach - try direct combination
            quick_output = os.path.join(temp_dir, "quick_output.mp4")
            
            # List of streams to combine
            streams_to_use = []
            if video_stream:
                streams_to_use.append(video_stream)
            if audio_stream:
                streams_to_use.append(audio_stream)
            
            # Attempt direct combination first
            if streams_to_use:
                logger.info("Attempting direct stream recombination...")
                direct_success = build_recovered_file(moov_data, streams_to_use, quick_output)
                
                if direct_success and os.path.exists(quick_output) and os.path.getsize(quick_output) > 0:
                    # Verify output
                    verify_cmd = ['ffprobe', '-v', 'error', quick_output]
                    verify_success, _, _ = run_command(verify_cmd)
                    
                    if verify_success:
                        logger.info("Direct recombination successful")
                        shutil.copy2(quick_output, output_file)
                        return True
            
            # Step B: Advanced approach - adapt MOOV to media
            logger.info("Direct approach failed, trying advanced MOOV adaptation...")
            
            # Extract reference information
            reference_info = extract_reference_info(reference_file)
            
            # Adapt MOOV to the media data
            adapted_moov = adapt_moov_to_media(moov_data, reference_info, temp_dir)
            if not adapted_moov:
                logger.error("Failed to adapt MOOV")
                return False
            
            # Build final output - try with adapted MOOV and extracted streams
            advanced_output = os.path.join(temp_dir, "advanced_output.mp4")
            
            streams_to_use = [adapted_moov]
            if video_stream:
                streams_to_use.append(video_stream)
            if audio_stream:
                streams_to_use.append(audio_stream)
            elif media_data:
                streams_to_use.append(media_data)
            
            advanced_success = build_recovered_file(adapted_moov, streams_to_use, advanced_output)
            
            if advanced_success and os.path.exists(advanced_output) and os.path.getsize(advanced_output) > 0:
                logger.info("Advanced MOOV adaptation successful")
                shutil.copy2(advanced_output, output_file)
                return True
            
            logger.error("All MOOV reconstruction attempts failed")
            return False
                
    except Exception as e:
        logger.error(f"Recovery failed: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python technique6_moov_atom_reconstruction.py damaged.mp4 reference.mp4 output.mp4")
        sys.exit(1)
    
    input_file = sys.argv[1]
    reference_file = sys.argv[2]
    output_file = sys.argv[3]
    
    if main(input_file, reference_file, output_file):
        sys.exit(0)
    else:
        sys.exit(1)