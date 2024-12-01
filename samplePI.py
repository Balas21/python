import re
import json
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient
import spacy
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
import PyPDF2

# Azure credentials
FORM_RECOGNIZER_ENDPOINT = "https://<your-form-recognizer-resource>.cognitiveservices.azure.com/"
FORM_RECOGNIZER_KEY = "<your-form-recognizer-key>"

TEXT_ANALYTICS_ENDPOINT = "https://<your-text-analytics-resource>.cognitiveservices.azure.com/"
TEXT_ANALYTICS_KEY = "<your-text-analytics-key>"

# Initialize Azure clients
form_recognizer_client = DocumentAnalysisClient(
    endpoint=FORM_RECOGNIZER_ENDPOINT, credential=AzureKeyCredential(FORM_RECOGNIZER_KEY)
)
text_analytics_client = TextAnalyticsClient(
    endpoint=TEXT_ANALYTICS_ENDPOINT, credential=AzureKeyCredential(TEXT_ANALYTICS_KEY)
)

# Load spaCy language model
nlp = spacy.load("en_core_web_wd")

# Function to extract text and bounding boxes using Form Recognizer
def extract_text_with_form_recognizer(pdf_path):
    with open(pdf_path, "rb") as file:
        poller = form_recognizer_client.begin_analyze_document("prebuilt-read", document=file)
        result = poller.result()

    text_elements = []
    for page in result.pages:
        for line in page.lines:
            text_elements.append({
                "text": line.content,
                "bounding_box": line.bounding_box,
                "page_number": page.page_number
            })

    return text_elements

# Function to redact PII using Text Analytics, Form Recognizer, and spaCy
def redact_pii_with_combined_services(text_elements):
    redacted_details = []
    redacted_text_elements = []

    for element in text_elements:
        text = element["text"]
        page_number = element["page_number"]

        # --- Azure Text Analytics PII Detection ---
        response = text_analytics_client.recognize_pii_entities([text])[0]
        if not response.is_error:
            for entity in response.entities:
                text = text.replace(entity.text, "[REDACTED]")
                redacted_details.append({
                    "source": "Text Analytics",
                    "type": entity.category,
                    "value": entity.text,
                    "confidence": entity.confidence_score,
                    "page_number": page_number
                })

        # --- spaCy Detection ---
        doc = nlp(text)
        for ent in doc.ents:
            if ent.label_ in {"PERSON", "ORG", "GPE", "LOC", "DATE"}:
                text = text.replace(ent.text, "[REDACTED]")
                redacted_details.append({
                    "source": "spaCy",
                    "type": ent.label_,
                    "value": ent.text,
                    "confidence": 1.0,
                    "page_number": page_number
                })

        # --- Custom Patterns (e.g., NHS ID) ---
        nhs_pattern = r"\b\d{3}-\d{3}-\d{4}\b"
        custom_matches = re.findall(nhs_pattern, element["text"])
        for match in custom_matches:
            text = text.replace(match, "[REDACTED-NHS-ID]")
            redacted_details.append({
                "source": "Custom",
                "type": "Custom-NHS-ID",
                "value": match,
                "confidence": 1.0,
                "page_number": page_number
            })

        redacted_text_elements.append({**element, "redacted_text": text})

    return redacted_text_elements, redacted_details

# Write redacted text to a new PDF
def write_redacted_pdf(original_pdf, redacted_text_elements, output_pdf):
    with open(original_pdf, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        writer = PyPDF2.PdfWriter()

        for i, page in enumerate(reader.pages):
            packet = BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)

            # Get redacted text for the current page
            page_text = " ".join(
                elem["redacted_text"] for elem in redacted_text_elements if elem["page_number"] == i + 1
            )
            can.drawString(50, 750, page_text[:500])  # Adjust position as needed
            can.save()

            # Merge the redacted content with the original page
            packet.seek(0)
            new_pdf = PyPDF2.PdfReader(packet)
            page.merge_page(new_pdf.pages[0])
            writer.add_page(page)

        with open(output_pdf, "wb") as output:
            writer.write(output)

# Save redacted details to JSON
def save_redacted_details_to_json(redacted_details, json_file):
    with open(json_file, "w") as file:
        json.dump(redacted_details, file, indent=4)

# Main program
if __name__ == "__main__":
    input_pdf = "input.pdf"
    output_pdf = "redacted_output.pdf"
    json_file = "redacted_details.json"

    # Step 1: Extract text and layout with Form Recognizer
    text_elements = extract_text_with_form_recognizer(input_pdf)

    # Step 2: Redact PII using Text Analytics, Form Recognizer, and spaCy
    redacted_text_elements, redacted_details = redact_pii_with_combined_services(text_elements)

    # Step 3: Write redacted text to a new PDF
    write_redacted_pdf(input_pdf, redacted_text_elements, output_pdf)

    # Step 4: Save redacted details to JSON
    save_redacted_details_to_json(redacted_details, json_file)

    print(f"Redacted PDF saved as {output_pdf}")
    print(f"Redacted details saved as {json_file}")
