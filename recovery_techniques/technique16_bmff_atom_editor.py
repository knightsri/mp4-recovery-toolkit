#!/usr/bin/env python3
"""
BMFF Low-Level Atom Editor (Technique 16) - Conceptual Python Reassembly

This script represents the idea of a low-level MP4 atom/box editor.
It performs a basic Python-based parsing of top-level atoms.
If essential atoms (ftyp, moov, mdat) are identified, it attempts to
reassemble them into a new file in a standard order (ftyp, moov, mdat).
This is a simplified demonstration of direct atom manipulation in Python.

A true implementation for comprehensive repair would require much more
detailed parsing of atom payloads (especially within moov) and sophisticated
logic for reconstructing or correcting corrupted atom data.

Usage:
    python technique16_bmff_atom_editor.py damaged.mp4 reference.mp4 output.mp4
"""

import os
import sys
import logging
import argparse
import struct
import subprocess # For ffprobe in check_mp4_file and potential fallback
import json       # For ffprobe in check_mp4_file
import shutil     # For fallback copy if all else fails
from typing import List, Tuple, Optional, Dict, Any, BinaryIO

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mp4_recovery_technique16')

FFMPEG_CMD = 'ffmpeg'     # Defined for check_mp4_file and potential fallback
FFPROBE_CMD = 'ffprobe'   # Defined for check_mp4_file

# --- Atom Class Definition (Simplified) ---
class Atom:
    def __init__(self, type_code: bytes, size: int, offset: int, header_size: int):
        self.type_code_bytes: bytes = type_code
        try:
            self.type: str = type_code.decode('ascii')
        except UnicodeDecodeError:
            self.type: str = f"0x{type_code.hex()}"
        self.size: int = size # Full size including header
        self.offset: int = offset # Absolute offset in file
        self.header_size: int = header_size # Size of the size+type fields (8 or 16)
        self.data_offset: int = offset + header_size # Where actual payload or children start
        self.data_size: int = size - header_size

    def __repr__(self):
        return f"<Atom type='{self.type}' size={self.size} offset={self.offset} data_size={self.data_size}>"

def read_atom_header(f: BinaryIO, current_file_offset: int) -> Optional[Tuple[bytes, int, int]]:
    """Reads atom header, returns (type, full_size, header_size)"""
    f.seek(current_file_offset)
    header_prefix = f.read(8)
    if len(header_prefix) < 8: return None

    size32 = struct.unpack('>I', header_prefix[:4])[0]
    type_code = header_prefix[4:8]
    
    header_size = 8
    full_size = size32

    if size32 == 1: # 64-bit extended size
        size64_bytes = f.read(8)
        if len(size64_bytes) < 8: return None
        full_size = struct.unpack('>Q', size64_bytes)[0]
        header_size = 16
    elif size32 == 0: # Extends to end of file
        pass # Caller needs to handle this using file_size

    if full_size !=0 and full_size < header_size:
        logger.warning(f"Atom '{type_code.decode('ascii','ignore')}' at {current_file_offset} has invalid size {full_size} < header_size {header_size}.")
        return None
        
    return type_code, full_size, header_size

def parse_top_level_atoms(file_path: str) -> List[Atom]:
    atoms: List[Atom] = []
    file_size = os.path.getsize(file_path)
    
    with open(file_path, 'rb') as f:
        current_offset = 0
        while current_offset < file_size:
            header_info = read_atom_header(f, current_offset)
            if not header_info:
                logger.debug(f"No more valid atom headers at offset {current_offset}.")
                # Try to find next atom by scanning (very basic error recovery)
                # This part could be much more sophisticated
                f.seek(current_offset + 1)
                scan_pos = current_offset + 1
                found_next = False
                # A real scanner would look for known 4CCs
                # For now, just advance if a simple header read fails
                if scan_pos < file_size -8: # Check if enough space for another header
                    current_offset = scan_pos
                    continue
                else:
                    break # Cannot scan further


            type_code, atom_full_size, atom_header_size = header_info

            if atom_full_size == 0: # Atom extends to end of file
                if type_code == b'mdat': # Common for mdat
                    atom_full_size = file_size - current_offset
                else: # Problematic for other types if not last atom
                    logger.warning(f"Atom '{type_code.decode('ascii','ignore')}' at {current_offset} has size 0 but isn't mdat. Assuming it extends to EOF.")
                    atom_full_size = file_size - current_offset
            
            if current_offset + atom_full_size > file_size:
                logger.warning(f"Atom '{type_code.decode('ascii','ignore')}' at {current_offset} with size {atom_full_size} "
                               f"exceeds file size {file_size}. Truncating atom size.")
                atom_full_size = file_size - current_offset
            
            if atom_full_size < atom_header_size:
                logger.warning(f"Atom '{type_code.decode('ascii','ignore')}' at {current_offset} has effective size {atom_full_size} < header size {atom_header_size}. Skipping.")
                current_offset +=1 # Try to recover by advancing one byte
                continue


            atom = Atom(type_code, atom_full_size, current_offset, atom_header_size)
            atoms.append(atom)
            logger.info(f"  Parsed top-level: {atom}")
            
            current_offset += atom_full_size
            if atom_full_size == 0 : break # Should not happen if size 0 was resolved
    return atoms

