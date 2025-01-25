from flask import Flask, request, jsonify
from routes import denoise, remove, transcribe

app = Flask(__name__)

# Register blueprints for modularity
app.register_blueprint(denoise.bp, url_prefix='/denoise')
app.register_blueprint(transcribe.bp, url_prefix='/transcribe')
app.register_blueprint(remove.bp, url_prefix='/remove')

@app.route("/")
def home():
    return jsonify({"message": "Welcome to Trimify API!"})

if __name__ == "__main__":
    app.run(debug=True)
