#!/usr/bin/env python3
"""
Convert a Libby audiobook (multiple MP3 parts + metadata.json) into a single M4B file with chapters.

Usage: python createAudiobook.py /path/to/audiobook/directory
"""
import os
import sys
import subprocess
import json
import tempfile
from pathlib import Path

# Import the buildChapters module
import buildChapters


def check_ffmpeg():
    """Check if FFmpeg is installed"""
    try:
        subprocess.run(
            ("ffmpeg", "-version"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("Error: FFmpeg not found. Please install it: https://www.ffmpeg.org/download.html")
        sys.exit(1)


def find_mp3_files(directory):
    """Find all MP3 files in the directory, sorted naturally"""
    mp3_files = sorted(
        [f for f in Path(directory).glob("*.mp3")],
        key=lambda x: x.name
    )
    if not mp3_files:
        print(f"Error: No MP3 files found in {directory}")
        sys.exit(1)
    return mp3_files


def load_metadata(directory):
    """Load and parse the metadata.json file"""
    metadata_path = Path(directory) / "metadata" / "metadata.json"
    if not metadata_path.exists():
        print(f"Error: metadata.json not found at {metadata_path}")
        sys.exit(1)

    with open(metadata_path, 'r') as f:
        raw_metadata = json.load(f)

    return buildChapters.Metadata.from_json(raw_metadata)


def create_audiobook(directory, output_path=None):
    """Create M4B audiobook from MP3 parts and metadata"""
    directory = Path(directory).resolve()

    print(f"Processing audiobook in: {directory}")

    # Load metadata
    print("Loading metadata...")
    metadata = load_metadata(directory)
    print(f"  Title: {metadata.title}")
    if metadata.author:
        print(f"  Author: {metadata.author}")
    if metadata.narrator:
        print(f"  Narrator: {metadata.narrator}")
    print(f"  Chapters: {len(metadata.chapters)}")

    # Find MP3 files
    print("\nFinding MP3 files...")
    mp3_files = find_mp3_files(directory)
    print(f"  Found {len(mp3_files)} MP3 files")
    for f in mp3_files:
        print(f"    - {f.name}")

    # Determine output path
    if output_path is None:
        # Use the audiobook title, sanitized for filename
        safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_'
                            for c in metadata.title)
        output_path = directory / f"{safe_title}.m4b"
    else:
        output_path = Path(output_path)

    print(f"\nOutput will be: {output_path}")

    # Create temporary files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create ffmetadata file
        print("\nGenerating chapter metadata...")
        ffmetadata_path = tmpdir / "ffmetadata.txt"
        ffmetadata_content = buildChapters.metadata_to_ffmpeg(metadata)
        with open(ffmetadata_path, 'w', encoding='utf-8') as f:
            f.write(ffmetadata_content)

        # Create concat list file for ffmpeg
        print("Creating concatenation list...")
        concat_list_path = tmpdir / "concat.txt"
        with open(concat_list_path, 'w', encoding='utf-8') as f:
            for mp3_file in mp3_files:
                # Use absolute paths and escape special characters
                escaped_path = str(mp3_file.resolve()).replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        # Run FFmpeg to concatenate and convert
        print("\nConverting to M4B (this may take a few minutes)...")
        ffmpeg_cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_path),
            "-i", str(ffmetadata_path),
            "-map_metadata", "1",
            "-c:a", "aac",
            "-b:a", "64k",
            "-vn",
            "-f", "ipod",
            "-y",  # Overwrite output file if it exists
            str(output_path)
        ]

        try:
            result = subprocess.run(
                ffmpeg_cmd,
                check=True,
                capture_output=True,
                text=True
            )
            print(f"\n✓ Success! Created: {output_path}")

            # Show file size
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"  File size: {size_mb:.1f} MB")

        except subprocess.CalledProcessError as e:
            print(f"\n✗ FFmpeg error occurred:")
            print(e.stderr)
            sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python createAudiobook.py /path/to/audiobook/directory [output.m4b]")
        print("\nThe directory should contain:")
        print("  - MP3 files (Part 001.mp3, Part 002.mp3, etc.)")
        print("  - metadata/metadata.json")
        sys.exit(1)

    check_ffmpeg()

    directory = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    create_audiobook(directory, output_path)


if __name__ == "__main__":
    main()
