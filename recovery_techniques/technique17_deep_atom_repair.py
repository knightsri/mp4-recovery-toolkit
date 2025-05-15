#!/usr/bin/env python3
"""
Deep Atom Structure Repair (Technique 17 - Python Centric)

This script aims to perform a comprehensive analysis and repair of the MP4
atom (box) structure using Python. It involves parsing the atom tree,
validating structural integrity, and attempting to rebuild or correct
corrupted atoms, especially within the MOOV atom and its children.

This is a complex technique and represents a significant implementation effort.
It will use a reference file heavily for guidance.

Usage:
    python technique17_deep_atom_repair.py damaged.mp4 reference.mp4 output.mp4
"""

import os
import sys
import struct
import logging
import subprocess # For FFmpeg/FFprobe as helpers or final validation
import shutil
import argparse
import json # <--- IMPORTED JSON
from typing import List, Tuple, Optional, Dict, Any, BinaryIO, Union

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('technique17_deep_atom_repair')

FFMPEG_CMD = 'ffmpeg'
FFPROBE_CMD = 'ffprobe'

# --- Atom Class Definition (More Detailed) ---
class Atom:
    def __init__(self, type_code: bytes, size: int, offset: int, header_size: int, payload_offset: int, is_extended_size: bool = False, version: Optional[int]=None, flags: Optional[int]=None):
        self.type_code_bytes: bytes = type_code
        try:
            self.type: str = type_code.decode('ascii')
        except UnicodeDecodeError:
            self.type: str = f"0x{type_code.hex()}" # Non-ascii type
        self.size: int = size # Full size including header
        self.offset: int = offset # Absolute offset in file
        self.header_size: int = header_size
        self.payload_offset: int = payload_offset # Offset to payload within the atom
        self.payload_size: int = size - header_size
        self.children: List[Atom] = []
        self.is_extended_size: bool = is_extended_size
        self.is_container: bool = type_code in [
            b'moov', b'trak', b'mdia', b'minf', b'stbl', b'udta', 
            b'meta', b'edts', b'dinf', b'ilst' # Added common containers
        ]
        self.valid: bool = True
        self.version: Optional[int] = version
        self.flags: Optional[int] = flags
        self.raw_payload_data: Optional[bytes] = None
        self.parsed_data: Dict[str, Any] = {}

    def __repr__(self, level=0):
        indent = "  " * level
        child_summary = f", {len(self.children)} children" if self.children else ""
        return (f"{indent}<Atom type='{self.type}' size={self.size} offset={self.offset} "
                f"payload_size={self.payload_size}{child_summary} valid={self.valid}>")

    def get_child(self, type_str: str) -> Optional['Atom']:
        for child in self.children:
            if child.type == type_str:
                return child
        return None

    def get_all_children(self, type_str: str) -> List['Atom']:
        return [child for child in self.children if child.type == type_str]

    def add_child(self, child_atom: 'Atom'):
        self.children.append(child_atom)

# --- Parser ---
FULL_BOX_TYPES = [
    b'mvhd', b'tkhd', b'mdhd', b'hdlr', b'stsd', b'stts', b'ctts', b'stsc',
    b'stsz', b'stz2', b'stco', b'co64', b'smhd', b'vmhd', b'hmhd', b'nmhd',
    b'elst', b'esds', b'meta', b'iloc', b'ipro', b'iinf', b'xml ', b'bxml',
    b'pitm', b'iref', b'meco', b'mere', b'dref', b'url ', b'urn ', b'mehd',
    b'trex', b'leva', b'sidx', b'ssix', b'prft'
]

