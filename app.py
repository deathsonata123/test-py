from flask import Flask, request, jsonify, send_from_directory
import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_path
import os
import requests
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
RESULT_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

def extract_text_from_pdf(pdf_path):
    """Extracts text from a PDF using OCR."""
    images = convert_from_path(pdf_path)
    extracted_text = []
    for img in images:
        text = pytesseract.image_to_string(img)
        extracted_text.append(text)
    return extracted_text

def annotate_pdf(student_pdf, markscheme_pdf, output_filename):
    """Compares student answers with the mark scheme and annotates the PDF."""
    student_answers = extract_text_from_pdf(student_pdf)
    correct_answers = extract_text_from_pdf(markscheme_pdf)

    pdf_document = fitz.open(student_pdf)

    for page_num, page in enumerate(pdf_document):
        # Skip if OCR did not return text for this page
        if page_num >= len(student_answers):
            continue

        text = student_answers[page_num]
        y_offset = 0  # To avoid annotation overlap on the same page
        for answer in correct_answers:
            # Using case-insensitive matching
            symbol = "✔" if answer.strip().lower() in text.lower() else "✖"
            page.insert_text((50, 50 + y_offset), symbol, fontsize=20, color=(1, 0, 0))
            y_offset += 25  # Increment offset for the next annotation

    output_path = os.path.join(RESULT_FOLDER, output_filename)
    pdf_document.save(output_path)
    pdf_document.close()  # Clean up and close the document
    return output_path

def download_file(file_url, folder):
    """Downloads a file from a URL and saves it to the specified folder."""
    try:
        response = requests.get(file_url)
        response.raise_for_status()
        # Get the filename from the URL and secure it
        filename = secure_filename(file_url.split("/")[-1])
        file_path = os.path.join(folder, filename)
        with open(file_path, "wb") as f:
            f.write(response.content)
        return file_path, filename
    except Exception as e:
        raise Exception(f"Error downloading file from {file_url}: {e}")

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "API is working! Use /check-pdf endpoint."})

@app.route("/check-pdf", methods=["POST"])
def check_pdf():
    """API Endpoint to process and annotate PDFs using file URLs."""
    try:
        data = request.get_json()
        if not data or "student_pdf_url" not in data or "markscheme_pdf_url" not in data:
            return jsonify({"error": "Missing required URLs in JSON payload"}), 400

        student_pdf_url = data["student_pdf_url"]
        markscheme_pdf_url = data["markscheme_pdf_url"]

        # Download the student and markscheme PDFs
        student_path, student_filename = download_file(student_pdf_url, UPLOAD_FOLDER)
        markscheme_path, _ = download_file(markscheme_pdf_url, UPLOAD_FOLDER)

        output_filename = f"checked_{student_filename}"
        annotated_pdf_path = annotate_pdf(student_path, markscheme_path, output_filename)

        file_url = f"{request.host_url}download/{output_filename}"

        return jsonify({
            "message": "AI Check Completed",
            "file_url": file_url
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download/<filename>", methods=["GET"])
def download_file_route(filename):
    """Serve the annotated PDF for download."""
    return send_from_directory(RESULT_FOLDER, filename, as_attachment=True)

# ✅ Updated block below
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
