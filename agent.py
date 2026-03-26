import os
import base64
import gspread
import hashlib
import json

from datetime import datetime
from anthropic import Anthropic
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def conectar_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    google_creds = os.getenv("GOOGLE_CREDENTIALS")
    if google_creds:
        # En producción (Render) — lee desde variable de entorno
        creds_dict = json.loads(google_creds)
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    else:
        # En local — lee desde archivo
        creds = Credentials.from_service_account_file("credentials/google.json", scopes=scopes)
    
    sheets_client = gspread.authorize(creds)
    return sheets_client.open("facturas-agente").sheet1

client = Anthropic()

tools = [
    {
        "name": "extraer_datos_factura",
        "description": "Extrae la fecha y el monto total de una imagen de factura argentina.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fecha": {"type": "string", "description": "Fecha de la factura en formato DD/MM/AAAA"},
                "monto_total": {"type": "number", "description": "Monto total de la factura en pesos argentinos"},
                "confianza": {"type": "string", "enum": ["alta", "media", "baja"]}
            },
            "required": ["fecha", "monto_total", "confianza"]
        }
    },
    {
        "name": "marcar_revision_manual",
        "description": "Marca una factura para revisión manual.",
        "input_schema": {
            "type": "object",
            "properties": {
                "motivo": {"type": "string"}
            },
            "required": ["motivo"]
        }
    }
]

def hash_archivo(imagen_path):
    with open(imagen_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def es_duplicado(sheet, hash_actual):
    filas = sheet.get_all_values()
    for fila in filas[1:]:
        if len(fila) > 6 and fila[6] == hash_actual:
            return True
    return False

def subir_a_supabase(imagen_path):
    nombre_archivo = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.path.basename(imagen_path)}"
    with open(imagen_path, "rb") as f:
        contenido = f.read()
    extension = imagen_path.split(".")[-1].lower()
    mime_type = "image/jpeg" if extension in ["jpg", "jpeg"] else "image/png"
    supabase.storage.from_("facturas").upload(path=nombre_archivo, file=contenido, file_options={"content-type": mime_type})
    return supabase.storage.from_("facturas").get_public_url(nombre_archivo)

def procesar_factura(imagen_path: str):
    sheet = conectar_sheets()
    hash_actual = hash_archivo(imagen_path)

    if es_duplicado(sheet, hash_actual):
        print(f"⚠️  Duplicado ignorado: {imagen_path}")
        return None

    with open(imagen_path, "rb") as f:
        imagen_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    extension = imagen_path.split(".")[-1].lower()
    media_type = "image/jpeg" if extension in ["jpg", "jpeg"] else "image/png"

    print(f"\n🤖 Procesando: {imagen_path}")

    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1024,
        tools=tools,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": imagen_b64}},
                {"type": "text", "text": "Analizá esta factura argentina y extraé la fecha y el monto total. Si no podés leerla claramente, marcala para revisión manual."}
            ]
        }]
    )

    for block in response.content:
        if block.type == "tool_use":
            tool_name = block.name
            tool_input = block.input

            if tool_name == "extraer_datos_factura":
                print(f"✅ Fecha: {tool_input['fecha']} | Monto: ${tool_input['monto_total']:,.2f} | Confianza: {tool_input['confianza']}")
                url = subir_a_supabase(imagen_path)
                sheet.append_row([
                    os.path.basename(imagen_path),
                    tool_input["fecha"],
                    tool_input["monto_total"],
                    tool_input["confianza"],
                    datetime.now().strftime("%d/%m/%Y %H:%M"),
                    url,
                    hash_actual
                ])
                print(f"📊 Guardado en Sheets")
                return tool_input

            elif tool_name == "marcar_revision_manual":
                print(f"⚠️  Revisión manual: {tool_input['motivo']}")
                sheet.append_row([os.path.basename(imagen_path), "REVISAR", 0, "baja", datetime.now().strftime("%d/%m/%Y %H:%M"), "", hash_actual])
                return None

def procesar_carpeta(carpeta: str):
    """Procesa todas las imágenes de una carpeta."""
    extensiones = [".jpg", ".jpeg", ".png"]
    archivos = [f for f in os.listdir(carpeta) if any(f.lower().endswith(e) for e in extensiones)]
    
    if not archivos:
        print("No hay imágenes para procesar.")
        return

    print(f"\n📂 Procesando {len(archivos)} archivos en '{carpeta}'...")
    for archivo in archivos:
        procesar_factura(os.path.join(carpeta, archivo))
    print(f"\n✅ Lote completo.")

if __name__ == "__main__":
    # Para procesar una sola factura:
    # procesar_factura("factura_prueba.jpg")
    
    # Para procesar una carpeta entera:
    procesar_carpeta("facturas_entrada")