def read_atom_header_unified(f: BinaryIO, current_file_offset: int) -> Optional[Tuple[bytes, int, int, int, bool, Optional[int], Optional[int]]]:
    f.seek(current_file_offset)
    header_prefix = f.read(8)
    if len(header_prefix) < 8: return None

    size32 = struct.unpack('>I', header_prefix[:4])[0]
    type_code = header_prefix[4:8]
    
    header_size = 8
    full_size = size32
    is_extended = False
    version, flags = None, None

    if size32 == 1:
        size64_bytes = f.read(8)
        if len(size64_bytes) < 8: return None
        full_size = struct.unpack('>Q', size64_bytes)[0]
        header_size = 16
        is_extended = True
    elif size32 == 0:
        pass 

    if type_code in FULL_BOX_TYPES:
        if full_size != 0 and full_size < header_size + 4 and not (size32==0): # Size 0 is special
             logger.debug(f"FullBox '{type_code.decode('ascii','ignore')}' at {current_file_offset} has size {full_size} too small for version/flags (header_size={header_size}). Reading as non-FullBox.")
        elif full_size == 0 or full_size >= header_size + 4: # Enough space for version/flags or size is 0
            vf_bytes = f.read(4)
            if len(vf_bytes) < 4:
                logger.warning(f"Could not read version/flags for FullBox '{type_code.decode('ascii','ignore')}' at {current_file_offset+header_size}.")
                # Potentially treat as non-FullBox or error
                return None # Or handle differently, for now assume error if vf_bytes not readable
            version = vf_bytes[0]
            flags = struct.unpack('>I', b'\x00' + vf_bytes[1:4])[0] & 0xFFFFFF
            header_size += 4
        else: # Not enough space, treat as non-FullBox for now
            logger.debug(f"Not enough space for version/flags in FullBox '{type_code.decode('ascii','ignore')}' at {current_file_offset}. Treating as standard box.")


    if full_size != 0 and full_size < header_size:
        logger.warning(f"Atom '{type_code.decode('ascii','ignore')}' at {current_file_offset} has invalid declared size {full_size} < actual header_size {header_size}.")
        return None
        
    payload_offset = current_file_offset + header_size
    return type_code, full_size, header_size, payload_offset, is_extended, version, flags

def parse_atoms_recursive_v2(f: BinaryIO, current_offset: int, parse_end_offset: int, file_size: int, depth: int = 0, max_depth: int = 20) -> List[Atom]:
    atoms = []
    if depth > max_depth:
        logger.warning(f"Max parsing depth {max_depth} reached at offset {current_offset}.")
        return atoms

    offset_within_parent = current_offset
    while offset_within_parent < parse_end_offset:
        header_info = read_atom_header_unified(f, offset_within_parent)
        if not header_info:
            logger.debug(f"No more valid atom headers at {offset_within_parent} (parent ends {parse_end_offset}).")
            break
        
        type_code, atom_full_size, atom_header_size, atom_payload_offset, is_extended, version, flags = header_info

        if atom_full_size == 0:
            if type_code == b'mdat':
                atom_full_size = file_size - offset_within_parent
                logger.info(f"mdat atom at {offset_within_parent} adjusted to size {atom_full_size} (to EOF)")
            elif offset_within_parent + atom_header_size <= parse_end_offset :
                atom_full_size = parse_end_offset - offset_within_parent
                logger.info(f"Atom '{type_code.decode('ascii','ignore')}' at {offset_within_parent} with size 0 adjusted to {atom_full_size} (to end of parent at {parse_end_offset}).")
            else:
                logger.warning(f"Atom '{type_code.decode('ascii','ignore')}' at {offset_within_parent} has size 0, but not mdat and parent end unclear. Stopping parse for this level.")
                break
        
        if atom_full_size < atom_header_size: # Check after size 0 resolution
            logger.warning(f"Atom '{type_code.decode('ascii','ignore')}' at {offset_within_parent} has final size {atom_full_size} < header_size {atom_header_size}. Atom is corrupt.")
            # Attempt to find next atom by scanning, or stop this level
            offset_within_parent += 1 # Skip one byte and try again (very basic error recovery)
            continue


        # Check if atom overflows its parent container
        if offset_within_parent + atom_full_size > parse_end_offset:
            logger.warning(f"Atom '{type_code.decode('ascii','ignore')}' ({atom_full_size} bytes) at {offset_within_parent} "
                           f"exceeds parent boundary ({parse_end_offset}). Correcting size to fit parent.")
            atom_full_size = parse_end_offset - offset_within_parent
            if atom_full_size < atom_header_size:
                logger.error(f"Cannot proceed with atom '{type_code.decode('ascii','ignore')}' as capped size {atom_full_size} is less than header size {atom_header_size}.")
                break # Stop parsing this parent


        atom = Atom(type_code, atom_full_size, offset_within_parent, atom_header_size, atom_payload_offset, is_extended, version, flags)
        
        # Conceptual: atom.parse_specific_payload(f) would go here
        if not atom.is_container and atom.payload_size > 0:
            # For non-container (leaf) atoms, we might want to store their raw payload if we plan to reconstruct the file.
            # Be cautious with 'mdat' as it can be huge.
            if atom.type != 'mdat': # Don't read full mdat payload into memory by default
                try:
                    f.seek(atom.payload_offset)
                    atom.raw_payload_data = f.read(atom.payload_size)
                except Exception as e:
                    logger.error(f"Error reading payload for {atom.type} at {atom.payload_offset}: {e}")
                    atom.valid = False # Mark as invalid if payload can't be read

        if atom.is_container and atom.payload_size > 0:
            atom.children = parse_atoms_recursive_v2(f, atom.payload_offset, atom.offset + atom.size, file_size, depth + 1, max_depth)
        
        atoms.append(atom)
        
        offset_within_parent += atom_full_size
        
        if offset_within_parent > parse_end_offset: # Safety break if something went wrong with size calculation
            logger.debug(f"Next atom offset {offset_within_parent} calculated beyond parent end {parse_end_offset}. Parent likely truncated or sizes miscalculated.")
            break
    return atoms


