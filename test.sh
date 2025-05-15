#!/bin/bash
# Test script for MP4 Repair Docker container

# Create test directory
mkdir -p tests

# Function to check if a command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}===== MP4 REPAIR TOOL TEST SCRIPT =====${NC}"

# Check if FFmpeg is installed
if ! command_exists ffmpeg; then
  echo -e "${RED}FFmpeg not found. Please install FFmpeg to run this test.${NC}"
  exit 1
fi

# Generate a test "good" MP4 file if it doesn't exist
if [ ! -f tests/good.mp4 ]; then
  echo -e "\n${YELLOW}Generating test 'good' MP4 file...${NC}"
  ffmpeg -f lavfi -i testsrc=duration=5:size=1280x720:rate=30 -c:v libx264 -profile:v baseline tests/good.mp4
else
  echo -e "\n${GREEN}Using existing test 'good' MP4 file${NC}"
fi

# Generate a "bad" MP4 file by truncating the good one
if [ ! -f tests/truncated.mp4 ]; then
  echo -e "\n${YELLOW}Generating test 'truncated' MP4 file...${NC}"
  # Copy first 90% of the good file to create a truncated (corrupted) file
  dd if=tests/good.mp4 of=tests/truncated.mp4 bs=1024 count=$(( $(stat --format="%s" tests/good.mp4) / 1024 * 9 / 10 ))
else
  echo -e "\n${GREEN}Using existing test 'truncated' MP4 file${NC}"
fi

# Create another corrupt file with a different corruption method
if [ ! -f tests/corrupted_data.mp4 ]; then
  echo -e "\n${YELLOW}Generating a corrupted data MP4 file with different corruption type...${NC}"
  # Copy the good file
  cp tests/good.mp4 tests/corrupted_data.mp4
  # Corrupt the middle of the file (overwrite bytes in the middle)
  dd if=/dev/zero of=tests/corrupted_data.mp4 bs=1 count=1000 seek=10000 conv=notrunc
else
  echo -e "\n${GREEN}Using existing corrupted data test file${NC}"
fi

# Check if we should run Docker tests
run_docker_tests=1
if ! command_exists docker; then
  echo -e "\n${YELLOW}Docker not found. Skipping Docker-based tests.${NC}"
  run_docker_tests=0
fi

# Run Docker tests if available
if [ $run_docker_tests -eq 1 ]; then
  # Build the Docker image if it doesn't exist
  if ! docker image inspect mp4repair >/dev/null 2>&1; then
    echo -e "\n${YELLOW}Building Docker image...${NC}"
    docker build -t mp4repair .
  fi

  # Run the container to check if the good file is valid
  echo -e "\n${BLUE}===== TEST 1: CHECKING GOOD FILE WITH DOCKER =====${NC}"
  docker run --rm -v "$(pwd)/tests:/data" mp4repair /data/good.mp4 /data/good.mp4 /data/dummy_output.mp4

  # Run the container to repair the first bad file
  echo -e "\n${BLUE}===== TEST 2: REPAIRING TRUNCATED FILE WITH DOCKER =====${NC}"
  docker run --rm -v "$(pwd)/tests:/data" mp4repair /data/truncated.mp4 /data/good.mp4 /data/docker_repaired1.mp4

  # Run the container to repair the second bad file
  echo -e "\n${BLUE}===== TEST 3: REPAIRING CORRUPTED DATA FILE WITH DOCKER =====${NC}"
  docker run --rm -v "$(pwd)/tests:/data" mp4repair /data/corrupted_data.mp4 /data/good.mp4 /data/docker_repaired2.mp4
fi

# Run direct Python script tests
echo -e "\n${BLUE}===== TEST 4: CHECKING GOOD FILE WITH PYTHON SCRIPT =====${NC}"
./mp4_repair.py tests/good.mp4 tests/good.mp4 tests/script_dummy_output.mp4

echo -e "\n${BLUE}===== TEST 5: REPAIRING TRUNCATED FILE WITH PYTHON SCRIPT =====${NC}"
./mp4_repair.py tests/truncated.mp4 tests/good.mp4 tests/script_repaired1.mp4

echo -e "\n${BLUE}===== TEST 6: REPAIRING CORRUPTED DATA FILE WITH PYTHON SCRIPT =====${NC}"
./mp4_repair.py tests/corrupted_data.mp4 tests/good.mp4 tests/script_repaired2.mp4

# Verify results
echo -e "\n${BLUE}===== VERIFYING REPAIR RESULTS =====${NC}"

