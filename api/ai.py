import base64
import json
import re
from io import BytesIO

import requests
from django.conf import settings
from PIL import Image


def _clamp(value):
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = 70
    return min(92, max(55, number))


def _parse_json(text):
    cleaned = re.sub(r'^```(?:json)?\s*', '', (text or '').strip(), flags=re.I)
    cleaned = re.sub(r'```$', '', cleaned).strip()
    start = cleaned.find('{')
    end = cleaned.rfind('}')
    if start < 0 or end < 0:
        raise ValueError('The AI did not return valid predictions.')
    return json.loads(cleaned[start:end + 1])


def prepare_image(raw_bytes):
    image = Image.open(BytesIO(raw_bytes))
    if image.mode in ('RGBA', 'P', 'LA'):
        image = image.convert('RGB')
    elif image.mode != 'RGB':
        image = image.convert('RGB')
    image.thumbnail((1280, 1280))
    buffer = BytesIO()
    image.save(buffer, format='JPEG', quality=72, optimize=True)
    return base64.b64encode(buffer.getvalue()).decode(), 'image/jpeg'


def _football_prompt():
    return '''You are a virtual football analyst. The image is a SportyBet Instant Football / VGames ticket screenshot.
Read every visible fixture. For each match return a 1X2 pick.
Rules:
- Use the exact team names from the screenshot.
- pick must be "{Home or Away team} Win" or "Draw".
- confidence is 55-92. Shorter odds / stronger implied probability = higher confidence.
- Only include matches you can actually see.
- Entertainment analysis only, not financial advice.
Return JSON only: {"predictions":[{"home":"Burnley","away":"Liverpool","pick":"Liverpool Win","confidence":82}]}'''


def _bottle_prompt():
    return '''You are a Spin the Bottle / UP-DOWN virtuals analyst. The image is a betting screenshot of that game.
Read every visible spin, round, or UP/DOWN market.
Rules:
- pick must be exactly "UP" or "DOWN".
- round should be a short label like "Round 1" or the market name on screen.
- confidence is 55-92 from visible odds, streak, or implied probability.
- Only include markets you can actually see.
- Entertainment analysis only, not financial advice.
Return JSON only: {"predictions":[{"round":"Round 1","pick":"UP","confidence":78}]}'''


def _normalize_football(rows):
    picks = []
    for item in rows or []:
        if not isinstance(item, dict):
            continue
        home = str(item.get('home') or '').strip()
        away = str(item.get('away') or '').strip()
        pick = str(item.get('pick') or '').strip()
        if home and away and pick:
            picks.append({'home': home, 'away': away, 'pick': pick, 'confidence': _clamp(item.get('confidence'))})
        if len(picks) >= 8:
            break
    return picks


def _normalize_bottle(rows):
    picks = []
    for index, item in enumerate(rows or []):
        if not isinstance(item, dict):
            continue
        pick = str(item.get('pick') or '').strip().upper()
        if pick in ('UP', 'DOWN'):
            picks.append({
                'round': str(item.get('round') or f'Round {index + 1}').strip(),
                'pick': pick,
                'confidence': _clamp(item.get('confidence')),
            })
        if len(picks) >= 8:
            break
    return picks


def _shape(game, parsed):
    rows = parsed.get('predictions') if isinstance(parsed, dict) else []
    if game == 'football':
        predictions = _normalize_football(rows)
        if not predictions:
            raise ValueError((parsed.get('error') if isinstance(parsed, dict) else None) or 'No football fixtures were detected in that screenshot.')
        return {'game': game, 'predictions': predictions}
    predictions = _normalize_bottle(rows)
    if not predictions:
        raise ValueError((parsed.get('error') if isinstance(parsed, dict) else None) or 'No UP/DOWN markets were detected in that screenshot.')
    return {'game': game, 'predictions': predictions}


def _openai(image_b64, mime, game):
    key = settings.OPENAI_API_KEY
    if not key:
        raise ValueError('missing')
    response = requests.post(
        'https://api.openai.com/v1/chat/completions',
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        json={
            'model': settings.OPENAI_MODEL,
            'temperature': 0.2,
            'response_format': {'type': 'json_object'},
            'messages': [
                {'role': 'system', 'content': _football_prompt() if game == 'football' else _bottle_prompt()},
                {'role': 'user', 'content': [
                    {'type': 'text', 'text': 'Analyze this screenshot and return JSON predictions only.'},
                    {'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{image_b64}'}},
                ]},
            ],
        },
        timeout=(10, 60),
    )
    payload = response.json()
    if not response.ok:
        raise ValueError(payload.get('error', {}).get('message') or 'OpenAI request failed.')
    content = payload.get('choices', [{}])[0].get('message', {}).get('content') or ''
    return _shape(game, _parse_json(content))


def _gemini(image_b64, mime, game):
    key = settings.GEMINI_API_KEY
    if not key:
        raise ValueError('missing')
    models = []
    for name in (settings.GEMINI_MODEL, 'gemini-flash-lite-latest', 'gemini-3.5-flash-lite', 'gemini-flash-latest'):
        if name and name not in models:
            models.append(name)
    last_error = 'Gemini request failed.'
    prompt = _football_prompt() if game == 'football' else _bottle_prompt()
    timed_out = False
    for model in models:
        bodies = [
            {
                'systemInstruction': {'parts': [{'text': prompt}]},
                'contents': [{'role': 'user', 'parts': [
                    {'text': 'Analyze this screenshot and return JSON predictions only.'},
                    {'inlineData': {'mimeType': mime, 'data': image_b64}},
                ]}],
                'generationConfig': {
                    'temperature': 0.2,
                    'responseMimeType': 'application/json',
                    'thinkingConfig': {'thinkingBudget': 0},
                },
            },
            {
                'systemInstruction': {'parts': [{'text': prompt}]},
                'contents': [{'role': 'user', 'parts': [
                    {'text': 'Analyze this screenshot and return JSON predictions only.'},
                    {'inlineData': {'mimeType': mime, 'data': image_b64}},
                ]}],
                'generationConfig': {
                    'temperature': 0.2,
                    'responseMimeType': 'application/json',
                },
            },
        ]
        for body in bodies:
            try:
                response = requests.post(
                    f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}',
                    json=body,
                    timeout=(10, 45),
                )
            except requests.Timeout:
                timed_out = True
                last_error = 'The AI timed out reading that screenshot.'
                break
            payload = response.json()
            if not response.ok:
                last_error = payload.get('error', {}).get('message') or last_error
                if response.status_code == 400:
                    continue
                break
            parts = payload.get('candidates', [{}])[0].get('content', {}).get('parts', [])
            text = ''.join(part.get('text') or '' for part in parts)
            if not text:
                last_error = 'The AI returned an empty prediction.'
                break
            return _shape(game, _parse_json(text))
    if timed_out:
        raise ValueError('The AI took too long to read that screenshot. Crop closer to the match list and try again.')
    raise ValueError(last_error)


def analyze_screenshot(raw_bytes, mime, game):
    image_b64, mime = prepare_image(raw_bytes)
    if settings.OPENAI_API_KEY:
        try:
            return _openai(image_b64, mime, game)
        except Exception:
            if settings.GEMINI_API_KEY:
                return _gemini(image_b64, mime, game)
            raise
    if settings.GEMINI_API_KEY:
        return _gemini(image_b64, mime, game)
    raise ValueError('Add OPENAI_API_KEY or GEMINI_API_KEY to .env.local, then restart the Django server.')
