import os
import subprocess
from flask import Blueprint, request, jsonify
from speechbrain.pretrained import SpectralMaskEnhancement

bp = Blueprint('denoise', __name__)

# Initialize SpeechBrain's pre-trained denoiser
denoiser = SpectralMaskEnhancement.from_hparams(
    source="speechbrain/metricgan-plus-voicebank",
    savedir="pretrained_models/metricgan-plus-voicebank"
)

def replace_audio_in_video(video_path, audio_path, output_video_path):
    try:
        # Use FFmpeg to replace the audio in the video
        subprocess.run(
            [
                'ffmpeg', '-i', video_path, '-i', audio_path,
                '-c:v', 'copy', '-map', '0:v:0', '-map', '1:a:0',
                '-shortest', output_video_path
            ],
            check=True
        )
        if not os.path.exists(output_video_path):
            raise Exception("Failed to create the output video with new audio")
        print(f"Successfully created: {output_video_path}")
        return output_video_path
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error: {str(e)}")
        raise
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise


@bp.route("/", methods=["POST"])
def denoise_audio():
    file = request.files['video']
    original_video_path = os.path.abspath(f"./uploads/{file.filename}")
    base_name = os.path.splitext(file.filename)[0]
    extracted_audio_path = os.path.abspath(f"./uploads/{base_name}_original.wav")
    first_pass_audio_path = os.path.abspath(f"./processed/{base_name}_denoised.wav")
    first_pass_video_path = os.path.abspath(f"./processed/{base_name}_denoised.mp4")
    second_pass_audio_path = os.path.abspath(f"./processed/{base_name}_denoised_twice.wav")
    second_pass_video_path = os.path.abspath(f"./processed/{base_name}_denoised_twice.mp4")

    processed_dir = os.path.abspath("./processed")
    os.makedirs(processed_dir, exist_ok=True)

    # Save the uploaded video file
    file.save(original_video_path)

    try:
        # Step 1: Extract audio from the original video
        subprocess.run(
            [
                'ffmpeg', '-i', original_video_path, '-vn', '-ar', '16000', '-ac', '1',
                '-acodec', 'pcm_s16le', extracted_audio_path
            ],
            check=True
        )

        if not os.path.exists(extracted_audio_path):
            return jsonify({"error": "Failed to extract audio from the original video"}), 500

        # Step 2: First denoising pass
        try:
            denoiser.enhance_file(extracted_audio_path, first_pass_audio_path)
        except Exception as denoise_error:
            return jsonify({"error": f"First denoising pass failed: {str(denoise_error)}"}), 500

        # Merge first-pass denoised audio with the original video
        subprocess.run(
            [
                'ffmpeg', '-i', original_video_path, '-i', first_pass_audio_path,
                '-c:v', 'copy', '-c:a', 'aac', first_pass_video_path
            ],
            check=True
        )

        if not os.path.exists(first_pass_video_path):
            return jsonify({"error": "Failed to create first-pass video with denoised audio"}), 500

        # Step 3: Extract audio from the first-pass video
        subprocess.run(
            [
                'ffmpeg', '-i', first_pass_video_path, '-vn', '-ar', '16000', '-ac', '1',
                '-acodec', 'pcm_s16le', second_pass_audio_path
            ],
            check=True
        )

        if not os.path.exists(second_pass_audio_path):
            return jsonify({"error": "Failed to extract audio from the first-pass video"}), 500

        # Step 4: Second denoising pass
        try:
            denoiser.enhance_file(second_pass_audio_path, second_pass_audio_path)
        except Exception as denoise_error:
            return jsonify({"error": f"Second denoising pass failed: {str(denoise_error)}"}), 500

        # Step 5: Replace audio in second-pass video with the second-pass denoised audio
        replace_audio_in_video(first_pass_video_path, second_pass_audio_path, second_pass_video_path)

        if not os.path.exists(second_pass_video_path):
            return jsonify({"error": "Failed to create second-pass video with denoised audio"}), 500

        return jsonify({
            "message": "Video denoised successfully after two passes!",
            "output": second_pass_video_path
        })

    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Subprocess failed: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
