#!/usr/bin/env bash
# Synthesize a tiny, license-clean test dataset (sine tones + noise only).
# Nothing here is copyrighted audio; everything is generated with ffmpeg.
#
# Usage: ./make_testdata.sh [output_dir]   (default: this script's directory)
set -euo pipefail

OUT="${1:-$(dirname "$0")}"
mkdir -p "$OUT"
cd "$OUT"

echo "== base tones =="
ffmpeg -v error -y -f lavfi -i "sine=frequency=440:duration=3:sample_rate=44100" \
  -ac 2 tone-3s-stereo-44k.wav
ffmpeg -v error -y -f lavfi -i "sine=frequency=880:duration=3:sample_rate=48000" \
  -ac 1 tone-3s-mono-48k.wav

echo "== format conversions =="
ffmpeg -v error -y -i tone-3s-stereo-44k.wav -c:a libmp3lame tone-3s.mp3
ffmpeg -v error -y -i tone-3s-stereo-44k.wav -c:a flac tone-3s.flac
ffmpeg -v error -y -i tone-3s-stereo-44k.wav -c:a libvorbis tone-3s.ogg
ffmpeg -v error -y -i tone-3s-stereo-44k.wav -c:a libopus tone-3s.opus
ffmpeg -v error -y -i tone-3s-stereo-44k.wav -c:a aac tone-3s.m4a

echo "== edge cases =="
head -c 200 tone-3s-stereo-44k.wav > tone-truncated.wav   # valid header, missing data
: > empty.wav                                              # zero bytes
cp tone-3s-stereo-44k.wav tone-wrong-extension.mp3          # wav data, mp3 name

echo "== 8s music mix for the real-model test =="
ffmpeg -v error -y \
  -f lavfi -i "sine=frequency=110:duration=8:sample_rate=44100" \
  -f lavfi -i "sine=frequency=440:duration=8:sample_rate=44100" \
  -f lavfi -i "anoisesrc=color=pink:duration=8:sample_rate=44100:amplitude=0.12" \
  -filter_complex "[0:a][1:a][2:a]amix=inputs=3:duration=longest:dropout_transition=0:normalize=0,volume=0.6[a]" \
  -map "[a]" -ac 2 -ar 44100 music-mix-8s.wav

echo "== done =="
ls -la "$OUT"
