import re
import spacy
from spacy.tokens import Span
from spacy.language import Language


@Language.component("regex_pii_matcher")
def regex_pii_matcher(doc):
    """
    Identifies PII in the text using regex patterns and assigns custom labels.
    """
    # Define regex patterns for PII
    patterns = [
        (r"\b\d{3}-\d{2}-\d{4}\b", "SSN"),  # Social Security Number
        (r"\b\d{4}-\d{4}-\d{4}-\d{4}\b", "CREDIT_CARD"),  # Credit Card Number
        (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", "EMAIL"),  # Email
        (r"\b\d{10}\b", "PHONE_NUMBER"),  # Phone Number (10 digits)
        (r"\b\d{5}(?:-\d{4})?\b", "ZIP_CODE"),  # ZIP Code (US format)
    ]

    # Create spans for matches
    matches = []
    for pattern, label in patterns:
        for match in re.finditer(pattern, doc.text):
            start_char, end_char = match.span()
            # Use doc.char_span to map character offsets to token indices
            span = doc.char_span(start_char, end_char, label=label)
            if span:  # Ensure span is valid (not crossing token boundaries)
                matches.append(span)

    # Attach matches as entities
    doc.ents = list(doc.ents) + matches
    return doc


# Load a SpaCy blank model
nlp = spacy.blank("en")

# Register and add the custom regex PII matcher to the pipeline
nlp.add_pipe("regex_pii_matcher", last=True)

# Test text containing PII
text = """
John's SSN is 123-45-6789. His email is john.doe@example.com.
He lives in ZIP code 90210 and his credit card number is 1234-5678-9101-1121.
You can reach him at 5551234567.
"""

# Process the text with the SpaCy pipeline
doc = nlp(text)

# Print the identified PII
print("PII Found:")
for ent in doc.ents:
    print(f"Text: {ent.text}, Label: {ent.label_}")

# Optional: Save results to a file
with open("pii_results.txt", "w") as file:
    for ent in doc.ents:
        file.write(f"Text: {ent.text}, Label: {ent.label_}\n")
