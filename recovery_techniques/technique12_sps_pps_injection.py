#!/usr/bin/env python3
"""
SPS/PPS Injection Technique (Technique 12) - Conceptual/Simplified

Extracts H.264 stream, extracts SPS/PPS from a reference file,
prepends them, and remuxes.
This is a simplified version. True MP4 atom editing is more complex.

Usage:
    python technique12_sps_pps_injection.py damaged.mp4 reference.mp4 output.mp4
"""

import os
import sys
import subprocess
import shutil
import logging
import argparse
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mp4_recovery_technique12')

FFMPEG_CMD = 'ffmpeg'

def check_mp4_file(file_path: str) -> bool:
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return False
    try:
        cmd = [FFMPEG_CMD, '-v', 'error', '-i', file_path, '-f', 'null', '-']
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return result.stderr.strip() == ''
    except Exception:
        return False

def extract_sps_pps_from_mp4(mp4_file: str, output_sps_pps_file: str) -> bool:
    """
    Extracts SPS and PPS NAL units from an MP4 file into a single .h264 file.
    This relies on ffmpeg's ability to dump extradata.
    A more robust method would parse the avcC box directly.
    """
    # This command extracts the global headers (extradata) which contain SPS/PPS for H.264
    # It writes them in Annex B format.
    cmd = [
        FFMPEG_CMD, '-y', '-i', mp4_file,
        '-c:v', 'copy', '-bsf:v', 'dump_extra',
        '-f', 'h264', '-an', '-sn', # no audio, no subtitles
        '-loglevel', 'error',
        output_sps_pps_file
    ]
    # The 'dump_extra' bitstream filter might not always put *only* SPS/PPS.
    # It's often used with -vframes 1 or similar to limit output.
    # A more targeted approach:
    # ffmpeg -i good.mp4 -c copy -vbsf h264_mp4toannexb -an -f h264 -vframes 1 temp.h264
    # Then parse temp.h264 for SPS/PPS NAL units.
    # For simplicity, we'll use a method that tries to get extradata if possible.
    # A common way to get extradata is to force a re-encode of 1 frame.
    # However, for *injection*, we need them in Annex B start code format.
    
    # Let's try to extract the first few frames and hope SPS/PPS are there.
    # This is a common workaround if dump_extra isn't available or behaving as expected.
    cmd_alt = [
        FFMPEG_CMD, '-y', '-i', mp4_file,
        '-c:v', 'copy', '-bsf:v', 'h264_mp4toannexb',
        '-vframes', '1', # Try to get first I-frame which should have SPS/PPS
        '-an', '-f', 'h264', '-loglevel', 'error',
        output_sps_pps_file
    ]
    logger.info(f"Attempting to extract SPS/PPS from {mp4_file} using command: {' '.join(cmd_alt)}")
    try:
        result = subprocess.run(cmd_alt, check=True, capture_output=True, text=True)
        if os.path.exists(output_sps_pps_file) and os.path.getsize(output_sps_pps_file) > 0:
            # Crude check: ensure it contains typical NAL unit types for SPS (0x67) and PPS (0x68)
            # This is not foolproof.
            with open(output_sps_pps_file, 'rb') as f_spspps:
                content = f_spspps.read()
                # Look for 00 00 01 67 or 00 00 00 01 67 (SPS)
                # and 00 00 01 68 or 00 00 00 01 68 (PPS)
                sps_found = re.search(rb'\x00\x00\x00?\x01\x67', content)
                pps_found = re.search(rb'\x00\x00\x00?\x01\x68', content)
                if sps_found and pps_found:
                    logger.info(f"SPS/PPS likely extracted to {output_sps_pps_file}")
                    return True
                else:
                    logger.warning("SPS/PPS NAL unit signatures not found in extracted data.")
                    if os.path.exists(output_sps_pps_file): os.remove(output_sps_pps_file)
                    return False
        logger.warning(f"Failed to extract SPS/PPS or output is empty. Stderr: {result.stderr.strip()}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to extract SPS/PPS from {mp4_file}. Stderr: {e.stderr.strip()}")
    return False


