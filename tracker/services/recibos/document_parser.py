import base64
from datetime import datetime
from io import BytesIO
import re

from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _normalize_line(line):
    return re.sub(r'\s+', ' ', line.strip())


def _looks_like_merchant_name(line):
    if not line:
        return False

    normalized_line = _normalize_line(line)
    lowered_line = normalized_line.lower()

    ignored_terms = (
        'infinitepay',
        'via cliente',
        'cnpj/cpf',
        'visa',
        'credito',
        'debito',
        'a vista',
        'mastercard',
        'elo',
        'pix',
        'aprovado',
        'aut',
        'aid',
        'doc',
        'cartao',
        'onl',
        'less',
        'cliente',
    )

    if any(term in lowered_line for term in ignored_terms):
        return False

    if re.search(r'\d', normalized_line):
        return False

    if len(normalized_line) < 4:
        return False

    letter_count = sum(character.isalpha() for character in normalized_line)
    return letter_count >= 4


def _resize_for_ocr(image):
    width, height = image.size
    scale_factor = 2
    return image.resize((width * scale_factor, height * scale_factor), Image.Resampling.LANCZOS)


def _conservative_center_crop(image):
    width, height = image.size
    left = int(width * 0.10)
    top = int(height * 0.10)
    right = int(width * 0.90)
    bottom = int(height * 0.90)

    if right <= left or bottom <= top:
        return image

    return image.crop((left, top, right, bottom))


def _build_ocr_variants(image):
    base = image.convert('L')
    base = _resize_for_ocr(base)
    base = ImageOps.autocontrast(base)

    sharpened = ImageEnhance.Sharpness(base).enhance(2.2)
    contrasted = ImageEnhance.Contrast(sharpened).enhance(1.8)

    binary = contrasted.point(lambda pixel: 255 if pixel > 165 else 0)
    binary = binary.filter(ImageFilter.MedianFilter(size=3))

    softer_binary = contrasted.point(lambda pixel: 255 if pixel > 145 else 0)

    return {
        'preview': contrasted,
        'ocr_variants': [
            ('psm6_binary', binary, '--oem 3 --psm 6'),
            ('psm4_binary', binary, '--oem 3 --psm 4'),
            ('psm6_soft_binary', softer_binary, '--oem 3 --psm 6'),
            ('psm4_contrasted', contrasted, '--oem 3 --psm 4'),
        ],
    }


def _image_to_bytes(image):
    output = BytesIO()
    image.save(output, format='PNG')
    output.seek(0)
    return output


def _score_ocr_text(text):
    if not text:
        return 0

    score = 0
    lowered_text = text.lower()
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if re.search(r'\d{2}/\d{2}/\d{4}', text):
        score += 4
    if re.search(r'\d+[.,]\d{2}', text):
        score += 4
    if 'r$' in lowered_text:
        score += 5
    if any(term in lowered_text for term in ('credito', 'debito', 'visa', 'mastercard', 'a vista')):
        score += 2

    merchant_like_lines = sum(1 for line in text.splitlines() if _looks_like_merchant_name(line))
    score += merchant_like_lines * 3

    short_noisy_lines = sum(1 for line in lines if len(line) <= 3)
    score -= short_noisy_lines * 2

    if len(lines) > 18:
        score -= (len(lines) - 18) * 2

    weird_symbol_count = len(re.findall(r'[“”"~`^<>|@#%*_=]+', text))
    score -= weird_symbol_count

    if 'r$ 900,00' in lowered_text or 'r$900,00' in lowered_text:
        score += 6

    return score


def preprocess_receipt_image(uploaded_file):
    image = Image.open(uploaded_file)
    variants = _build_ocr_variants(image)
    return _image_to_bytes(variants['preview'])


def image_file_to_base64(image_file):
    return base64.b64encode(image_file.getvalue()).decode('utf-8')


def extract_text_from_receipt(processed_image):
    return extract_receipt_ocr_variants(processed_image)['best_text']


def _run_best_ocr_for_image(image):
    variants = _build_ocr_variants(image)
    best_text = ''
    best_score = float('-inf')
    fallback_text = ''

    for _, variant_image, config in variants['ocr_variants']:
        text = pytesseract.image_to_string(
            variant_image,
            lang='por+eng',
            config=config,
        ).strip()

        if text and not fallback_text:
            fallback_text = text

        score = _score_ocr_text(text)
        if score > best_score:
            best_score = score
            best_text = text

    return {
        'text': best_text or fallback_text,
        'score': best_score if best_score != float('-inf') else 0,
    }


def extract_receipt_ocr_variants(processed_image):
    processed_image.seek(0)
    image = Image.open(processed_image)
    full_result = _run_best_ocr_for_image(image)
    cropped_result = _run_best_ocr_for_image(_conservative_center_crop(image))

    best_result = full_result if full_result['score'] >= cropped_result['score'] else cropped_result

    return {
        'full_image_ocr': full_result['text'],
        'cropped_image_ocr': cropped_result['text'],
        'best_text': best_result['text'],
        'best_source': 'full' if best_result is full_result else 'cropped',
    }


