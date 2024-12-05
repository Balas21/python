import fitz  # PyMuPDF
import spacy
import re
import easyocr
import json

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

# Initialize EasyOCR reader
reader = easyocr.Reader(['en'])

# Custom pattern for identifying DOB
DOB_PATTERN = r"\b\d{2}/\d{2}/\d{4}\b"  # Matches date patterns like 12/12/2000

def redact_text(page, redact_regions):
    """Black out specified regions on a PDF page."""
    for rect in redact_regions:
        page.add_redact_annot(rect, fill=(0, 0, 0))  # Add redaction with black fill
    page.apply_redactions()  # Apply the redactions to the page

def find_pii(text):
    """Find PII (Person, Address, DOB) in text using spaCy."""
    doc = nlp(text)
    pii_regions = []

    # Named Entity Recognition for PERSON and GPE (General Location)
    for ent in doc.ents:
        if ent.label_ in ["PERSON", "GPE"]:  # Add more labels as needed
            pii_regions.append({"text": ent.text, "label": ent.label_})

    # Match custom DOB pattern
    dob_matches = list(re.finditer(DOB_PATTERN, text))
    for match in dob_matches:
        pii_regions.append({"text": match.group(), "label": "DOB"})

    return pii_regions

def extract_image_text(image_bytes):
    """Extract text from an image using EasyOCR."""
    results = reader.readtext(image_bytes)
    text = " ".join([res[1] for res in results])  # Concatenate all detected texts
    return text

def redact_pdf(input_pdf_path, output_pdf_path, json_output_path):
    """Redact PII data (including text in images) in a PDF and save JSON report."""
    pdf_document = fitz.open(input_pdf_path)
    redaction_report = []

    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        text = page.get_text("text")
        rects_to_redact = []
        page_report = {"page_number": page_num + 1, "redactions": []}

        # Find PII in text
        for pii in find_pii(text):
            rects = page.search_for(pii["text"])  # Find bounding box for text
            if rects:
                for rect in rects:
                    rects_to_redact.append(rect)
                    page_report["redactions"].append({
                        "text": pii["text"],
                        "type": pii["label"],
                        "coordinates": [rect.x0, rect.y0, rect.x1, rect.y1],
                    })

        # Check for images and redact content
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = pdf_document.extract_image(xref)
            image_bytes = base_image["image"]

            # Extract and analyze text from image
            image_text = extract_image_text(image_bytes)
            pii_in_image = find_pii(image_text)
            if pii_in_image:
                rect = page.get_image_bbox(img_index)
                rects_to_redact.append(rect)
                for pii in pii_in_image:
                    page_report["redactions"].append({
                        "text": pii["text"],
                        "type": pii["label"],
                        "coordinates": [rect.x0, rect.y0, rect.x1, rect.y1],
                    })

        # Redact PII regions with black rectangles
        redact_text(page, rects_to_redact)
        redaction_report.append(page_report)

    # Save redacted PDF
    pdf_document.save(output_pdf_path)
    pdf_document.close()

    # Save JSON report
    with open(json_output_path, "w") as json_file:
        json.dump(redaction_report, json_file, indent=4)

    print(f"Redacted PDF saved to {output_pdf_path}")
    print(f"Redaction report saved to {json_output_path}")

# Run the redaction function
input_pdf = "input.pdf"  # Replace with your input PDF path
output_pdf = "redacted_output.pdf"
json_output = "redaction_report.json"
redact_pdf(input_pdf, output_pdf, json_output)

print(f"Redacted PDF saved to {output_pdf}")
print(f"Redaction report saved to {json_output}")