# Check Docker repaired files if Docker tests were run
if [ $run_docker_tests -eq 1 ]; then
  if [ -f tests/docker_repaired1.mp4 ]; then
    size=$(du -h tests/docker_repaired1.mp4 | cut -f1)
    echo -e "${GREEN}Docker repaired truncated file (size: $size)${NC}"
    
    # Check if ffprobe can read the file
    if ffprobe -v error tests/docker_repaired1.mp4 > /dev/null 2>&1; then
      echo -e "${GREEN}✓ Docker repaired truncated file is valid${NC}"
    else
      echo -e "${RED}✗ Docker repaired truncated file validation failed${NC}"
    fi
  else
    echo -e "${RED}✗ Docker failed to repair truncated file${NC}"
  fi
  
  if [ -f tests/docker_repaired2.mp4 ]; then
    size=$(du -h tests/docker_repaired2.mp4 | cut -f1)
    echo -e "${GREEN}Docker repaired corrupted data file (size: $size)${NC}"
    
    # Check if ffprobe can read the file
    if ffprobe -v error tests/docker_repaired2.mp4 > /dev/null 2>&1; then
      echo -e "${GREEN}✓ Docker repaired corrupted data file is valid${NC}"
    else
      echo -e "${RED}✗ Docker repaired corrupted data file validation failed${NC}"
    fi
  else
    echo -e "${RED}✗ Docker failed to repair corrupted data file${NC}"
  fi
fi

# Check Python script repaired files
if [ -f tests/script_repaired1.mp4 ]; then
  size=$(du -h tests/script_repaired1.mp4 | cut -f1)
  echo -e "${GREEN}Python script repaired truncated file (size: $size)${NC}"
  
  # Check if ffprobe can read the file
  if ffprobe -v error tests/script_repaired1.mp4 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Python script repaired truncated file is valid${NC}"
  else
    echo -e "${RED}✗ Python script repaired truncated file validation failed${NC}"
  fi
else
  echo -e "${RED}✗ Python script failed to repair truncated file${NC}"
fi

if [ -f tests/script_repaired2.mp4 ]; then
  size=$(du -h tests/script_repaired2.mp4 | cut -f1)
  echo -e "${GREEN}Python script repaired corrupted data file (size: $size)${NC}"
  
  # Check if ffprobe can read the file
  if ffprobe -v error tests/script_repaired2.mp4 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Python script repaired corrupted data file is valid${NC}"
  else
    echo -e "${RED}✗ Python script repaired corrupted data file validation failed${NC}"
  fi
else
  echo -e "${RED}✗ Python script failed to repair corrupted data file${NC}"
fi

# Final summary
echo -e "\n${BLUE}===== TEST SUMMARY =====${NC}"

# Count successful repairs
success_count=0
total_tests=0

# Docker tests if run
if [ $run_docker_tests -eq 1 ]; then
  total_tests=$((total_tests + 2))
  
  if [ -f tests/docker_repaired1.mp4 ] && ffprobe -v error tests/docker_repaired1.mp4 > /dev/null 2>&1; then
    success_count=$((success_count + 1))
  fi
  
  if [ -f tests/docker_repaired2.mp4 ] && ffprobe -v error tests/docker_repaired2.mp4 > /dev/null 2>&1; then
    success_count=$((success_count + 1))
  fi
fi

# Python script tests
total_tests=$((total_tests + 2))

if [ -f tests/script_repaired1.mp4 ] && ffprobe -v error tests/script_repaired1.mp4 > /dev/null 2>&1; then
  success_count=$((success_count + 1))
fi

if [ -f tests/script_repaired2.mp4 ] && ffprobe -v error tests/script_repaired2.mp4 > /dev/null 2>&1; then
  success_count=$((success_count + 1))
fi

# Print summary
echo -e "${BLUE}Successful repairs: $success_count / $total_tests${NC}"

if [ $success_count -eq $total_tests ]; then
  echo -e "\n${GREEN}ALL TESTS PASSED! MP4 Repair Tool is working correctly.${NC}"
elif [ $success_count -gt 0 ]; then
  echo -e "\n${YELLOW}PARTIAL SUCCESS: Some tests passed, but not all.${NC}"
  echo -e "The tool is working but may have limitations with certain types of corruption."
else
  echo -e "\n${RED}ALL TESTS FAILED: The repair tool is not functioning correctly.${NC}"
  echo -e "Please check the logs above for more details."
  exit 1
fi

echo -e "\n${GREEN}Tests completed.${NC}"
exit 0