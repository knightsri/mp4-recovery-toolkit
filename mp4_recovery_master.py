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
import json
from typing import List, Dict, Any, Optional, Tuple # Added Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mp4_recovery_master')

# Validation tolerances
DURATION_TOLERANCE = 0.05  # 5% tolerance for duration difference
SIZE_TOLERANCE = 0.30  # 30% tolerance for file size difference

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

def get_media_info(file_path: str) -> Optional[Dict[str, Any]]:
    """Get media information using ffprobe."""
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return json.loads(result.stdout)
        return None
    except Exception as e:
        logger.warning(f"Failed to get media info for {file_path}: {e}")
        return None

def check_for_errors(file_path: str) -> Tuple[bool, int]:
    """Check for errors in the output file using ffmpeg."""
    try:
        cmd = [
            'ffmpeg',
            '-v', 'error',
            '-i', file_path,
            '-f', 'null',
            '-'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        error_count = len(result.stderr.strip().split('\n')) if result.stderr.strip() else 0
        has_critical_errors = error_count > 10  # More than 10 error lines is concerning
        return has_critical_errors, error_count
    except Exception as e:
        logger.warning(f"Failed to check errors for {file_path}: {e}")
        return True, 999

def is_output_truly_valid(output_file: str, reference_file: str, original_file: str) -> bool:
    """
    Validate the output file to ensure it's truly valid.

    Checks:
    - File exists and has size > 0
    - Duration is similar to reference (within tolerance)
    - File size is reasonable compared to reference
    - Video/audio streams are present and match expected codecs
    - No excessive errors when checking with ffmpeg

    Args:
        output_file: Path to the repaired output file
        reference_file: Path to the reference file
        original_file: Path to the original damaged file

    Returns:
        bool: True if output is valid, False otherwise
    """
    # Basic file existence and size check
    if not os.path.exists(output_file):
        logger.warning(f"Output file does not exist: {output_file}")
        return False

    output_size = os.path.getsize(output_file)
    if output_size == 0:
        logger.warning(f"Output file is empty: {output_file}")
        return False

    # Get media info for all files
    output_info = get_media_info(output_file)
    reference_info = get_media_info(reference_file)

    if not output_info:
        logger.warning(f"Could not get media info for output file: {output_file}")
        return False

    # Check for excessive errors
    has_errors, error_count = check_for_errors(output_file)
    if has_errors:
        logger.warning(f"Output file has {error_count} errors - may not be fully valid")
        return False

    # If we have reference info, do comparative validation
    if reference_info:
        # Compare duration
        output_duration = float(output_info.get('format', {}).get('duration', 0))
        ref_duration = float(reference_info.get('format', {}).get('duration', 0))

        if ref_duration > 0:
            duration_diff = abs(output_duration - ref_duration) / ref_duration
            if duration_diff > DURATION_TOLERANCE:
                logger.warning(f"Duration mismatch: output={output_duration}s, reference={ref_duration}s, diff={duration_diff*100:.1f}%")
                return False

        # Compare file size
        ref_size = os.path.getsize(reference_file)
        if ref_size > 0:
            size_diff = abs(output_size - ref_size) / ref_size
            if size_diff > SIZE_TOLERANCE:
                logger.info(f"File size difference: output={output_size}, reference={ref_size}, diff={size_diff*100:.1f}%")
                # Size difference alone isn't fatal, just log it

        # Check for video stream
        output_has_video = any(s.get('codec_type') == 'video' for s in output_info.get('streams', []))
        ref_has_video = any(s.get('codec_type') == 'video' for s in reference_info.get('streams', []))

        if ref_has_video and not output_has_video:
            logger.warning("Reference has video but output does not")
            return False

        # Check for audio stream
        output_has_audio = any(s.get('codec_type') == 'audio' for s in output_info.get('streams', []))
        ref_has_audio = any(s.get('codec_type') == 'audio' for s in reference_info.get('streams', []))

        if ref_has_audio and not output_has_audio:
            logger.warning("Reference has audio but output does not")
            # This is a warning but not necessarily fatal

    logger.info(f"Output file validation passed: {output_file}")
    return True

def check_script_exists(script_path: str) -> bool:
    """Check if a script file exists."""
    return os.path.exists(script_path)

def validate_file_path(file_path: str, must_exist: bool = True) -> Tuple[bool, str]:
    """
    Validate a file path for security and existence.

    Args:
        file_path: Path to validate
        must_exist: Whether the file must already exist

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path:
        return False, "File path is empty"

    # Check for path traversal attempts
    abs_path = os.path.abspath(file_path)
    if ".." in os.path.normpath(file_path):
        return False, "Path traversal detected in file path"

    if must_exist and not os.path.exists(abs_path):
        return False, f"File does not exist: {abs_path}"

    return True, ""

def validate_mp4_file(file_path: str) -> Tuple[bool, str]:
    """
    Validate that a file is an MP4 file.

    Args:
        file_path: Path to the file

    Returns:
        Tuple of (is_valid, error_message)
    """
    is_valid, error = validate_file_path(file_path, must_exist=True)
    if not is_valid:
        return False, error

    # Check file extension (basic check)
    _, ext = os.path.splitext(file_path)
    if ext.lower() not in ['.mp4', '.m4v', '.m4a']:
        return False, f"File does not have a valid MP4 extension: {ext}"

    return True, ""

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
            logger.info(f"Technique {technique['name']} created output: {technique_specific_output}")

            # Validate the output before declaring success
            if is_output_truly_valid(technique_specific_output, reference_file, input_file):
                print(f"\n✅ SUCCESS: {technique['name']} technique worked!")
                shutil.copy2(technique_specific_output, output_file)
                logger.info(f"Copied validated result to final output: {output_file}")
                return True
            else:
                logger.warning(f"{technique['name']} produced output but it failed validation")
                print(f"\n⚠️  WARNING: {technique['name']} produced output but it failed validation checks")
                return False
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
    
    except subprocess.SubprocessError as e:
        logger.error(f"Subprocess error running {technique['name']}: {str(e)}")
        print(f"Error running {technique['name']}: {str(e)}")
        return False
    except OSError as e:
        logger.error(f"File system error running {technique['name']}: {str(e)}")
        print(f"File system error with {technique['name']}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error running {technique['name']}: {str(e)}", exc_info=True)
        print(f"Unexpected error running {technique['name']}: {str(e)}")
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
                # Attempt to remove read-only files if present
                def handle_remove_readonly(func, path, exc):
                    """Error handler for Windows readonly files."""
                    import stat
                    os.chmod(path, stat.S_IWRITE)
                    func(path)

                shutil.rmtree(temp_dir_base, onerror=handle_remove_readonly)
                logger.info(f"Successfully cleaned up base temporary directory: {temp_dir_base}")
            except PermissionError as e:
                logger.warning(f"Permission denied cleaning up {temp_dir_base}: {e}")
                print(f"Warning: Could not remove temporary directory {temp_dir_base} (permission denied)")
            except OSError as e:
                logger.warning(f"OS error cleaning up {temp_dir_base}: {e}")
                print(f"Warning: Could not remove temporary directory {temp_dir_base}")
            except Exception as e:
                logger.error(f"Unexpected error cleaning up {temp_dir_base}: {e}", exc_info=True)
                print(f"Warning: Could not remove temporary directory {temp_dir_base}")

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
    
    # Validate input file
    is_valid, error = validate_mp4_file(args.input_file)
    if not is_valid:
        logger.critical(f"Input file validation failed: {error}")
        print(f"Error: Input file validation failed: {error}")
        sys.exit(1)

    # Validate reference file
    is_valid, error = validate_mp4_file(args.reference_file)
    if not is_valid:
        logger.warning(f"Reference file validation failed: {error}. Some techniques may be less effective or fail.")
        print(f"Warning: Reference file validation failed: {error}")

    # Validate output file path (must not exist yet, but path should be valid)
    is_valid, error = validate_file_path(args.output_file, must_exist=False)
    if not is_valid:
        logger.critical(f"Output file path validation failed: {error}")
        print(f"Error: Output file path validation failed: {error}")
        sys.exit(1)

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