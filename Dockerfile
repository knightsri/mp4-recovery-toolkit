# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set labels for the image
LABEL maintainer="Your Name <your.email@example.com>"
LABEL description="MP4 Recovery Toolkit - Runs a suite of Python scripts to repair and analyze damaged MP4 files using FFmpeg."
LABEL version="1.2.1"

# Install FFmpeg (which includes ffprobe)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy all necessary scripts
COPY mp4_recovery_master.py ./mp4_recovery_master.py
COPY recovery_techniques/ ./recovery_techniques/
COPY mp4_info.py ./mp4_info.py

# Copy requirements.txt and install any Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Make scripts executable (optional, as we call them with python)
RUN chmod +x mp4_recovery_master.py mp4_info.py

# Create wrapper scripts for direct tool access
RUN echo '#!/bin/bash\n\
if [ "$1" = "ffmpeg" ] || [ "$1" = "ffprobe" ]; then\n\
  exec "$@"\n\
elif [ "$1" = "--info" ] && [ -n "$2" ]; then\n\
  exec python -u /app/mp4_info.py "$2"\n\
else\n\
  exec python -u /app/mp4_recovery_master.py "$@"\n\
fi' > /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

# Define mount points for data.
VOLUME ["/data", "/input", "/reference", "/output"]

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set the entrypoint to our wrapper script
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command (will be overridden by `docker run` arguments for repair, or by --list)
CMD ["--help"]