# --- Specific Atom Parsing Functions ---
def parse_stco_co64(atom: Atom, f: BinaryIO) -> Optional[List[int]]:
    if atom.type not in ['stco', 'co64'] or not atom.raw_payload_data or len(atom.raw_payload_data) < 4 :
        if atom.type in ['stco', 'co64'] and atom.payload_size > 0 and not atom.raw_payload_data: # If payload wasn't pre-read
            try:
                f.seek(atom.payload_offset)
                atom.raw_payload_data = f.read(atom.payload_size)
                if not atom.raw_payload_data or len(atom.raw_payload_data) < 4: return None
            except: return None
        else: return None

    payload = atom.raw_payload_data
    entry_count = struct.unpack('>I', payload[0:4])[0]
    offsets = []
    entry_size = 4 if atom.type == 'stco' else 8
    fmt = '>I' if atom.type == 'stco' else '>Q'
    
    expected_payload_min_size = 4 + entry_count * entry_size
    if len(payload) < expected_payload_min_size:
        logger.warning(f"Atom {atom.type} payload size {len(payload)} too small for {entry_count} entries of size {entry_size}. Expected at least {expected_payload_min_size}.")
        actual_entries = (len(payload) - 4) // entry_size
        logger.info(f"Reading {actual_entries} entries instead of declared {entry_count}.")
        entry_count = actual_entries # Adjust entry count

    current_offset_in_payload = 4
    for _ in range(entry_count):
        if current_offset_in_payload + entry_size > len(payload): break
        data_chunk = payload[current_offset_in_payload : current_offset_in_payload + entry_size]
        offsets.append(struct.unpack(fmt, data_chunk)[0])
        current_offset_in_payload += entry_size
        
    atom.parsed_data['chunk_offsets'] = offsets
    return offsets

