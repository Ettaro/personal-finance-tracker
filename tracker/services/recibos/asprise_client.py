import os
from decimal import Decimal

import requests

from tracker.services.category_classifier import normalize_category_name


ASPRISE_ENDPOINT = 'https://ocr.asprise.com/api/v1/receipt'


def _format_amount(value):
    if value is None:
        return ''

    try:
        amount = Decimal(str(value))
    except Exception:
        return ''

    return f'{amount:.2f}'.replace('.', ',')


def _suggest_category_from_receipt(receipt):
    text = ' '.join(
        str(value or '')
        for value in (
            receipt.get('merchant_name'),
            receipt.get('ocr_text'),
            receipt.get('payment_method'),
        )
    ).lower()

    if any(term in text for term in (
        'restaurant',
        'restaurante',
        'miyagi',
        'food',
        'mercado',
        'supermercado',
        'padaria',
        'lanchonete',
        'sushi',
    )):
        return 'Food'

    if any(term in text for term in ('uber', '99', 'fuel', 'gasolina', 'posto')):
        return 'Transport'

    if any(term in text for term in ('netflix', 'spotify', 'prime', 'youtube')):
        return 'Subscriptions'

    if any(term in text for term in ('cinema', 'show', 'games', 'steam')):
        return 'Leisure'

    return ''


def map_asprise_receipt(receipt):
    ocr_text = receipt.get('ocr_text') or ''
    return {
        'description': receipt.get('merchant_name') or '',
        'amount': _format_amount(receipt.get('total')),
        'date': receipt.get('date') or '',
        'type': 'despesa',
        'suggested_category': normalize_category_name(_suggest_category_from_receipt(receipt)),
        'asprise_metadata': {
            'provider_status': 'success',
            'message': 'Receipt data was extracted with Asprise OCR.',
            'ocr_confidence': receipt.get('ocr_confidence'),
            'currency': receipt.get('currency'),
            'payment_method': receipt.get('payment_method'),
            'credit_card_type': receipt.get('credit_card_type'),
        },
        'ocr_text': ocr_text,
    }


def extract_receipt_with_asprise(image_file):
    api_key = os.getenv('ASPRISE_API_KEY', 'TEST')

    image_file.seek(0)
    response = requests.post(
        ASPRISE_ENDPOINT,
        data={
            'api_key': api_key,
            'recognizer': os.getenv('ASPRISE_RECOGNIZER', 'auto'),
            'ref_no': 'financial_tracker_receipt',
        },
        files={'file': ('receipt.png', image_file, 'image/png')},
        timeout=45,
    )
    response.raise_for_status()

    payload = response.json()
    receipts = payload.get('receipts') or []
    if not payload.get('success') or not receipts:
        return None

    return {
        'payload': payload,
        'parsed_data': map_asprise_receipt(receipts[0]),
    }
