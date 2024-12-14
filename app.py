from flask import Flask, request, jsonify
from routes import denoise, transcribe, silence_removal

app = Flask(__name__)

# Register blueprints for modularity
app.register_blueprint(denoise.bp, url_prefix='/denoise')
app.register_blueprint(transcribe.bp, url_prefix='/transcribe')
app.register_blueprint(silence_removal.bp, url_prefix='/process')

@app.route("/")
def home():
    return jsonify({"message": "Welcome to Trimify API!"})

if __name__ == "__main__":
    app.run(debug=True)