def parse_stsz_stz2(atom: Atom, f: BinaryIO) -> Optional[List[int]]:
    if atom.type not in ['stsz', 'stz2'] or not atom.raw_payload_data or len(atom.raw_payload_data) < 4:
        if atom.type in ['stsz', 'stz2'] and atom.payload_size > 0 and not atom.raw_payload_data:
            try:
                f.seek(atom.payload_offset)
                atom.raw_payload_data = f.read(atom.payload_size)
                if not atom.raw_payload_data or len(atom.raw_payload_data) < 4: return None
            except: return None
        else: return None

    payload = atom.raw_payload_data
    sample_size = struct.unpack('>I', payload[0:4])[0]
    current_offset_in_payload = 4
    
    if atom.type == 'stz2':
        if len(payload) < current_offset_in_payload + 1: return None
        field_size_val = struct.unpack('>B', payload[current_offset_in_payload : current_offset_in_payload+1])[0]
        atom.parsed_data['field_size'] = field_size_val
        current_offset_in_payload +=1
        logger.warning("stz2 entry parsing based on field_size is not fully implemented here.")
        return [] 

    if len(payload) < current_offset_in_payload + 4 and sample_size == 0 : return None # Needs entry_count
    entry_count = struct.unpack('>I', payload[current_offset_in_payload : current_offset_in_payload+4])[0]
    current_offset_in_payload +=4
    atom.parsed_data['uniform_sample_size'] = sample_size
    atom.parsed_data['sample_count'] = entry_count
    
    sizes = []
    if sample_size == 0:
        expected_payload_min_size = current_offset_in_payload + entry_count * 4
        if len(payload) < expected_payload_min_size:
             logger.warning(f"stsz payload size {len(payload)} too small for {entry_count} entries. Expected {expected_payload_min_size}")
             actual_entries = (len(payload) - current_offset_in_payload) // 4
             logger.info(f"Reading {actual_entries} entries instead of declared {entry_count}.")
             entry_count = actual_entries
        for _ in range(entry_count):
            if current_offset_in_payload + 4 > len(payload): break
            data_chunk = payload[current_offset_in_payload : current_offset_in_payload+4]
            sizes.append(struct.unpack('>I', data_chunk)[0])
            current_offset_in_payload += 4
        atom.parsed_data['sample_sizes'] = sizes
    else: 
        atom.parsed_data['sample_sizes'] = [sample_size] * entry_count
    return sizes


# --- Repair Logic Functions (Conceptual) ---
def validate_atom_tree(root_atom: Atom, file_size: int, f_damaged: BinaryIO) -> bool:
    logger.info("Validating parsed atom tree...")
    all_valid_overall = True
    if not root_atom.children:
        logger.error("No top-level atoms found. File is likely not MP4 or severely corrupt.")
        return False

    # Recursive validation function
    def _validate_node(atom: Atom, parent_end_offset: int) -> bool:
        node_valid = True
        # Check 1: Atom boundaries
        if atom.offset + atom.size > parent_end_offset:
            logger.warning(f"Atom {atom.type} at {atom.offset} (size {atom.size}) exceeds its parent's boundary ({parent_end_offset}).")
            atom.valid = False
            node_valid = False
        
        # Check 2: Minimum size
        if atom.size < atom.header_size: # Should not happen if read_atom_header_unified is good
            logger.warning(f"Atom {atom.type} at {atom.offset} has size {atom.size} < header_size {atom.header_size}.")
            atom.valid = False
            node_valid = False

        # Add more checks here:
        # - Presence of mandatory child atoms for known containers
        # - Consistency checks within atom payloads if parsed (e.g., stts entries vs stsz count)

        if atom.is_container:
            for child in atom.children:
                if not _validate_node(child, atom.offset + atom.size):
                    node_valid = False # Propagate invalidity up
        return node_valid

    for top_atom in root_atom.children:
        if not _validate_node(top_atom, file_size):
            all_valid_overall = False

    # Example: Validate chunk offsets if moov and mdat are present
    moov = root_atom.get_child('moov')
    mdat = root_atom.get_child('mdat')
    if moov and mdat and mdat.offset >= 0 and mdat.size > 0: # mdat.offset can be 0
        for trak in moov.get_all_children('trak'):
            stbl = None
            mdia = trak.get_child('mdia')
            if mdia:
                minf = mdia.get_child('minf')
                if minf:
                    stbl = minf.get_child('stbl')
            
            if stbl:
                co_atom = stbl.get_child('stco') or stbl.get_child('co64')
                if co_atom:
                    # Ensure stco/co64 is parsed before validation
                    if 'chunk_offsets' not in co_atom.parsed_data:
                        parse_stco_co64(co_atom, f_damaged) # Pass the file handle
                    
                    if 'chunk_offsets' in co_atom.parsed_data:
                        for offset_val in co_atom.parsed_data['chunk_offsets']:
                            if not (mdat.offset <= offset_val < mdat.offset + mdat.size):
                                logger.error(f"Invalid chunk offset {offset_val} in {co_atom.type} (atom at {co_atom.offset}). Points outside mdat [{mdat.offset}-{mdat.offset+mdat.size-1}].")
                                co_atom.valid = False
                                all_valid_overall = False
    else:
        if not moov: logger.warning("validate_atom_tree: MOOV atom not found.")
        if not mdat: logger.warning("validate_atom_tree: MDAT atom not found.")

    if all_valid_overall:
        logger.info("Atom tree validation passed structural checks performed so far.")
    else:
        logger.warning("Atom tree validation found structural issues.")
    return all_valid_overall


