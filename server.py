import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from agent import procesar_factura
import tempfile

load_dotenv()
app = Flask(__name__)
CORS(app)
@app.route("/subir", methods=["POST"])
def subir():
    # ... todo el código de subir
    if resultado:
        return jsonify({"ok": True, "datos": resultado})
    else:
        return jsonify({"ok": False, "mensaje": "Duplicado o requiere revisión manual"})

@app.route("/")
def index():
    return open("index.html").read()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)