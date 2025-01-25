from flask import Blueprint, request, jsonify
import os
import openai
import subprocess
import uuid

bp = Blueprint('remove', __name__)

# Set your OpenAI API key via environment variable or hardcode (not recommended):
openai.api_key = os.getenv("OPENAI_API_KEY")

@bp.route("/", methods=["POST"])
def remove_filler_words_video():
    """
    Receives a video file, transcribes it with OpenAI Whisper API (segment-level),
    removes segments containing filler words, and returns a shortened video.
    """
    # Step 1: Save the uploaded file (e.g., .mp4)
    file = request.files['video']  # or 'audio' if desired
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
    filler_words = {"uh", "um", "ah", "like", "you know", "so", "basically"}

    # Step 4: Build a list of segments to keep (i.e., those that don't contain filler words)
    keep_segments = []
    for seg in segments:
        seg_text = seg["text"].lower()
        start_s = seg["start"]  # in seconds
        end_s   = seg["end"]    # in seconds

        # If this segment's text does NOT contain filler words, we keep it
        if not any(fw in seg_text for fw in filler_words):
            keep_segments.append((start_s, end_s))

    # Edge case: if no segments remain, return early
    if not keep_segments:
        return jsonify({
            "message": "All segments contained filler words!",
            "output": None
        }), 200

    # Step 5: Use FFmpeg to cut each kept segment from the video
    temp_files = []
    for i, (start_s, end_s) in enumerate(keep_segments):
        segment_filename = f"segment_{i}_{uuid.uuid4().hex}.mp4"
        segment_path = os.path.join("processed", segment_filename)

        cmd_cut = [
            "ffmpeg",
            "-y",               # Overwrite
            "-i", input_path,
            "-ss", str(start_s),
            "-to", str(end_s),
            "-c", "copy",       # Avoid re-encoding for speed
            segment_path
        ]
        subprocess.run(cmd_cut, check=True)
        temp_files.append(segment_path)

    # Step 6: Create a concat list file for FFmpeg
    concat_list_path = os.path.join("processed", f"concat_{uuid.uuid4().hex}.txt")
    with open(concat_list_path, "w") as f:
        for seg_file in temp_files:
            f.write(f"file '{os.path.abspath(seg_file)}'\n")

    # Step 7: Concatenate all segment files into one final video
    final_filename = f"no_fillers_{file.filename}"
    final_path = os.path.join("processed", final_filename)

    cmd_concat = [
        "ffmpeg",
        "-y",          # Overwrite
        "-f", "concat",
        "-safe", "0",  # Allow absolute paths in list
        "-i", concat_list_path,
        "-c", "copy",  # Again, no re-encoding
        final_path
    ]
    subprocess.run(cmd_concat, check=True)

    # (Optional) Cleanup temporary segments or the concat list:
    # for seg_file in temp_files:
    #     os.remove(seg_file)
    # os.remove(concat_list_path)

    return jsonify({
        "message": "Filler segments removed from the video!",
        "output": final_path
    })
