#!/usr/bin/env python3
"""
MP4 Recovery Master Script

This script runs through all available recovery techniques until one succeeds.
It serves as a master script for the MP4 Recovery Suite.

Usage:
    python mp4_recovery_master.py damaged.mp4 reference.mp4 output.mp4
"""

import os
import sys
import subprocess
import logging
import argparse
import shutil
from typing import List, Dict, Any, Optional # Added Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mp4_recovery_master')

# Define available recovery techniques
TECHNIQUES: List[Dict[str, Any]] = [
    {
        'name': 'Standard Remux',
        'description': 'Basic stream extraction and remuxing using FFmpeg copy.',
        'script': 'technique1_standard_remux.py'
    },
    {
        'name': 'Advanced FFmpeg',
        'description': 'Multiple advanced FFmpeg parameter combinations.',
        'script': 'technique2_advanced_ffmpeg.py'
    },
    {
        'name': 'Raw NAL Extraction',
        'description': 'Raw NAL unit extraction for H.264 data, then remux.',
        'script': 'technique3_raw_nal_extraction.py'
    },
    {
        'name': 'Raw AAC Extraction',
        'description': 'Raw AAC frame extraction for audio, then remux with video (if NAL extracted).',
        'script': 'technique4_raw_aac_extraction.py'
    },
    {
        'name': 'Atom Structure Repair (Conceptual)',
        'description': 'Repair MP4 atom/box structure (Conceptual - needs specific Python BMFF lib).',
        'script': 'technique5_atom_structure_repair.py' # Placeholder script
    },
    {
        'name': 'MOOV Atom Reconstruction (Conceptual)',
        'description': 'Rebuild the MOOV atom using a reference file (Conceptual - needs specific Python BMFF lib).',
        'script': 'technique6_moov_atom_reconstruction.py' # Placeholder script
    },
    {
        'name': 'Frame by Frame Rebuild (Conceptual)',
        'description': 'Extract individual frames and rebuild (Conceptual - needs specific Python BMFF lib & stream parsing).',
        'script': 'technique7_frame_by_frame.py' # Placeholder script
    },
    {
        'name': 'Multi-Segment Repair',
        'description': 'Split and repair in segments, then concatenate.',
        'script': 'technique8_multi_segment_repair.py'
    },
    {
        'name': 'Metadata Transplant',
        'description': 'Transplant metadata from reference to extracted streams.',
        'script': 'technique9_metadata_transplant.py'
    },
    {
        'name': 'Hybrid FFmpeg Approach',
        'description': 'Combine multiple FFmpeg techniques in predefined chains.',
        'script': 'technique10_hybrid_approach.py'
    },
    {
        'name': 'Audio Offset Correction',
        'description': 'Attempts to correct audio/video synchronization issues using FFmpeg.',
        'script': 'technique11_audio_offset_correction.py'
    },
    {
        'name': 'SPS/PPS Injection (Simplified)',
        'description': 'Extracts H.264, injects SPS/PPS from reference, remuxes (Simplified FFmpeg approach).',
        'script': 'technique12_sps_pps_injection.py'
    },
    {
        'name': 'VFR to CFR Fix',
        'description': 'Converts video to Constant Frame Rate using FFmpeg to fix timestamp issues (re-encodes).',
        'script': 'technique13_vfr_to_cfr_fix.py'
    },
    {
        'name': 'Recover from Raw Disk Image (Conceptual)',
        'description': 'Conceptual file carving from a disk image. (Not a direct MP4 repair output).',
        'script': 'technique14_recover_from_raw_disk_image.py' # Placeholder
    },
    {
        'name': 'FFprobe Deep Analysis Repair (Conceptual)',
        'description': 'Uses ffprobe analysis for heuristic FFmpeg repair attempts (Conceptual).',
        'script': 'technique15_ffprobe_deep_analysis_repair.py' # Placeholder
    },
    {
        'name': 'BMFF Atom Editor (Conceptual)',
        'description': 'Low-level MP4 atom editing for repair (Highly Conceptual - needs Python BMFF lib).',
        'script': 'technique16_bmff_atom_editor.py' # Placeholder
    },
    {
        'name': 'Deep Atom Repair (Python Centric)',
        'description': 'Comprehensive Python-based atom parsing, validation, and repair attempts, assisted by FFmpeg.',
        'script': 'technique17_deep_atom_repair.py' # New Technique
    }]

