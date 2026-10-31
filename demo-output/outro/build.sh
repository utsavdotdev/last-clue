#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")"
python3 render.py
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_type,codec_name,width,height,avg_frame_rate,pix_fmt -of default=nokey=0:noprint_wrappers=1 the-last-clue-outro.mp4
