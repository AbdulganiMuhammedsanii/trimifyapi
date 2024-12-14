import subprocess
import os
import requests
from flask import Blueprint, request, jsonify
from dotenv import load_dotenv
load_dotenv()

bp = Blueprint('transcribe', __name__)

@bp.route("/", methods=["POST"])
def transcribe_video():
    file = request.files['video']
    input_path = f"./uploads/{file.filename}"
    audio_path = f"./processed/{file.filename.split('.')[0]}.wav"

    # Save the uploaded video
    file.save(input_path)

    try:
        # Extract audio using ffmpeg
        subprocess.run([
            "ffmpeg", "-i", input_path, "-vn", "-acodec", "pcm_s16le",
            "-ar", "44100", "-ac", "2", audio_path
        ], check=True)

        # Get the OpenAI API key from the environment
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return jsonify({"error": "OpenAI API key not found in environment variables"}), 500


        # Call OpenAI Whisper API for transcription
        with open(audio_path, "rb") as audio_file:
            response = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={
                    "Authorization": f"Bearer {api_key}"
                },
                files={
                    "file": audio_file,
                },
                data={
                    "model": "whisper-1"
                },
            )
            # Ensure the response is successful
            if response.status_code == 200:
                transcription = response.json()
                return jsonify({"transcription": transcription.get('text', 'No transcription available')})
            else:
                return jsonify({"error": f"OpenAI API error: {response.text}"}), response.status_code

    except subprocess.CalledProcessError:
        return jsonify({"error": "Failed to extract audio from video."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