def list_techniques() -> None:
    """List all available recovery techniques."""
    print("\nAvailable Recovery Techniques:")
    print("------------------------------")
    
    for i, technique in enumerate(TECHNIQUES, 1):
        print(f"{i}. {technique['name']}")
        print(f"   Description: {technique['description']}")
        print(f"   Script: {technique['script']}")
        print()

def check_script_exists(script_path: str) -> bool:
    """Check if a script file exists."""
    return os.path.exists(script_path)

def run_technique(technique: Dict[str, Any], input_file: str, reference_file: str, output_file: str, temp_dir_base: str) -> bool:
    """Run a specific recovery technique."""
    print("\n" + "="*80)
    print(f" TRYING TECHNIQUE: {technique['name']} ".center(80, '='))
    print("="*80 + "\n")
    
    script_file_name = technique['script']
    script_path = os.path.join('recovery_techniques', script_file_name) 
    
    if not check_script_exists(script_path):
        logger.warning(f"Script not found: {script_path}. Skipping technique '{technique['name']}'.")
        print(f"❌ Script not found: {script_path}")
        if "Conceptual" in technique['description'] or "Placeholder" in technique['description']:
             print(f"   (This is a conceptual/placeholder technique; no script to run or script is a stub.)")
        return False
    
    technique_output_suffix = f"recovered_{TECHNIQUES.index(technique) + 1}_{os.path.basename(output_file)}"
    technique_specific_output = os.path.join(temp_dir_base, technique_output_suffix)
    
    # For technique 14, the 'output_file' argument to the script is a directory
    current_output_arg = technique_specific_output
    if technique['script'] == 'technique14_recover_from_raw_disk_image.py':
        # Create a specific subdir for fragments from technique 14
        technique14_frag_dir = os.path.join(temp_dir_base, "technique14_fragments")
        os.makedirs(technique14_frag_dir, exist_ok=True)
        current_output_arg = technique14_frag_dir
        logger.info(f"Technique 14 will output fragments to: {current_output_arg}")


    if os.path.exists(technique_specific_output) and technique['script'] != 'technique14_recover_from_raw_disk_image.py':
        os.remove(technique_specific_output)

    try:
        cmd = [
            sys.executable,
            script_path,
            input_file,
            reference_file,
            current_output_arg 
        ]
        
        logger.info(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.stdout: logger.debug(f"Output from {technique['name']}:\n{result.stdout}")
        if result.stderr: logger.warning(f"Errors from {technique['name']}:\n{result.stderr}")

        # Technique 14 is special: success means it ran, not necessarily produced a playable output_file
        if technique['script'] == 'technique14_recover_from_raw_disk_image.py':
            if result.returncode == 0: # Script itself didn't crash
                logger.info(f"Technique 14 ({technique['name']}) completed its conceptual run.")
                print(f"ⓘ {technique['name']} completed. Check logs/fragment directory for conceptual output.")
                # It doesn't produce a single MP4, so it can't "succeed" in the master script's sense of creating output_file
                return False 
            else:
                logger.warning(f"Technique 14 ({technique['name']}) script failed with return code {result.returncode}.")
                return False


        if result.returncode == 0 and os.path.exists(technique_specific_output) and os.path.getsize(technique_specific_output) > 0:
            logger.info(f"SUCCESS: {technique['name']} technique created output: {technique_specific_output}")
            print(f"\n✅ SUCCESS: {technique['name']} technique worked!")
            
            shutil.copy2(technique_specific_output, output_file)
            logger.info(f"Copied successful result to final output: {output_file}")
            return True
        else:
            logger.info(f"FAILED: {technique['name']} technique (return code: {result.returncode}).")
            print(f"\n❌ FAILED: {technique['name']} technique failed.")
            if result.stderr:
                stderr_lines = result.stderr.strip().split('\n')
                for line in stderr_lines[-10:]: print(f"    {line}")
            if not os.path.exists(technique_specific_output) or os.path.getsize(technique_specific_output) == 0:
                logger.info(f"No valid output file produced by {technique['name']} at {technique_specific_output}")
                print(f"    (No valid output file produced at {technique_specific_output})")
            return False
    
    except Exception as e:
        logger.error(f"Master script error running {technique['name']}: {str(e)}")
        print(f"Error running {technique['name']}: {str(e)}")
        return False

def run_recovery(input_file: str, reference_file: str, output_file: str, specific_technique_num: Optional[int] = None) -> bool:
    temp_dir_base = os.path.join(os.path.dirname(os.path.abspath(output_file)) or '.', "mp4_recovery_temp_master")
    
    try:
        os.makedirs(temp_dir_base, exist_ok=True)
        logger.info(f"Created base temporary directory: {temp_dir_base}")
        
        success = False
        techniques_to_run = []
        if specific_technique_num is not None:
            if 1 <= specific_technique_num <= len(TECHNIQUES):
                techniques_to_run.append(TECHNIQUES[specific_technique_num - 1])
            else:
                logger.error(f"Invalid technique number: {specific_technique_num}")
                print(f"❌ Invalid technique number: {specific_technique_num}")
                return False
        else:
            techniques_to_run = TECHNIQUES
            
        for technique_info in techniques_to_run:
            if os.path.exists(output_file): # Clean final output before this technique makes its attempt
                os.remove(output_file)
                
            success = run_technique(technique_info, input_file, reference_file, output_file, temp_dir_base)
            if success:
                logger.info(f"Recovery successful with technique: {technique_info['name']}")
                break 
        
        return success
    
    finally:
        if os.path.exists(temp_dir_base):
            try:
                shutil.rmtree(temp_dir_base)
                logger.info(f"Successfully cleaned up base temporary directory: {temp_dir_base}")
            except Exception as e:
                logger.error(f"Failed to clean up temporary directory {temp_dir_base}: {e}")

def main():
    parser = argparse.ArgumentParser(description='MP4 Recovery Master Script')
    parser.add_argument('input_file', help='Path to the damaged MP4 file')
    parser.add_argument('reference_file', help='Path to a working reference MP4 file (may not be used by all techniques)')
    parser.add_argument('output_file', help='Path where the repaired file will be saved')
    parser.add_argument('-t', '--technique', type=int, help='Specific technique number to use (1-based index)')
    parser.add_argument('-l', '--list', action='store_true', help='List available techniques')
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print(" MP4 RECOVERY TOOLKIT ".center(80, '='))
    print("="*80 + "\n")
    
    if args.list:
        list_techniques()
        sys.exit(0)
    
    if not os.path.exists(args.input_file):
        logger.critical(f"Input file does not exist: {args.input_file}")
        print(f"Error: Input file does not exist: {args.input_file}")
        sys.exit(1)
    
    if not os.path.exists(args.reference_file) and any(
        tech['script'] not in [
            'technique14_recover_from_raw_disk_image.py', # May not need ref
            # Add other scripts that genuinely don't need a reference
        ] for tech in (TECHNIQUES if not args.technique else [TECHNIQUES[args.technique-1]])
    ):
        logger.warning(f"Reference file does not exist: {args.reference_file}. Some techniques may be less effective or fail.")
    
    output_dir_path = os.path.dirname(os.path.abspath(args.output_file))
    if output_dir_path and not os.path.exists(output_dir_path):
        try:
            os.makedirs(output_dir_path)
            logger.info(f"Created output directory: {output_dir_path}")
        except OSError as e:
            logger.critical(f"Could not create output directory {output_dir_path}: {e}")
            print(f"Error: Could not create output directory {output_dir_path}: {e}")
            sys.exit(1)

    abs_input_file = os.path.abspath(args.input_file)
    abs_reference_file = os.path.abspath(args.reference_file)
    abs_output_file = os.path.abspath(args.output_file)

    logger.info(f"Input file: {abs_input_file}")
    logger.info(f"Reference file: {abs_reference_file}")
    logger.info(f"Output file: {abs_output_file}")
    
    print(f"Input file: {abs_input_file}")
    print(f"Reference file: {abs_reference_file}")
    print(f"Output file: {abs_output_file}")
    
    if args.technique:
        logger.info(f"Attempting specific technique: {args.technique}")
        print(f"Using specific technique: {args.technique}")
    
    if run_recovery(abs_input_file, abs_reference_file, abs_output_file, args.technique):
        print("\n" + "="*80)
        print(" SUCCESS: FILE REPAIRED ".center(80, '='))
        print("="*80)
        print(f"\nRepaired file saved to: {abs_output_file}")
        sys.exit(0)
    else:
        print("\n" + "="*80)
        print(" FAILED: ALL ATTEMPTED TECHNIQUES FAILED ".center(80, '='))
        print("="*80)
        if not args.technique:
            print("\nUnable to repair the file with the attempted technique(s).")
        else:
            print(f"\nUnable to repair the file with technique {args.technique}.")
        print("Consider checking logs, trying other techniques, or if the file is severely damaged,")
        print("more advanced manual analysis or specialized commercial software might be needed.")
        sys.exit(1)

if __name__ == "__main__":
    main()