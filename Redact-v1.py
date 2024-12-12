import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import pytesseract
import io
import spacy  # Load spaCy model
import os  # To handle saving files
from spacy.matcher import Matcher
from spacy.tokens import Span
from spacy.pipeline import EntityRuler
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Update this path as needed

# Load spaCy model
nlp = spacy.load("en_core_web_trf")

def redact_pii_text(page):
   
    text_blocks = page.get_text("dict")["blocks"]
    
    for block in text_blocks:
        if "lines" in block:
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"]
                    bbox = fitz.Rect(span["bbox"])
                    
                    # Detect PII using spaCy
                    doc = nlp(text)                    
                    for ent in doc.ents:
                        if ent.label_ in ["PERSON", "EMAIL", "PHONE", "GPE","UK_POSTCODE","APP_NUMBER"]:
                           for rect in page.search_for(ent.text): 
                            page.add_redact_annot(rect,fill=(0, 0, 0))  # mark as "remove this" 

    page.apply_redactions()   
  


def redact_pii_image(image, page_number, img_index, output_folder):
    # OCR to extract text
    text = pytesseract.image_to_string(image)
    ocr_result = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    #print(f"OCR Result {ocr_result}")
    print(f"ocr_result['text']:{ocr_result['text']}")
    ocr_text = " ".join(ocr_result['text'])
    print(f"ocr_text from image {ocr_text}")
    doc = nlp(ocr_text)
   
    # Prepare for drawing on the image
    draw = ImageDraw.Draw(image)
    
    # Get bounding boxes for detected words
    boxes = pytesseract.image_to_boxes(image)
    
    for ent in doc.ents:
        print(f"Document entities: {ent} and label {ent.label_}")
        if ent.label_ in ["PERSON", "EMAIL", "PHONE", "ORG", "GPE"]:  
            # Loop through the OCR result 
            for i, word in enumerate(ocr_result['text']):               
                if word.strip().lower() == ent.text.lower():
                        print(f'word.strip().lower() {word.strip().lower()} and {ent.text.lower()}')
                        # Get the bounding box for the word (x, y, width, height)
                        x, y, w, h = ocr_result['left'][i], ocr_result['top'][i], ocr_result['width'][i], ocr_result['height'][i]                        
                        # Draw a black rectangle over the detected word (redaction)
                        draw.rectangle([x, y, x + w, y + h], fill="black")
    
    # Save the redacted image separately in the specified output folder
    redacted_image_path = os.path.join(output_folder, f"redacted_page_{page_number}_image_{img_index}.png")
    image.save(redacted_image_path)
    return redacted_image_path

def process_images(page, output_folder, page_number):
    images = page.get_images(full=True)    
    for img_index, img in enumerate(images):
        xref = img[0]  # Reference to the image (image xref)
        base_image = page.parent.extract_image(xref)
        image_bytes = base_image["image"]
        image_ext = base_image["ext"]
        
        # Open the image using Pillow
        image = Image.open(io.BytesIO(image_bytes))
        
        # Redact PII in the image
        redacted_image_path = redact_pii_image(image, page_number, img_index, output_folder)
        
        # Save the redacted image to bytes
        img_stream = io.BytesIO()
        redacted_image = Image.open(redacted_image_path)
        redacted_image.save(img_stream, format=image_ext.upper())  
        img_stream.seek(0)        
        page.replace_image(xref,filename=None, pixmap=None, stream=img_stream)  


def process_and_redact_pii(input_pdf, output_pdf, output_folder):
   #Open the pdf using fitz--
    doc = fitz.open(input_pdf)
    print(f"No of pages in the PDF is {len(doc)}")
    
    for page_num in range(len(doc)):
        print(f"Processing PII Redact for the Page Number : {page_num}")
        page = doc[page_num]      
      
        redact_pii_text(page)     
     
        process_images(page, output_folder, page_num)
    
    # Save the redacted PDF
    doc.save(output_pdf)

# Run the process
input_pdf = "sample1.pdf"
output_pdf = "output-7.pdf"
output_folder = "output_images1"  # Folder to store the redacted images

# Create output folder if it doesn't exist
os.makedirs(output_folder, exist_ok=True)

process_and_redact_pii(input_pdf, output_pdf, output_folder)
