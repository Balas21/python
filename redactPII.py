import re
import json
import PyPDF2
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
import spacy
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO

# Azure Cognitive Services credentials
AZURE_ENDPOINT = "https://<your-resource-name>.cognitiveservices.azure.com/"
AZURE_KEY = "<your-key>"

# Initialize Azure Text Analytics Client
def authenticate_client():
    return TextAnalyticsClient(endpoint=AZURE_ENDPOINT, credential=AzureKeyCredential(AZURE_KEY))

client = authenticate_client()

# Load spaCy language model
nlp = spacy.load("en_core_web_sm")

# Function to extract text from PDF
def extract_text_from_pdf(pdf_path):
    with open(pdf_path, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
        return text

# Redact PII with Azure and spaCy
def redact_pii_with_azure_and_spacy(text, client):
    redacted_text = text
    redacted_details = []

    # --- Azure PII Detection ---
    documents = [text]
    response = client.recognize_pii_entities(documents=documents)[0]

    if not response.is_error:
        for entity in response.entities:
            redacted_text = redacted_text.replace(entity.text, "[REDACTED]")
            redacted_details.append({
                "source": "Azure",
                "type": entity.category,
                "value": entity.text,
                "confidence": entity.confidence_score
            })

    # --- spaCy NER Detection ---
    doc = nlp(text)
    for ent in doc.ents:
        if ent.label_ in {"PERSON", "ORG", "GPE", "LOC", "DATE"}:  # Filter specific labels
            redacted_text = redacted_text.replace(ent.text, "[REDACTED]")
            redacted_details.append({
                "source": "spaCy",
                "type": ent.label_,
                "value": ent.text,
                "confidence": 1.0  # SpaCy does not provide confidence scores
            })

    # --- Custom Patterns (NHS ID Example) ---
    nhs_pattern = r"\b\d{3}-\d{3}-\d{4}\b"  # Example NHS ID pattern
    custom_matches = re.findall(nhs_pattern, text)
    for match in custom_matches:
        redacted_text = redacted_text.replace(match, "[REDACTED-NHS-ID]")
        redacted_details.append({
            "source": "Custom",
            "type": "Custom-NHS-ID",
            "value": match,
            "confidence": 1.0
        })

    return redacted_text, redacted_details

# Write redacted text to a new PDF
def write_redacted_pdf(original_pdf, redacted_text, output_pdf):
    with open(original_pdf, "rb") as file:
        reader = PyPDF2.PdfReader(file)
        writer = PyPDF2.PdfWriter()

        for page in reader.pages:
            packet = BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)

            # Write the redacted text on the page
            can.drawString(50, 750, redacted_text[:500])  # Adjust as needed
            can.save()

            # Merge the canvas with the original page
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

    # Step 1: Extract text from the PDF
    extracted_text = extract_text_from_pdf(input_pdf)

    # Step 2: Redact PII using Azure and spaCy
    redacted_text, redacted_details = redact_pii_with_azure_and_spacy(extracted_text, client)

    # Step 3: Write redacted text to a new PDF
    write_redacted_pdf(input_pdf, redacted_text, output_pdf)

    # Step 4: Save redacted details to JSON
    save_redacted_details_to_json(redacted_details, json_file)

    print(f"Redacted PDF saved as {output_pdf}")
    print(f"Redacted details saved as {json_file}")
