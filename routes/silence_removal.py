from flask import Blueprint, request, jsonify
from pydub import AudioSegment, silence
from utils.nlp_utils import remove_filler_words

bp = Blueprint('silence_removal', __name__)

@bp.route("/", methods=["POST"])
def process_audio():
    file = request.files['audio']
    input_path = f"./uploads/{file.filename}"
    output_path = f"./processed/processed_{file.filename}"

    # Load audio
    audio = AudioSegment.from_file(input_path)
    
    # Remove long silences
    non_silent = silence.detect_nonsilent(audio, min_silence_len=1000, silence_thresh=-30)
    processed_audio = sum([audio[start:end] for start, end in non_silent])

    # Save processed audio
    processed_audio.export(output_path, format="wav")
    
    # Remove filler words
    transcript = request.form['transcript']
    cleaned_transcript = remove_filler_words(transcript)

    return jsonify({"message": "Audio processed successfully!", "cleaned_transcript": cleaned_transcript})