def repair_file(input_file: str, reference_file: str, output_file: str) -> bool:
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    temp_dir = os.path.join(os.path.dirname(output_file), f"{base_name}_technique12_temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    raw_video_damaged = os.path.join(temp_dir, "damaged_video.h264")
    sps_pps_ref = os.path.join(temp_dir, "ref_sps_pps.h264")
    video_with_injected_headers = os.path.join(temp_dir, "video_injected.h264")
    audio_damaged = os.path.join(temp_dir, "damaged_audio.aac") # Assuming AAC

    success = False
    try:
        logger.info(f"Starting SPS/PPS injection for {input_file} using {reference_file}")

        # 1. Extract H.264 stream from damaged file
        cmd_extract_video = [
            FFMPEG_CMD, '-y', '-i', input_file, '-c:v', 'copy', 
            '-bsf:v', 'h264_mp4toannexb', '-an', '-f', 'h264', 
            '-loglevel', 'error', raw_video_damaged
        ]
        logger.info(f"Extracting raw video from damaged file: {' '.join(cmd_extract_video)}")
        subprocess.run(cmd_extract_video, check=False) # Allow failure
        
        if not (os.path.exists(raw_video_damaged) and os.path.getsize(raw_video_damaged) > 0):
            logger.error("Failed to extract raw video stream from damaged file.")
            return False

        # 2. Extract SPS/PPS from reference file
        if not extract_sps_pps_from_mp4(reference_file, sps_pps_ref):
            logger.error("Failed to extract SPS/PPS from reference file.")
            return False

        # 3. Prepend SPS/PPS to the damaged H.264 stream
        logger.info(f"Prepending SPS/PPS to damaged video stream.")
        with open(video_with_injected_headers, 'wb') as outfile:
            with open(sps_pps_ref, 'rb') as sps_pps_f:
                # Only write SPS/PPS, not other NAL units from the reference's first frame if present
                # This requires parsing or a more precise extraction.
                # For this simplified example, we assume sps_pps_ref contains *only* or primarily SPS/PPS.
                ref_content = sps_pps_f.read()
                # A more robust method would parse NAL units from ref_content and only write SPS/PPS types
                outfile.write(ref_content) 
            with open(raw_video_damaged, 'rb') as damaged_f:
                # We need to be careful not to duplicate SPS/PPS if the damaged stream already has some.
                # This is a simplification; ideal approach is to strip existing SPS/PPS from damaged stream.
                outfile.write(damaged_f.read())
        
        if not (os.path.exists(video_with_injected_headers) and os.path.getsize(video_with_injected_headers) > 0):
            logger.error("Failed to create video stream with injected headers.")
            return False

        # 4. Extract audio from damaged file (if any)
        cmd_extract_audio = [
            FFMPEG_CMD, '-y', '-i', input_file, '-c:a', 'copy', 
            '-vn', '-f', 'adts', '-loglevel', 'error', audio_damaged
        ]
        subprocess.run(cmd_extract_audio, check=False)
        has_audio = os.path.exists(audio_damaged) and os.path.getsize(audio_damaged) > 0
        logger.info(f"Audio extraction from damaged file: {'successful' if has_audio else 'failed/no audio'}")

        # 5. Remux the new H.264 stream (with injected headers) and audio
        cmd_remux = [FFMPEG_CMD, '-y', '-framerate', '30'] # Assume 30fps, or get from reference
        # Get framerate from reference if possible
        try:
            probe_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', reference_file]
            fps_str = subprocess.check_output(probe_cmd, text=True).strip()
            if '/' in fps_str:
                num, den = map(int, fps_str.split('/'))
                if den != 0: cmd_remux = [FFMPEG_CMD, '-y', '-r', str(num/den)]
        except Exception:
            pass # Stick to default 30fps

        cmd_remux.extend(['-i', video_with_injected_headers])
        if has_audio:
            cmd_remux.extend(['-i', audio_damaged])
        
        cmd_remux.extend(['-c', 'copy', '-movflags', '+faststart', '-loglevel', 'error', output_file])
        
        if has_audio:
             cmd_remux.extend(['-map', '0:v:0', '-map', '1:a:0'])
        else:
             cmd_remux.extend(['-map', '0:v:0'])


        logger.info(f"Remuxing with injected headers: {' '.join(cmd_remux)}")
        result = subprocess.run(cmd_remux, check=True, capture_output=True, text=True)
        
        if result.returncode == 0 and check_mp4_file(output_file):
            logger.info(f"File successfully repaired with SPS/PPS injection: {output_file}")
            success = True
        else:
            logger.error(f"Failed to remux with injected SPS/PPS. Stderr: {result.stderr.strip()}")
            if os.path.exists(output_file): os.remove(output_file)

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg command failed: {e.cmd}, stderr: {e.stderr.strip()}")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temp directory: {temp_dir}")
            
    return success

def main():
    parser = argparse.ArgumentParser(description='SPS/PPS Injection MP4 Repair Technique 12')
    parser.add_argument('input_file', help='Path to the damaged MP4 file')
    parser.add_argument('reference_file', help='Path to a working reference MP4 file for SPS/PPS')
    parser.add_argument('output_file', help='Path where the repaired file will be saved')
    args = parser.parse_args()

    if not os.path.exists(args.input_file) or not os.path.exists(args.reference_file):
        logger.error(f"Input or reference file not found.")
        sys.exit(1)

    if repair_file(args.input_file, args.reference_file, args.output_file):
        logger.info("SPS/PPS Injection completed successfully.")
        sys.exit(0)
    else:
        logger.error("SPS/PPS Injection failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()