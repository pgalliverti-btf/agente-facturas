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
    if "factura" not in request.files:
        return jsonify({"error": "No se recibió archivo"}), 400
    
    archivo = request.files["factura"]
    extension = archivo.filename.split(".")[-1].lower()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{extension}") as tmp:
        archivo.save(tmp.name)
        resultado = procesar_factura(tmp.name)
        os.unlink(tmp.name)
    
    if resultado:
        return jsonify({"ok": True, "datos": resultado})
    else:
        return jsonify({"ok": False, "mensaje": "Duplicado o requiere revisión manual"})
    
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)