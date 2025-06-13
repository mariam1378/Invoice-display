import streamlit as st
import pdfplumber
import re
import unicodedata
from io import BytesIO

# --- Helper Functions (same as before, simplified here) ---
def normalize_arabic(text):
    return re.sub(r'[\u0617-\u061A\u064B-\u0652]', '', unicodedata.normalize("NFKD", text))

def reverse_arabic_words(text):
    def reverse_if_arabic(word):
        return word[::-1] if all('\u0600' <= ch <= '\u06FF' for ch in word) else word
    return ' '.join(reverse_if_arabic(w) for w in text.split())

def detect_currency(text):
    if not text:
        return None
    text = normalize_arabic(text)
    text = reverse_arabic_words(text.lower())
    currency_patterns = {
        'AED': [r'درهم', r'بالدرهم', r'\buae\b', r'dubai', r'emirates', r'aed', r'د\.إ'],
        'USD': [r'usd', r'\$', r'usa'],
        'EUR': [r'euros?', r'€', r'\beu\b'],
        'INR': [r'inr', r'₹', r'rupees?'],
        'GBP': [r'gbp', r'£', r'pounds?'],
        'SAR': [r'sar', r'﷼', r'saudi']
    }
    for currency, patterns in currency_patterns.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return currency
    return None

def is_total_keyword(text):
    keywords = ['total payable', 'amount due', 'grand total', 'invoice total', 'total']
    return any(k in text.lower() for k in keywords)

def extract_number(text):
    match = re.search(r'\d[\d,]*(\.\d{1,2})?', text.replace(" ", ""))
    return match.group(0) if match else None

def extract_invoice_data(file):
    full_text = ""
    totals = []
    with pdfplumber.open(file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                full_text += text + "\n"
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    cells = [str(c or '').strip() for c in row]
                    for i, cell in enumerate(cells):
                        if is_total_keyword(cell):
                            # Look right
                            for j in range(i+1, len(cells)):
                                amount = extract_number(cells[j])
                                if amount:
                                    totals.append((amount, page_num+1, cell))
                                    break
    currency = detect_currency(full_text)
    totals = sorted(totals, key=lambda x: float(x[0].replace(',', '')), reverse=True)
    return totals[0] if totals else None, currency

# --- Streamlit UI ---
st.title("🧾 Invoice Total Extractor")
st.write("Upload a PDF invoice to extract the **total payable** and **currency**.")

uploaded_file = st.file_uploader("Upload your invoice (PDF only)", type=["pdf"])

if uploaded_file is not None:
    st.info("Processing your file...")
    try:
        total_info, currency = extract_invoice_data(BytesIO(uploaded_file.read()))
        if total_info:
            amount, page, label = total_info
            st.success(f"**Total Amount:** {currency or ''} {amount}")
            st.caption(f"Found on page {page}, labeled: '{label}'")
        else:
            st.warning("No total amount could be found in the document.")
        if not currency:
            st.info("Currency not detected — ensure currency is mentioned in the PDF.")
    except Exception as e:
        st.error(f"❌ Error reading PDF: {e}")
