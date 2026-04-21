import os
import json
import base64
import requests
from io import BytesIO
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq

load_dotenv()

app = Flask(__name__)
CORS(app)

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
PLANTNET_API_KEY = os.getenv("PLANTNET_API_KEY", "").strip().strip('"').strip("'")

BOTANIST_SYSTEM_PROMPT = """You are BotanistAI, a seasoned botanist with an insatiable passion for the intricate world of flora. Your role is to serve as a deeply knowledgeable and enthusiastic guide for users who are looking to identify, understand, and care for plants of all species. When a user presents you with a description or an image of a plant, you should approach the task with scientific rigor. You speak with a blend of academic precision and approachable warmth, often sharing fascinating facts about a plant's evolutionary history or its specific ecological niche. Your expertise extends to plant life cycles, blooming patterns, pollination methods, and environmental triggers. You are also tasked with offering practical advice on soil composition, light requirements, and hydration needs. You should be mindful of plant safety, always providing warnings if a species is toxic or invasive. Every response should foster a deeper appreciation for the natural world."""

MONTHS = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
]

# Lightweight curated bloom dataset (northern hemisphere baseline).
BLOOM_DATA_BY_SPECIES = {
    'rosa chinensis': ['April', 'May', 'June', 'July', 'August', 'September'],
    'helianthus annuus': ['June', 'July', 'August', 'September'],
    'solanum lycopersicum': ['June', 'July', 'August', 'September'],
    'lavandula angustifolia': ['June', 'July', 'August'],
    'hibiscus rosa-sinensis': ['May', 'June', 'July', 'August', 'September', 'October'],
    'jasminum officinale': ['June', 'July', 'August', 'September']
}

BLOOM_DATA_BY_GENUS = {
    'rosa': ['April', 'May', 'June', 'July', 'August', 'September'],
    'helianthus': ['June', 'July', 'August', 'September'],
    'solanum': ['June', 'July', 'August', 'September'],
    'lavandula': ['June', 'July', 'August'],
    'hibiscus': ['May', 'June', 'July', 'August', 'September', 'October'],
    'jasminum': ['June', 'July', 'August', 'September']
}


def normalize_species_name(scientific_name):
    """Normalize scientific name to genus + species for lookup."""
    if not scientific_name:
        return ''

    parts = [p for p in scientific_name.strip().split() if p]
    if len(parts) < 2:
        return scientific_name.strip().lower()

    return f"{parts[0].lower()} {parts[1].lower()}"


def shift_months_by_hemisphere(months, offset=6):
    """Shift month list by offset (6 months for opposite hemisphere)."""
    shifted = []
    for month in months:
        if month not in MONTHS:
            continue
        idx = MONTHS.index(month)
        shifted.append(MONTHS[(idx + offset) % 12])
    return shifted


def format_month_range(months):
    """Format months into a readable season range."""
    if not months:
        return 'Unknown'

    if len(months) == 1:
        return months[0]

    return f"{months[0]}-{months[-1]}"


def infer_hemisphere(location):
    """Infer hemisphere from free-text location."""
    if not location:
        return 'northern'

    text = location.lower()
    southern_markers = [
        'southern', 'australia', 'new zealand', 'argentina',
        'chile', 'south africa', 'uruguay', 'paraguay'
    ]
    northern_markers = ['northern', 'usa', 'canada', 'europe', 'india', 'japan']

    if any(marker in text for marker in southern_markers):
        return 'southern'

    if any(marker in text for marker in northern_markers):
        return 'northern'

    return 'northern'


def build_bloom_profile(scientific_name, genus_name, user_location):
    """Build hemisphere-aware bloom payload with species/genus fallback."""
    normalized_species = normalize_species_name(scientific_name)
    normalized_genus = (genus_name or '').strip().lower()

    north_months = BLOOM_DATA_BY_SPECIES.get(normalized_species)
    source = 'species'

    if not north_months and normalized_genus:
        north_months = BLOOM_DATA_BY_GENUS.get(normalized_genus)
        source = 'genus'

    if not north_months:
        return {
            'bloom_season': 'Unknown',
            'bloom_season_by_location': {
                'northern_hemisphere': 'Unknown',
                'southern_hemisphere': 'Unknown',
                'user_location': 'Unknown',
                'note': 'No reliable bloom data available for this species in the current PlantDex dataset.'
            }
        }

    south_months = shift_months_by_hemisphere(north_months, offset=6)
    hemisphere = infer_hemisphere(user_location)
    user_months = north_months if hemisphere == 'northern' else south_months

    return {
        'bloom_season': format_month_range(user_months),
        'bloom_season_by_location': {
            'northern_hemisphere': format_month_range(north_months),
            'southern_hemisphere': format_month_range(south_months),
            'user_location': format_month_range(user_months),
            'note': f"Estimated from {source}-level bloom profile."
        }
    }