def attempt_rebuild_moov(damaged_atoms_root: Atom, ref_atoms_root: Atom, damaged_file_path: str, temp_dir: str) -> Optional[bytes]:
    logger.info("Conceptual: Attempting to rebuild MOOV atom...")
    logger.warning("Full MOOV rebuild from Python is highly complex and not implemented in this conceptual script.")
    return None 

def write_repaired_mp4(output_path: str, ftyp_atom: Optional[Atom], moov_atom: Optional[Atom], mdat_atom: Optional[Atom], other_atoms: List[Atom], f_orig: BinaryIO):
    logger.info(f"Writing repaired MP4 to {output_path}...")
    with open(output_path, 'wb') as f_out:
        atoms_to_write: List[Atom] = []
        # Preferred order for streaming: ftyp, free/skip (padding for moov), moov, mdat
        # More complex ordering might be needed based on 'pdin' etc.
        
        # Add ftyp if present
        if ftyp_atom and ftyp_atom.valid: atoms_to_write.append(ftyp_atom)
        else: logger.warning("FTYP atom is missing or invalid for writing.")

        # Add moov if present and valid
        if moov_atom and moov_atom.valid: atoms_to_write.append(moov_atom)
        else: logger.warning("MOOV atom is missing or invalid for writing. Output file will likely be unplayable.")

        # Add other top-level atoms (excluding moov, mdat, ftyp already decided)
        for atom in other_atoms:
            if atom.type not in ['ftyp', 'moov', 'mdat'] and atom.valid:
                atoms_to_write.append(atom)
        
        # Add mdat if present and valid
        if mdat_atom and mdat_atom.valid: atoms_to_write.append(mdat_atom)
        else: logger.warning("MDAT atom is missing or invalid for writing. No media data.")


        for atom in atoms_to_write:
            logger.debug(f"Writing atom: {atom.type} (size: {atom.size}) from offset {atom.offset}")
            try:
                f_orig.seek(atom.offset)
                # Atom size includes its own header.
                atom_data = f_orig.read(atom.size)
                if len(atom_data) != atom.size:
                    logger.error(f"Error reading atom {atom.type}: expected {atom.size} bytes, got {len(atom_data)}.")
                    continue # Skip writing this corrupt atom
                f_out.write(atom_data)
            except Exception as e:
                 logger.error(f"Failed to read/write atom {atom.type} from original file: {e}")
        
    logger.info(f"Finished writing repaired MP4 conceptually to {output_path}")