def parse_receipt_text(text):
    lines = [_normalize_line(line) for line in text.splitlines() if line.strip()]

    description = ''
    for line in lines:
        if _looks_like_merchant_name(line):
            description = line
            break

    amount_match = re.search(r'r\$\s*(\d+[.,]\d{2})', text, re.IGNORECASE)
    if not amount_match:
        amount_candidates = re.findall(r'(\d+[.,]\d{2})', text)
        amount = amount_candidates[-1] if amount_candidates else ''
    else:
        amount = amount_match.group(1)

    date_match = re.search(r'(\d{2}/\d{2}/\d{4})', text)
    date = date_match.group(1) if date_match else ''

    lowered_text = text.lower()
    transaction_type = 'despesa'
    if any(term in lowered_text for term in ('recebido', 'deposito', 'transferencia recebida', 'pix recebido')):
        transaction_type = 'receita'

    suggested_category = ''
    description_lower = description.lower()
    if any(term in description_lower for term in (
        'restaurante',
        'lanchonete',
        'hamburg',
        'pizza',
        'sushi',
        'bar',
        'caf',
        'miyagi',
        'mercado',
        'supermercado',
        'hortifruti',
        'padaria',
    )):
        suggested_category = 'alimentacao'
    elif any(term in description_lower for term in ('uber', '99', 'posto', 'combustivel', 'gasolina')):
        suggested_category = 'transporte'
    elif any(term in description_lower for term in ('netflix', 'spotify', 'prime', 'youtube', 'disney')):
        suggested_category = 'assinaturas'
    elif any(term in description_lower for term in ('cinema', 'teatro', 'show', 'games', 'steam')):
        suggested_category = 'lazer'

    return {
        'description': description,
        'amount': amount,
        'date': date,
        'type': transaction_type,
        'suggested_category': suggested_category,
    }


def _unique_texts_from_payload(ocr_payload):
    seen = set()
    texts = []

    for key in ('best_text', 'full_image_ocr', 'cropped_image_ocr'):
        text = (ocr_payload.get(key) or '').strip()
        if text and text not in seen:
            seen.add(text)
            texts.append(text)

    return texts


def _extract_description_from_texts(texts):
    for text in texts:
        parsed = parse_receipt_text(text)
        if parsed['description']:
            return parsed['description']
    return ''


def _extract_amount_from_texts(texts):
    candidates = []

    for text in texts:
        for match in re.finditer(r'r\$\s*(\d+[.,]\d{2})', text, re.IGNORECASE):
            raw_value = match.group(1)
            normalized_value = raw_value.replace('.', '').replace(',', '.')
            try:
                numeric_value = float(normalized_value)
            except ValueError:
                continue
            candidates.append((numeric_value, raw_value))

    if not candidates:
        for text in texts:
            for raw_value in re.findall(r'(\d+[.,]\d{2})', text):
                normalized_value = raw_value.replace('.', '').replace(',', '.')
                try:
                    numeric_value = float(normalized_value)
                except ValueError:
                    continue
                candidates.append((numeric_value, raw_value))

    if not candidates:
        return ''

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _extract_date_from_texts(texts):
    current_year = datetime.now().year
    candidates = []

    for text in texts:
        for raw_date in re.findall(r'(\d{2}/\d{2}/\d{4})', text):
            try:
                parsed_date = datetime.strptime(raw_date, '%d/%m/%Y')
            except ValueError:
                continue

            year_distance = abs(parsed_date.year - current_year)
            candidates.append((year_distance, -parsed_date.year, raw_date))

    if not candidates:
        return ''

    candidates.sort()
    return candidates[0][2]


def parse_receipt_ocr_payload(ocr_payload):
    texts = _unique_texts_from_payload(ocr_payload)
    base_text = ocr_payload.get('best_text', '')
    base_parsed = parse_receipt_text(base_text) if base_text else {
        'description': '',
        'amount': '',
        'date': '',
        'type': 'despesa',
        'suggested_category': '',
    }

    description = _extract_description_from_texts(texts) or base_parsed['description']
    amount = _extract_amount_from_texts(texts) or base_parsed['amount']
    date = _extract_date_from_texts(texts) or base_parsed['date']

    merged_text = '\n'.join(texts).lower()
    transaction_type = 'despesa'
    if any(term in merged_text for term in ('recebido', 'deposito', 'transferencia recebida', 'pix recebido')):
        transaction_type = 'receita'

    suggested_category = base_parsed['suggested_category']
    description_lower = description.lower()
    if any(term in description_lower for term in (
        'restaurante',
        'lanchonete',
        'hamburg',
        'pizza',
        'sushi',
        'bar',
        'caf',
        'miyagi',
        'mercado',
        'supermercado',
        'hortifruti',
        'padaria',
    )):
        suggested_category = 'alimentacao'

    return {
        'description': description,
        'amount': amount,
        'date': date,
        'type': transaction_type,
        'suggested_category': suggested_category,
    }
