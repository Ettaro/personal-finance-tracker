import json
import os
from urllib import error, request


def _build_fallback_result(parsed_data):
    return {
        'description': parsed_data.get('description', ''),
        'amount': parsed_data.get('amount', ''),
        'date': parsed_data.get('date', ''),
        'type': parsed_data.get('type', 'despesa'),
        'suggested_category': parsed_data.get('suggested_category', ''),
        'ai_metadata': {
            'used': False,
            'provider_status': 'fallback',
            'message': 'The interpretation used the local system rules.',
        },
    }


def _extract_json_object(content):
    content = (content or '').strip()
    if not content:
        return {}

    start = content.find('{')
    end = content.rfind('}')
    if start == -1 or end == -1 or end < start:
        return {}

    try:
        return json.loads(content[start:end + 1])
    except json.JSONDecodeError:
        return {}


def _clean_ai_response(ai_data, parsed_data, categories):
    valid_types = {'receita', 'despesa'}
    available_category_names = {category.name.lower(): category.name for category in categories}

    cleaned = _build_fallback_result(parsed_data)
    cleaned['ai_metadata'] = {
        'used': True,
        'provider_status': 'ok',
        'message': ai_data.get('reasoning', '').strip() or 'AI refined the fields extracted from the receipt.',
    }

    for field in ('description', 'amount', 'date'):
        candidate = (ai_data.get(field) or '').strip()
        if candidate:
            cleaned[field] = candidate

    transaction_type = (ai_data.get('transaction_type') or '').strip().lower()
    if transaction_type in valid_types:
        cleaned['type'] = transaction_type

    suggested_category = (ai_data.get('suggested_category') or '').strip()
    if suggested_category and suggested_category.lower() in available_category_names:
        cleaned['suggested_category'] = available_category_names[suggested_category.lower()]

    return cleaned


def map_receipt_fields_with_ai(ocr_payload, parsed_data, categories):
    api_key = os.getenv('RECEIPT_AI_API_KEY')
    model = os.getenv('RECEIPT_AI_MODEL')
    base_url = os.getenv('RECEIPT_AI_BASE_URL', 'https://api.openai.com/v1/chat/completions')

    fallback = _build_fallback_result(parsed_data)

    if not api_key or not model:
        fallback['ai_metadata'] = {
            'used': False,
            'provider_status': 'unconfigured',
            'message': 'Configure RECEIPT_AI_API_KEY and RECEIPT_AI_MODEL to enable AI interpretation.',
        }
        return fallback

    category_names = [category.name for category in categories]

    system_prompt = (
        'You interpret OCR text extracted from receipts and payment slips. '
        'Use only the provided text and the available categories. '
        'Do not invent categories that do not exist. '
        'Reply with valid JSON only.'
    )
    user_prompt = {
        'ocr_sources': {
            'best_text': ocr_payload.get('best_text', ''),
            'best_source': ocr_payload.get('best_source', ''),
            'full_image_ocr': ocr_payload.get('full_image_ocr', ''),
            'cropped_image_ocr': ocr_payload.get('cropped_image_ocr', ''),
        },
        'current_extraction': {
            'description': parsed_data.get('description', ''),
            'amount': parsed_data.get('amount', ''),
            'date': parsed_data.get('date', ''),
            'type': parsed_data.get('type', 'despesa'),
            'suggested_category': parsed_data.get('suggested_category', ''),
        },
        'available_categories': category_names,
        'expected_response_schema': {
            'description': 'string',
            'amount': 'string',
            'date': 'string',
            'transaction_type': 'receita or despesa',
            'suggested_category': 'one category from available_categories or an empty string',
            'reasoning': 'brief explanation of the suggestion',
        },
    }

    payload = {
        'model': model,
        'response_format': {'type': 'json_object'},
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': json.dumps(user_prompt, ensure_ascii=False)},
        ],
        'temperature': 0.1,
    }

    http_request = request.Request(
        base_url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with request.urlopen(http_request, timeout=30) as response:
            response_data = json.loads(response.read().decode('utf-8'))
    except (error.URLError, TimeoutError, json.JSONDecodeError):
        fallback['ai_metadata'] = {
            'used': False,
            'provider_status': 'error',
            'message': 'AI did not respond as expected. The system used local rules to fill the fields.',
        }
        return fallback

    message_content = (
        response_data.get('choices', [{}])[0]
        .get('message', {})
        .get('content', '')
    )
    ai_data = _extract_json_object(message_content)
    if not ai_data:
        fallback['ai_metadata'] = {
            'used': False,
            'provider_status': 'invalid_response',
            'message': 'The AI response did not return valid JSON. The system used local rules instead.',
        }
        return fallback

    return _clean_ai_response(ai_data, parsed_data, categories)
