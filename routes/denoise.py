from flask import Blueprint, request, jsonify
import moviepy as mp
import ffmpeg

bp = Blueprint('denoise', __name__)

@bp.route("/", methods=["POST"])
def denoise_video():
    file = request.files['video']
    input_path = f"./uploads/{file.filename}"
    output_path = f"./processed/denoised_{file.filename}"
    
    file.save(input_path)
    
    # Using FFmpeg for denoising
    ffmpeg.input(input_path).output(output_path, af='anlmdn').run()
    
    return jsonify({"message": "Video denoised successfully!", "output": output_path})