def check_mp4_file(file_path: str, min_duration_sec: float = 0.1) -> bool:
    """Checks if an MP4 file is valid and has a minimum duration using ffprobe."""
    # (Using the version from technique17 for consistency - ensure it's robust)
    if not os.path.exists(file_path) or os.path.getsize(file_path) < 256:
        return False
    try:
        cmd = [FFPROBE_CMD, '-v', 'error', '-show_format', '-show_streams', '-of', 'json', file_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False, timeout=15)
        if result.returncode != 0 or not result.stdout:
            logger.warning(f"check_mp4_file: ffprobe failed or no output for {file_path}. Stderr: {result.stderr.strip()}")
            return False
        
        info = json.loads(result.stdout)
        if not info.get('streams'): 
            logger.warning(f"check_mp4_file: No streams in {file_path}")
            return False
        duration_str = info.get('format', {}).get('duration')
        if duration_str:
            try:
                if float(duration_str) < min_duration_sec: 
                    logger.warning(f"check_mp4_file: Duration {float(duration_str)}s < {min_duration_sec}s in {file_path}")
                    return False
            except ValueError:
                logger.warning(f"check_mp4_file: Non-float duration '{duration_str}' in {file_path}")
                return False
        else: 
            logger.warning(f"check_mp4_file: No duration info in {file_path}")
            return False 
        
        cmd_check_ffmpeg = [FFMPEG_CMD, '-v', 'error', '-i', file_path, '-f', 'null', '-']
        result_check_ffmpeg = subprocess.run(cmd_check_ffmpeg, stderr=subprocess.PIPE, text=True, check=False, timeout=15)
        is_good = result_check_ffmpeg.stderr.strip() == '' and result_check_ffmpeg.returncode == 0
        if not is_good:
             logger.warning(f"check_mp4_file: FFmpeg found errors in {file_path}:\n{result_check_ffmpeg.stderr.strip()}")
        return is_good
    except subprocess.TimeoutExpired:
        logger.warning(f"check_mp4_file: ffprobe/ffmpeg timed out for {file_path}")
        return False
    except json.JSONDecodeError:
        logger.warning(f"check_mp4_file: ffprobe output {file_path} not valid JSON.")
        return False
    except Exception as e:
        logger.error(f"check_mp4_file: Unexpected error for {file_path}: {e}", exc_info=True)
        return False


def attempt_python_reassembly(input_file: str, output_file: str, atoms: List[Atom]) -> bool:
    """
    Attempts to reassemble a new MP4 by writing ftyp, moov, then mdat (if found)
    from the original file based on parsed atom information.
    This is a very simplified structural reassembly.
    """
    logger.info("Attempting Python-based atom reassembly...")
    ftyp_atom: Optional[Atom] = next((a for a in atoms if a.type == 'ftyp'), None)
    moov_atom: Optional[Atom] = next((a for a in atoms if a.type == 'moov'), None)
    mdat_atom: Optional[Atom] = next((a for a in atoms if a.type == 'mdat'), None)

    if not (ftyp_atom and moov_atom and mdat_atom):
        logger.warning("Essential atoms (ftyp, moov, mdat) not all found or parsed correctly by Python parser. Cannot perform Python reassembly.")
        return False

    # Ensure atoms are valid in terms of size and offset before trying to read
    if not (ftyp_atom.size > 0 and moov_atom.size > 0 and mdat_atom.size > 0):
        logger.warning("One or more essential atoms has zero or invalid size. Cannot perform Python reassembly.")
        return False

    try:
        with open(input_file, 'rb') as f_in, open(output_file, 'wb') as f_out:
            # Write ftyp
            logger.debug(f"Writing ftyp (offset {ftyp_atom.offset}, size {ftyp_atom.size})")
            f_in.seek(ftyp_atom.offset)
            f_out.write(f_in.read(ftyp_atom.size))

            # Write moov (for faststart-like behavior)
            logger.debug(f"Writing moov (offset {moov_atom.offset}, size {moov_atom.size})")
            f_in.seek(moov_atom.offset)
            f_out.write(f_in.read(moov_atom.size))

            # Write mdat
            logger.debug(f"Writing mdat (offset {mdat_atom.offset}, size {mdat_atom.size})")
            f_in.seek(mdat_atom.offset)
            # Handle potentially large mdat by copying in chunks
            remaining_size = mdat_atom.size
            chunk_size = 1024 * 1024 # 1MB chunks
            while remaining_size > 0:
                read_size = min(chunk_size, remaining_size)
                chunk_data = f_in.read(read_size)
                if not chunk_data:
                    logger.error(f"Unexpected EOF while reading mdat data. Expected {remaining_size} more bytes.")
                    return False # Failed to read full mdat
                f_out.write(chunk_data)
                remaining_size -= len(chunk_data)
        
        logger.info(f"Python-based reassembly written to {output_file}")
        return check_mp4_file(output_file) # Validate the reassembled file
    except Exception as e:
        logger.error(f"Error during Python-based atom reassembly: {e}", exc_info=True)
        return False