# --- Main Repair Logic ---
def deep_repair_logic(input_file: str, reference_file: str, output_file: str) -> bool:
    logger.info(f"Starting Technique 17: Deep Atom Repair for {input_file}")
    
    file_size = 0
    if os.path.exists(input_file): file_size = os.path.getsize(input_file)
    else: logger.error(f"Input file {input_file} not found."); return False
    if file_size == 0: logger.error(f"Input file {input_file} is empty."); return False

    ref_file_size = 0
    if os.path.exists(reference_file): ref_file_size = os.path.getsize(reference_file)
    else: logger.warning(f"Reference file {reference_file} not found. Some repairs may be limited.");

    parsed_atoms_damaged_root: Optional[Atom] = None
    # parsed_atoms_ref_root: Optional[Atom] = None # Reference parsing can be added if used by repair strategies
    
    temp_repaired_path = os.path.join(os.path.dirname(output_file) or ".", "temp_t17_repaired.mp4")

    with open(input_file, 'rb') as f_damaged:
        logger.info("--- Parsing Damaged File ---")
        top_level_atoms_damaged = parse_atoms_recursive_v2(f_damaged, 0, file_size, file_size)
        if not top_level_atoms_damaged:
            logger.error("Failed to parse any top-level atoms from damaged file.")
            # Fallback to simple FFmpeg copy
            cmd_fallback = [FFMPEG_CMD, '-y', '-i', input_file, '-c', 'copy', '-movflags', '+faststart', '-loglevel', 'error', output_file]
            try:
                logger.info("Attempting direct FFmpeg copy due to parsing failure.")
                subprocess.run(cmd_fallback, check=True)
                return check_output_validity(output_file)
            except: return False

        parsed_atoms_damaged_root = Atom(b'root', file_size, 0, 0, 0) # Root is conceptual
        parsed_atoms_damaged_root.children = top_level_atoms_damaged

        logger.info(f"Python parser identified {len(parsed_atoms_damaged_root.children)} top-level atoms.")
        for atom in parsed_atoms_damaged_root.children: logger.info(f"  {atom}") # Use atom's __repr__

        # Pre-parse critical tables like stco/stsz from the damaged file if moov exists
        moov_damaged = parsed_atoms_damaged_root.get_child('moov')
        if moov_damaged:
            for trak in moov_damaged.get_all_children('trak'):
                stbl = None
                mdia = trak.get_child('mdia')
                if mdia:
                    minf = mdia.get_child('minf')
                    if minf: stbl = minf.get_child('stbl')
                
                if stbl:
                    stco_atom = stbl.get_child('stco') or stbl.get_child('co64')
                    stsz_atom = stbl.get_child('stsz') or stbl.get_child('stz2')
                    if stco_atom: parse_stco_co64(stco_atom, f_damaged)
                    if stsz_atom: parse_stsz_stz2(stsz_atom, f_damaged)
        
        validation_passed = validate_atom_tree(parsed_atoms_damaged_root, file_size, f_damaged)

        # --- Attempt to write a "cleaned" version based on parsed valid atoms ---
        # This is a very basic reassembly. True repair would modify atom contents before writing.
        ftyp_atom = parsed_atoms_damaged_root.get_child('ftyp')
        moov_atom = parsed_atoms_damaged_root.get_child('moov')
        mdat_atom = parsed_atoms_damaged_root.get_child('mdat')
        other_top_level_atoms = [a for a in parsed_atoms_damaged_root.children if a.type not in ['ftyp', 'moov', 'mdat']]
        
        # If critical atoms are missing, this basic reassembly won't help much without reconstruction.
        if not ftyp_atom or not moov_atom or not mdat_atom:
            logger.warning("Critical atoms (ftyp, moov, or mdat) missing or marked invalid by parser. Python-based reassembly likely to fail.")
            # Fallback to FFmpeg strategies if Python based reassembly is unlikely to succeed
            logger.info("Falling back to FFmpeg strategies due to missing critical atoms for Python reassembly.")
            # (FFmpeg strategies from previous response's deep_repair_logic can be inserted here)
            # For now, let's just try a robust remux
            cmd_ffmpeg_repair = [FFMPEG_CMD, '-y', '-i', input_file, '-c', 'copy', '-map_metadata', '0', '-ignore_unknown', '-fflags', '+genpts+igndts', '-movflags', '+faststart', '-avoid_negative_ts', 'make_zero', '-loglevel', 'error', output_file]
            try:
                subprocess.run(cmd_ffmpeg_repair, check=True)
                return check_output_validity(output_file)
            except Exception as e:
                logger.error(f"Fallback FFmpeg repair attempt failed: {e}")
                return False

        # If atoms are present, try writing them out to a temporary file
        write_repaired_mp4(temp_repaired_path, ftyp_atom, moov_atom, mdat_atom, other_top_level_atoms, f_damaged)

    # After Python-based attempt (or if it was skipped), validate temp_repaired_path
    if os.path.exists(temp_repaired_path) and check_output_validity(temp_repaired_path):
        logger.info(f"Python-based atom reassembly produced a potentially valid file: {temp_repaired_path}")
        shutil.copy2(temp_repaired_path, output_file)
        if os.path.exists(temp_repaired_path): os.remove(temp_repaired_path)
        return True
    else:
        logger.warning(f"Python-based atom reassembly did not produce a valid file (checked {temp_repaired_path}).")
        if os.path.exists(temp_repaired_path): os.remove(temp_repaired_path)
        
        # If Python attempt failed, as a final effort for this technique, try FFmpeg
        logger.info("Python-based reassembly failed or skipped. Attempting final robust FFmpeg remux as part of Technique 17.")
        cmd_final_ffmpeg = [FFMPEG_CMD, '-y', '-i', input_file, '-c', 'copy', '-map_metadata', '0', '-ignore_unknown', '-fflags', '+genpts+igndts', '-movflags', '+faststart', '-avoid_negative_ts', 'make_zero', '-loglevel', 'error', output_file]
        try:
            subprocess.run(cmd_final_ffmpeg, check=True)
            return check_output_validity(output_file)
        except Exception as e:
            logger.error(f"Final FFmpeg remux attempt in Technique 17 failed: {e}")
            return False


