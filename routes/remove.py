from flask import Blueprint, request, jsonify
import os
import openai
import subprocess
import uuid
import re

bp = Blueprint('remove', __name__)

# Set your OpenAI API key via environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

@bp.route("/", methods=["POST"])
def remove_filler_words_video():
    """
    Receives a video file, transcribes it with OpenAI Whisper API (segment-level),
    removes segments containing filler words, and returns a shortened video.
    """
    # Step 1: Save the uploaded file (e.g., .mp4)
    file = request.files['video']  # Ensure your form field is named 'video'
    input_path = os.path.join('uploads', file.filename)
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('processed', exist_ok=True)
    file.save(input_path)

    # Step 2: Transcribe via OpenAI Whisper API with verbose JSON
    with open(input_path, "rb") as video_file:
        transcript = openai.Audio.transcribe(
            model="whisper-1",
            file=video_file,
            response_format="verbose_json"
        )

    # Extract segments from the response
    segments = transcript.get("segments", [])

    # Step 3: Define filler words
    # Start with a minimal set to avoid over-filtering
    filler_words = {"uh", "um", "ah", "like", "you know", "so", "basically"}

    # Step 4: Build a list of segments to keep (i.e., those that don't contain filler words)
    keep_segments = []
    for seg in segments:
        seg_text = seg["text"].lower()
        start_s = seg["start"]  # in seconds
        end_s = seg["end"]      # in seconds

        # Use regex to find whole word matches
        contains_filler = False
        for fw in filler_words:
            # Escape any regex special characters in filler words
            fw_escaped = re.escape(fw)
            # For multi-word fillers like "you know", match them as a phrase
            pattern = r'\b' + fw_escaped + r'\b'
            if re.search(pattern, seg_text):
                contains_filler = True
                print(f"Removing segment: [{start_s:.2f} - {end_s:.2f}], Text: {seg_text}")
                break
        if not contains_filler:
            keep_segments.append((start_s, end_s))
            print(f"Keeping segment: [{start_s:.2f} - {end_s:.2f}], Text: {seg_text}")

    # Edge case: if no segments remain, return early
    if not keep_segments:
        return jsonify({
            "message": "All segments contained filler words!",
            "output": None
        }), 200

    # Step 5: Use FFmpeg to cut each kept segment from the video with re-encoding
    temp_files = []
    for i, (start_s, end_s) in enumerate(keep_segments):
        segment_filename = f"segment_{i}_{uuid.uuid4().hex}.mp4"
        segment_path = os.path.join("processed", segment_filename)

        cmd_cut = [
            "ffmpeg",
            "-y",               # Overwrite if exists
            "-i", input_path,   # Input file
            "-ss", str(start_s),# Start time
            "-to", str(end_s),  # End time
            "-c:v", "libx264",  # Re-encode video to H.264
            "-c:a", "aac",      # Re-encode audio to AAC
            "-preset", "fast",  # Encoding preset
            "-crf", "22",       # Quality (lower is better)
            segment_path        # Output segment
        ]
        print(f"Running FFmpeg command: {' '.join(cmd_cut)}")
        try:
            subprocess.run(cmd_cut, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error: {e.stderr.decode()}")
            return jsonify({"error": "FFmpeg failed during segment cutting."}), 500
        temp_files.append(segment_path)

    # Step 6: Create a concat list file for FFmpeg
    concat_list_path = os.path.join("processed", f"concat_{uuid.uuid4().hex}.txt")
    with open(concat_list_path, "w") as f:
        for seg_file in temp_files:
            f.write(f"file '{os.path.abspath(seg_file)}'\n")

    # Step 7: Concatenate all segment files into one final video with re-encoding
    final_filename = f"no_fillers_{file.filename}"
    final_path = os.path.join("processed", final_filename)

    cmd_concat = [
        "ffmpeg",
        "-y",               # Overwrite if exists
        "-f", "concat",     # Use concat demuxer
        "-safe", "0",       # Allow absolute paths
        "-i", concat_list_path, # Input concat list
        "-c:v", "libx264",  # Ensure consistent codec
        "-c:a", "aac",      # Ensure consistent codec
        "-preset", "fast",  # Encoding preset
        "-crf", "22",       # Quality
        final_path          # Output final video
    ]
    print(f"Running FFmpeg concat command: {' '.join(cmd_concat)}")
    try:
        subprocess.run(cmd_concat, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg concat error: {e.stderr.decode()}")
        return jsonify({"error": "FFmpeg failed during concatenation."}), 500

    # Step 8: Cleanup temporary segments and concat list
    for seg_file in temp_files:
        os.remove(seg_file)
    os.remove(concat_list_path)

    return jsonify({
        "message": "Filler segments removed from the video!",
        "output": final_path
    })