@app.route('/api/scan-plant', methods=['POST'])
def scan_plant():
    """Scan plant using PlantNet API only."""
    try:
        data = request.json
        image_base64 = data.get('image')
        user_location = data.get('location', 'Unknown')

        if not image_base64:
            return jsonify({'error': 'No image provided'}), 400

        if not PLANTNET_API_KEY:
            return jsonify({'error': 'PlantNet API key not configured. Add PLANTNET_API_KEY to .env'}), 500

        # Query PlantNet API
        plantnet_results, plantnet_error = query_plantnet(image_base64, user_location)

        if plantnet_error:
            return jsonify({'error': plantnet_error}), 400

        if not plantnet_results:
            return jsonify({'error': 'Could not identify plant. Try a clearer close-up image.'}), 400

        return jsonify(plantnet_results), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def query_plantnet(image_base64, user_location='Unknown'):
    """Query PlantNet API for plant identification."""
    try:
        # Accept both raw base64 and data URLs from the frontend camera capture.
        if ',' in image_base64:
            image_base64 = image_base64.split(',', 1)[1]

        image_data = base64.b64decode(image_base64)
        print(f"Image size: {len(image_data)} bytes")

        params = {
            'api-key': PLANTNET_API_KEY,
            'lang': 'en'
        }

        endpoint = 'https://my-api.plantnet.org/v2/identify/all'
        organ_candidates = ['leaf', 'flower', 'fruit', 'bark', 'auto']

        response = None
        for organ in organ_candidates:
            files = {'images': ('plant.jpg', BytesIO(image_data), 'image/jpeg')}
            response = requests.post(
                endpoint,
                files=files,
                data={'organs': organ},
                params=params,
                timeout=30
            )

            print(f"PlantNet endpoint: {endpoint}")
            print(f"PlantNet organ hint: {organ}")
            print(f"PlantNet response status: {response.status_code}")

            if response.status_code == 200:
                break

            if response.status_code == 404:
                try:
                    error_body = response.json()
                    message = str(error_body.get('message', '')).lower()
                    print(f"PlantNet 404 body: {error_body}")
                    if message == 'species not found':
                        # Retry with another organ hint before giving up.
                        continue
                except Exception:
                    pass

            # For other error codes, stop early and report the real API issue.
            break

        if response is None:
            return None, 'PlantNet request failed (no response).'

        if response.status_code == 404:
            return None, 'PlantNet could not find a species match. Try a clearer close-up of a leaf or flower.'

        if response.status_code != 200:
            print(f"PlantNet API error: {response.status_code}")
            print(f"Response: {response.text}")
            return None, f"PlantNet request failed (HTTP {response.status_code})."

        data = response.json()
        print(f"PlantNet results count: {len(data.get('results', []))}")
        print(f"PlantNet response: {json.dumps(data, indent=2)}")
        
        if not data.get('results'):
            return None, 'PlantNet returned no identification results. Try another angle with better lighting.'

        top_result = data['results'][0]
        species = top_result.get('species', {})
        scientific_name = species.get('scientificName', 'Unknown')
        genus_name = species.get('genus', {}).get('name', '')
        bloom_profile = build_bloom_profile(scientific_name, genus_name, user_location)
        
        return {
            'plant_name': species.get('commonNames', ['Unknown'])[0],
            'scientific_name': scientific_name,
            'plant_type': 'Unknown',
            'confidence': round(top_result.get('score', 0), 2),
            'description': f"Identified via PlantNet API. Genus: {species.get('genus', {}).get('name', 'Unknown')}",
            'bloom_season': bloom_profile.get('bloom_season', 'Unknown'),
            'bloom_season_by_location': bloom_profile.get('bloom_season_by_location', {}),
            'care_tips': [
                'Research specific care requirements for this species',
                'Check soil moisture needs',
                'Provide appropriate sunlight',
                'Maintain suitable temperature'
            ],
            'toxicity': 'Unknown - research before consumption',
            'native_regions': [species.get('genus', {}).get('name', 'Unknown')],
            'genus': species.get('genus', {}).get('name', ''),
            'family': species.get('family', {}).get('name', '')
        }, None

    except Exception as e:
        print(f"PlantNet error: {e}")
        return None, 'Plant scan failed due to an internal processing error.'


@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat with BotanistAI using Groq."""
    try:
        data = request.json
        message = data.get('message', '')
        context = data.get('context', '')

        if not message:
            return jsonify({'error': 'No message provided'}), 400

        combined_message = f"{context}\n\nUser: {message}".strip() if context else message

        stream = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": BOTANIST_SYSTEM_PROMPT},
                {"role": "user", "content": combined_message}
            ],
            stream=False
        )

        reply = stream.choices[0].message.content

        return jsonify({'reply': reply}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok'}), 200


if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