def check_output_validity(file_path: str, min_duration_sec: float = 1.0) -> bool:
    if not os.path.exists(file_path) or os.path.getsize(file_path) < 1024: 
        logger.debug(f"Validity Check: File {file_path} is too small or does not exist.")
        return False
    try:
        cmd = [FFPROBE_CMD, '-v', 'error', '-show_format', '-show_streams', '-of', 'json', file_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        info = json.loads(result.stdout) # <--- This is where 'json' module is used
        
        if not info.get('streams'): 
            logger.warning(f"Validity Check: No streams in {file_path}")
            return False
        duration_str = info.get('format', {}).get('duration')
        if duration_str:
            try:
                if float(duration_str) < min_duration_sec :
                    logger.warning(f"Validity Check: Duration {float(duration_str)}s < {min_duration_sec}s in {file_path}")
                    return False
            except ValueError: # Handle non-float duration strings
                logger.warning(f"Validity Check: Non-float duration '{duration_str}' in {file_path}")
                return False # Or some other logic if non-float duration might be valid in some context
        else: # No duration
            logger.warning(f"Validity Check: No duration info in {file_path}")
            return False 
        
        cmd_check_ffmpeg = [FFMPEG_CMD, '-v', 'error', '-i', file_path, '-f', 'null', '-']
        result_check_ffmpeg = subprocess.run(cmd_check_ffmpeg, stderr=subprocess.PIPE, text=True, check=False)
        if result_check_ffmpeg.stderr.strip() != '':
            logger.warning(f"Validity Check: FFmpeg found errors in {file_path}:\n{result_check_ffmpeg.stderr.strip()}")
            return False
        logger.info(f"Validity Check: {file_path} passed.")
        return True
    except subprocess.CalledProcessError as e: # ffprobe failed
        logger.warning(f"Validity Check: ffprobe error for {file_path}. Stderr: {e.stderr.strip()}")
        return False
    except json.JSONDecodeError:
        logger.warning(f"Validity Check: ffprobe output for {file_path} was not valid JSON.")
        return False
    except Exception as e_gen:
        logger.error(f"Validity Check: Unexpected error for {file_path}: {e_gen}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Technique 17: Deep MP4 Atom Structure Repair (Python Centric Conceptual)')
    parser.add_argument('input_file', help='Path to the damaged MP4 file')
    parser.add_argument('reference_file', help='Path to a working reference MP4 file')
    parser.add_argument('output_file', help='Path where the repaired file will be saved')
    args = parser.parse_args()

    output_dir = os.path.dirname(args.output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    if deep_repair_logic(args.input_file, args.reference_file, args.output_file):
        logger.info(f"Technique 17 completed. Output may be at {args.output_file}")
        sys.exit(0)
    else:
        logger.error(f"Technique 17 failed for {args.input_file}.")
        # Ensure master script sees a failure if final output is not valid
        if os.path.exists(args.output_file) and not check_output_validity(args.output_file, 0.1): # check even tiny files
             try: os.remove(args.output_file)
             except: pass
        sys.exit(1)

