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
    removes segments containing filler words, and returns a shortened video
    with crossfade transitions between cuts.

    Returns:
    JSON with file path if successful.
    Otherise, status code and error message.
    """
    # Step 1: Save the uploaded file
    #get file by request.files['video]
    #input_path = os.path.join('uploads', file.filename)
    file = request.files['video']  # Ensure your form field is named 'video'
    input_path = os.path.join('uploads', file.filename)

    #make new directories with os.makedirs('name', exist_ok=True),
    #if exist dont make
    #and last file.save(input.path)
    os.makedirs('uploads', exist_ok=True)
    os.makedirs('processed', exist_ok=True)
    file.save(input_path)

    # Step 2: Transcribe via OpenAI Whisper API with verbose JSON
    #open the passed in unput path as video_file
    # with python openai you say transcript = openai.Audio.transcribe(model=, file=, response_format=)
    with open(input_path, "rb") as video_file:
        transcript = openai.Audio.transcribe(
            model="whisper-1",
            file=video_file,
            response_format="verbose_json"
        )

    # Extract segments from the response
    #assign to segments if not empty
    segments = transcript.get("segments", [])

    # Step 3: Define filler words
    filler_words = {"uh", "um", "ah", "like", "you know", "so", "basically"}

    # Step 4: Build a list of segments to keep
    # seg in segments has value for text as seg["text"]
    # seg["start"] and seg["end"] for the timestamp for start and end of words
    keep_segments = []
    for seg in segments:
        seg_text = seg["text"].lower()
        start_s = seg["start"]  # in seconds
        end_s = seg["end"]      # in seconds

        # Check for filler words using regex
        contains_filler = False
        for fw in filler_words:
            fw_escaped = re.escape(fw)
            pattern = r'\b' + fw_escaped + r'\b'
            if re.search(pattern, seg_text):
                contains_filler = True
                print(f"Removing segment: [{start_s:.2f} - {end_s:.2f}], Text: {seg_text}")
                break
        #for all possible filler words we use regex to check if it is in the seg and remove that clip
        #if it does not contain it we keep that sengment and append it
        if not contains_filler:
            keep_segments.append((start_s, end_s))
            print(f"Keeping segment: [{start_s:.2f} - {end_s:.2f}], Text: {seg_text}")

    # Edge case: if no segments remain, return early
    #somehow the segments to keep are empty, then we just say no filler words and quit
    # and add status code after
    if not keep_segments:
        return jsonify({
            "message": "All segments contained filler words!",
            "output": None
        }), 200

    # Step 5: Cut each kept segment from the video
    # we are going to cut the segments from the video
    temp_files = []
    #enumerate all the segments and define unique name for each clip segment and 
    #begin the process of curring the video using the cmd cut
    # there are several fields including the ffmpeg, input path, the start and end time path,
    # preset values and segment path. 
    #we try to do the cut process and ifit fails we return the error status code.
    for i, (start_s, end_s) in enumerate(keep_segments):
        segment_filename = f"segment_{i}_{uuid.uuid4().hex}.mp4"
        segment_path = os.path.join("processed", segment_filename)

        cmd_cut = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-ss", str(start_s),
            "-to", str(end_s),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            "-crf", "22",
            segment_path
        ]
        print(f"Running FFmpeg command: {' '.join(cmd_cut)}")
        try:
            subprocess.run(cmd_cut, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error: {e.stderr.decode()}")
            return jsonify({"error": "FFmpeg failed during segment cutting."}), 500
        #append to the temp files that we will be stitching together after.
        
        temp_files.append(segment_path)

    # Step 6: If there's only one segment, we're done
    #simply return one video if no fillers and rename the file
    final_filename = f"no_fillers_{file.filename}"
    final_path = os.path.join("processed", final_filename)
    if len(temp_files) == 1:
        os.rename(temp_files[0], final_path)
        return jsonify({
            "message": "Filler segments removed (only one segment)!",
            "output": final_path
        }), 200

    # Otherwise, pairwise crossfade the segments
    CROSSFADE_DURATION = 0.5  # seconds of overlap
    merged_path = temp_files[0]


    #we will iterate through all the clips
    for i in range(1, len(temp_files)):
        next_segment = temp_files[i]
        temp_merged = os.path.join("processed", f"merged_{uuid.uuid4().hex}.mp4")

        # Get the duration of the current merged file
        #this gives us the duration of the current file
        probe_cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            merged_path
        ]
        #probe_cmd gives us this duration
        try:
            result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            duration_merged = float(result.stdout.strip())
        except subprocess.CalledProcessError as e:
            print(f"ffprobe error: {e.stderr}")
            return jsonify({"error": "ffprobe failed to get video duration."}), 500

        # Blend videos together
        # The video crossfade offset: near the end of the current clip
        #using the given duration_merged-crossfade duration. as long as the clip is long enough we crossfad with next clip.
        offset = max(0, duration_merged - CROSSFADE_DURATION)

        # Build filter_complex for video xfade + audio acrossfade (with resampling)
        #ensuring we keep audio and the appropriate crossfade.
        filter_complex = (
            f"[0:v][1:v] xfade=transition=fade:duration={CROSSFADE_DURATION}:offset={offset}[v];"
            f"[0:a]aresample=async=1:first_pts=0[a0];"
            f"[1:a]aresample=async=1:first_pts=0[a1];"
            f"[a0][a1]acrossfade=d={CROSSFADE_DURATION}[a]"
        )
        #implement the xfade_cmd as well.
        xfade_cmd = [
            "ffmpeg", "-y",
            "-i", merged_path,
            "-i", next_segment,
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            "-crf", "22",
            temp_merged
        ]

        print(f"Running FFmpeg crossfade command: {' '.join(xfade_cmd)}")
        try:
            subprocess.run(xfade_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg crossfade error: {e.stderr.decode()}")
            return jsonify({"error": "FFmpeg failed during crossfade merging."}), 500

        # Remove the old merged_path if not the first segment file
        if merged_path != temp_files[0]:
            try:
                os.remove(merged_path)
            except OSError:
                pass
        #this is the updated path and it will continue for all the segments
        merged_path = temp_merged

    # Rename the final merged file to the final output
    # we finally finished merging
    os.rename(merged_path, final_path)

    # Clean up
    #delete the segments that were created.
    for seg_file in temp_files:
        if os.path.exists(seg_file):
            os.remove(seg_file)
    #made it to this point so successful status code.
    return jsonify({
        "message": "Filler segments removed with crossfade transitions!",
        "output": final_path
    }), 200
