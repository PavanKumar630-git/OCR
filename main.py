from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
import requests
import random
import re
from typing import Dict, Any

app = FastAPI()

OCR_API_URL = "https://api8.ocr.space/parse/image"
OCR_API_KEYS = [
    "donotstealthiskey_ip1",
    "K86525687388957"
]

# Language to OCR language code mapping
LANGUAGE_MAPPING = {
    "english": "eng",
    "hindi": "hin",
    "telugu": "tel",
    "kannada": "kan",
    "tamil": "tam",
    "malayalam": "mal"
}

import re
from typing import Dict, Any

def extract_document_info(ocr_data: Dict[str, Any], document_type: str) -> Dict[str, Any]:
    parsed_text = ocr_data.get("ParsedResults", [{}])[0].get("ParsedText", "")
    lines = [line.strip() for line in parsed_text.splitlines() if line.strip()]

    result = {
        "name": "",
        "father_name": "",
        "mother_name": "",
        "dob": "",
        "gender": "",
        "address": "",
        "document_number": "",
        "document_type": document_type.upper(),
        # "mobile": ""
    }

    # Common patterns
    patterns = {
        "aadhaar": re.compile(r'\b[2-9]\d{3}[ ]?\d{4}[ ]?\d{4}\b'),
        "pan": re.compile(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b'),
        "voter": re.compile(r'\b[A-Z]{2,3}[0-9]{7}\b'),
        "dob": re.compile(r'\b(\d{2}[/-]\d{2}[/-]\d{4}|\d{4}[/-]\d{2}[/-]\d{2})\b'),
        "gender": re.compile(r'\b(FEMALE|MALE|F|M|स्त्री|पुरुष|స్త్రీ|పురుషుడు|பெண்|ஆண்|ಹೆಣ್ಣು|ಗಂಡು|സ്ത്രീ|പുരുഷൻ)\b', re.IGNORECASE),
        # "mobile": re.compile(r'(\+91[\-\s]?|0)?[6-9]\d{9}\b'),
        "pincode": re.compile(r'\b[1-9][0-9]{5}\b')
    }

    # Document-specific keywords
    doc_keywords = {
        "AADHAAR": {
            "en": ["aadhaar", "uidai", "vid", "unique identification", "govt of india", "government of india"],
            "hi": ["आधार", "यूआईडीएआई", "वीआईडी"],
            "te": ["ఆధార్", "యుడై", "విడి"],
            "ta": ["ஆதார்", "யுஐடிஏஐ", "விஐடி"],
            "kn": ["ಆಧಾರ್", "ಯುಐಡಿಎಐ", "ವಿಐಡಿ"],
            "ml": ["ആധാർ", "യുഐഡിഐ", "വിഐഡി"]
        },
        "PAN": {
            "en": ["income tax", "permanent account", "govt of india"],
        },
        "VOTERID": {
            "en": ["election commission", "epic", "voter", "elector"]
        }
    }

    name_patterns = {
        "en": re.compile(r'^[A-Z][a-z]+(?: [A-Z][a-z]+)*$'),
        "hi": re.compile(r'^[\u0900-\u097F ]+$'),
        "te": re.compile(r'^[\u0C00-\u0C7F ]+$'),
        "ta": re.compile(r'^[\u0B80-\u0BFF ]+$'),
        "kn": re.compile(r'^[\u0C80-\u0CFF ]+$'),
        "ml": re.compile(r'^[\u0D00-\u0D7F ]+$')
    }

    relation_keywords = {
        "father": {
            "en": ["father", "s/o", "son of", "d/o", "daughter of"],
            "hi": ["पिता", "पुत्र", "पुत्री", "श्री"],
            "te": ["తండ్రి", "కొడుకు", "కుమార్తె"]
        },
        "mother": {
            "en": ["mother", "w/o", "wife of"],
            "hi": ["माता", "पत्नी"],
            "te": ["తల్లి", "భార్య"]
        }
    }

    doc_language = "en"
    for lang, keywords in doc_keywords[document_type.upper()].items():
        if any(keyword.lower() in parsed_text.lower() for keyword in keywords):
            doc_language = lang
            break

    # Document Number
    if document_type.upper() == "AADHAAR":
        if m := patterns["aadhaar"].search(parsed_text):
            result["document_number"] = m.group().strip()

        # Extract DOB and Gender
        for i, line in enumerate(lines):
            if "dob" in line.lower() or patterns["dob"].search(line):
                if patterns["dob"].search(line):
                    result["dob"] = patterns["dob"].search(line).group()
                # Try to get name from previous 1-2 lines
                for j in range(i-2, i):
                    if j >= 0 and not any(x in lines[j].lower() for x in ["dob", "enrol", "government", "authority", "your aadhaar", "female", "male", "uidai"]):
                        result["name"] = lines[j].strip()
                        break
            # Gender
            if "female" in line.lower():
                result["gender"] = "FEMALE"
            elif "male" in line.lower():
                result["gender"] = "MALE"

        # Extract address from lines before Aadhaar number
        if result["document_number"]:
            aadhaar_index = parsed_text.find(result["document_number"])
            address_block = parsed_text[:aadhaar_index]
            address_lines = []
            for line in address_block.splitlines():
                if not any(x in line.lower() for x in ["dob", "name", "enrol", "uidai", "aadhar", "gov", "authority", "female", "male"]) and not patterns["aadhaar"].search(line):
                    address_lines.append(line.strip())
            if address_lines:
                result["address"] = "\n".join([l for l in address_lines if l])
    elif document_type.upper() == "PAN":
        if m := patterns["pan"].search(parsed_text):
            result["document_number"] = m.group().strip()

        for i, line in enumerate(lines):
            if "name" in line.lower() and i + 1 < len(lines):
                result["name"] = lines[i + 1].strip()
            elif "father" in line.lower() and i + 1 < len(lines):
                result["father_name"] = lines[i + 1].strip()
            elif "date of birth" in line.lower() and i + 1 < len(lines):
                dob_match = patterns["dob"].search(lines[i + 1])
                if dob_match:
                    result["dob"] = dob_match.group()
    elif document_type.upper() == "VOTERID":
        if m := patterns["voter"].search(parsed_text):
            result["document_number"] = m.group().strip()

    # Filter lines to ignore headers
    header_phrases = [
        "governmentof india","government of india", "unique identification", "uidai","Permanent Account Number Card",
        "income tax", "election commission", "help@uidai.gov.in", "www.uidai.gov.in"
    ]
    lines_filtered = [
        line for line in lines
        if not any(header.lower() in line.lower() for header in header_phrases)
    ]

    # Extract names
    name_candidates = []
    relationship_candidates = []
    for line in lines_filtered:
        if (patterns["aadhaar"].search(line) or
            patterns["pan"].search(line) or
            patterns["voter"].search(line) or
            patterns["dob"].search(line) 
            # or
            # patterns["mobile"].search(line)
            ):
            continue
        if name_patterns[doc_language].match(line):
            name_candidates.append(line.strip())
        elif len(line.split()) <= 4 and not any(char.isdigit() for char in line):
            relationship_candidates.append(line.strip())

    # Assign names based on logic
    if name_candidates:
        result["name"] = name_candidates[0]
        if len(name_candidates) > 1:
            result["father_name"] = name_candidates[1]
        if len(name_candidates) > 2:
            result["mother_name"] = name_candidates[2]

    if not result["name"] and relationship_candidates:
        result["name"] = relationship_candidates[0]
        if len(relationship_candidates) > 1:
            result["father_name"] = relationship_candidates[1]
        if len(relationship_candidates) > 2:
            result["mother_name"] = relationship_candidates[2]

    # DOB
    if m := patterns["dob"].search(parsed_text):
        result["dob"] = m.group()

    # Gender
    if g := patterns["gender"].search(parsed_text):
        gender = g.group().upper()
        if gender in ["F", "FEMALE", "स्त्री", "స్త్రీ", "பெண்", "ಹೆಣ್ಣು", "സ്ത്രീ"]:
            result["gender"] = "FEMALE"
        elif gender in ["M", "MALE", "पुरुष", "పురుషుడు", "ஆண்", "ಗಂಡು", "പുരുഷൻ"]:
            result["gender"] = "MALE"

    # Mobile
    # if m := patterns["mobile"].search(parsed_text):
    #     result["mobile"] = m.group()

    # Address
    address_keywords = {
        "en": ["address", "residence"],
        "hi": ["पता", "निवास"],
        "te": ["చిరునామా", "నివాసం"]
    }
    collecting_address = False
    address_lines = []
    for line in lines:
        line_lower = line.lower()
        if any(keyword in line_lower for keyword in address_keywords.get(doc_language, [])):
            collecting_address = True
            continue
        if collecting_address:
            if patterns["pincode"].search(line):
                address_lines.append(line)
                break
            if line:
                address_lines.append(line)

    if address_lines:
        result["address"] = "\n".join(address_lines)

    return result

@app.post("/upload/")
async def upload_file(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    language: str = Form("english")
):
    try:
        # Validate language input
        if language.lower() not in LANGUAGE_MAPPING:
            return JSONResponse(
                content={"error": f"Unsupported language. Supported languages are: {', '.join(LANGUAGE_MAPPING.keys())}"},
                status_code=400
            )

        # Validate document type
        if document_type.upper() not in ["AADHAAR", "PAN", "VOTERID"]:
            return JSONResponse(
                content={"error": "Unsupported document type. Supported types are: AADHAAR, PAN, VOTERID"},
                status_code=400
            )

        # Read file content
        file_bytes = await file.read()
        api_key = random.choice(OCR_API_KEYS)

        # Prepare the multipart/form-data
        files = {
            'file': (file.filename, file_bytes, file.content_type),
        }

        # OCR form data
        data = {
            'language': LANGUAGE_MAPPING[language.lower()],  # Use selected language
            'isOverlayRequired': 'true',
            'FileType': '.Auto',
            'IsCreateSearchablePDF': 'false',
            'isSearchablePdfHideTextLayer': 'true',
            'detectOrientation': 'false',
            'isTable': 'false',
            'scale': 'true',
            'OCREngine': '1',
            'detectCheckbox': 'false',
            'checkboxTemplate': '0',
        }

        # Headers
        headers = {
            'apikey': api_key,
        }

        # Send to OCR API
        response = requests.post(OCR_API_URL, headers=headers, files=files, data=data)
        json_data = response.json()
        
        # Check for OCR errors
        if response.status_code != 200 or json_data.get("IsErroredOnProcessing", False):
            error_message = json_data.get("ErrorMessage", ["OCR processing failed"])[0]
            return JSONResponse(
                content={"error": f"OCR processing error: {error_message}"},
                status_code=response.status_code
            )

        result = extract_document_info(json_data, document_type)
        parsed_text = json_data.get("ParsedResults", [{}])[0].get("ParsedText", "")
        
        return {
            "ocr_data": parsed_text,
            "extracted_data": result,
            # "document_language": language.lower(),
            # "document_type": document_type.upper()
        }
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