def repair_file(input_file: str, reference_file: str, output_file: str) -> bool:
    logger.info(f"Starting Conceptual BMFF Atom Editor (Technique 16) for {input_file}")
    logger.info("This script performs basic Python-based atom parsing and attempts a simple reassembly.")
    logger.info("If Python reassembly fails or is not possible, it falls back to an FFmpeg copy.")

    if not os.path.exists(input_file):
        logger.error(f"Input file not found: {input_file}")
        return False
    if os.path.getsize(input_file) == 0:
        logger.error(f"Input file is empty: {input_file}")
        return False


    parsed_top_level_atoms = parse_top_level_atoms(input_file)
    
    if not parsed_top_level_atoms:
        logger.warning("No top-level atoms parsed by Python. Attempting direct FFmpeg copy.")
    elif attempt_python_reassembly(input_file, output_file, parsed_top_level_atoms):
        logger.info("Python-based atom reassembly successful and output is valid.")
        return True
    else:
        logger.warning("Python-based atom reassembly failed or produced invalid output.")
        if os.path.exists(output_file): # Clean up failed Python attempt
            try: os.remove(output_file)
            except OSError: pass

    # Fallback to FFmpeg if Python reassembly failed or wasn't possible
    logger.info("Attempting a simple FFmpeg copy as a fallback for Technique 16.")
    cmd_copy = [FFMPEG_CMD, '-y', '-i', input_file, '-c', 'copy', '-movflags', '+faststart', '-loglevel', 'error', output_file]
    if os.path.exists(output_file): os.remove(output_file) # Clean before FFmpeg attempt
    try:
        result = subprocess.run(cmd_copy, check=True, capture_output=True, text=True, timeout=120)
        if check_mp4_file(output_file):
            logger.info(f"Fallback FFmpeg copy successful for Technique 16: {output_file}")
            return True
        else:
            logger.error(f"Fallback FFmpeg copy produced invalid output. Stderr (if any): {result.stderr.strip()}")
            if os.path.exists(output_file): os.remove(output_file)
            return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during fallback FFmpeg copy (CalledProcessError): {e.stderr.strip()}")
    except subprocess.TimeoutExpired:
        logger.error("Fallback FFmpeg copy timed out.")
    except Exception as e_gen:
        logger.error(f"General error during fallback FFmpeg copy: {e_gen}", exc_info=True)
    
    if os.path.exists(output_file): os.remove(output_file) # Final cleanup on failure
    logger.error("Technique 16 (Conceptual BMFF Atom Editor) did not result in a verified repaired file.")
    return False

def main():
    parser = argparse.ArgumentParser(description='Conceptual BMFF Atom Editor MP4 Repair Technique 16')
    parser.add_argument('input_file', help='Path to the damaged MP4 file')
    parser.add_argument('reference_file', help='Path to a working reference MP4 file (usage minimal in this version)')
    parser.add_argument('output_file', help='Path where the repaired file will be saved')
    args = parser.parse_args()

    output_dir = os.path.dirname(args.output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    if repair_file(args.input_file, args.reference_file, args.output_file):
        logger.info(f"Technique 16 completed. Output at {args.output_file}")
        sys.exit(0)
    else:
        logger.error(f"Technique 16 failed for {args.input_file}.")
        sys.exit(1)

if __name__ == "__main__":
    main()