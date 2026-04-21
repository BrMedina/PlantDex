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


def parse_json_object(text):
    """Extract and parse first JSON object found in model output."""
    try:
        return json.loads(text)
    except Exception:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end + 1])
    return {}


def normalize_species_name(scientific_name):
    """Normalize scientific name to genus + species for lookup."""
    if not scientific_name:
        return ''

    parts = [p for p in scientific_name.strip().split() if p]
    if len(parts) < 2:
        return scientific_name.strip().lower()

    return f"{parts[0].lower()} {parts[1].lower()}"


def format_month_range(months):
    """Format months into a readable season range."""
    if not months:
        return 'Unknown'

    if len(months) == 1:
        return months[0]

    return f"{months[0]}-{months[-1]}"


def build_bloom_profile(scientific_name, genus_name):
    """Build bloom payload with species/genus fallback."""
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
            'bloom_source': 'No reliable bloom data available for this species in the current PlantDex dataset.'
        }

    return {
        'bloom_season': format_month_range(north_months),
        'bloom_source': f"Estimated from {source}-level bloom profile."
    }


def build_plant_description(species, score):
    """Build a readable plant description from identification metadata."""
    scientific_name = species.get('scientificName', 'Unknown')
    genus = species.get('genus', {}).get('name', 'Unknown genus')
    family = species.get('family', {}).get('name', 'Unknown family')
    common_names = species.get('commonNames', [])

    common_name_text = ''
    if common_names:
        common_name_text = f" Commonly known as {common_names[0]}."

    confidence_pct = int(round((score or 0) * 100))
    return (
        f"{scientific_name} is a flowering plant in the {family} family and {genus} genus."
        f"{common_name_text}"
        f" This profile is based on visual identification confidence of about {confidence_pct}%."
    ).strip()


def enrich_plant_details_with_groq(scientific_name, common_name, family, genus):
    """Use Groq model knowledge to enrich plant details."""
    if not os.getenv("GROQ_API_KEY"):
        return {}

    prompt = (
        "Return only valid JSON with keys: description, plant_type, bloom_season, toxicity, native_regions. "
        "Do not include markdown. native_regions must be an array of strings. "
        "If uncertain, use 'Unknown'. "
        f"Plant scientific name: {scientific_name}. "
        f"Common name: {common_name}. "
        f"Family: {family}. "
        f"Genus: {genus}."
    )

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "You are a botanist assistant that returns concise factual JSON only."
                },
                {"role": "user", "content": prompt}
            ],
            stream=False
        )
        content = completion.choices[0].message.content or ""
        parsed = parse_json_object(content)
        return parsed if isinstance(parsed, dict) else {}
    except Exception as e:
        print(f"Groq enrichment error: {e}")
        return {}


@app.route('/api/scan-plant', methods=['POST'])
def scan_plant():
    """Scan plant using PlantNet API only."""
    try:
        data = request.json
        image_base64 = data.get('image')

        if not image_base64:
            return jsonify({'error': 'No image provided'}), 400

        if not PLANTNET_API_KEY:
            return jsonify({'error': 'PlantNet API key not configured. Add PLANTNET_API_KEY to .env'}), 500

        # Query PlantNet API
        plantnet_results, plantnet_error = query_plantnet(image_base64)

        if plantnet_error:
            return jsonify({'error': plantnet_error}), 400

        if not plantnet_results:
            return jsonify({'error': 'Could not identify plant. Try a clearer close-up image.'}), 400

        return jsonify(plantnet_results), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def query_plantnet(image_base64):
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
        score = top_result.get('score', 0)
        scientific_name = species.get('scientificName', 'Unknown')
        genus_name = species.get('genus', {}).get('name', '')
        family_name = species.get('family', {}).get('name', '')
        common_name = species.get('commonNames', ['Unknown'])[0]
        bloom_profile = build_bloom_profile(scientific_name, genus_name)
        plant_description = build_plant_description(species, score)
        groq_details = enrich_plant_details_with_groq(
            scientific_name=scientific_name,
            common_name=common_name,
            family=family_name,
            genus=genus_name
        )

        final_description = str(groq_details.get('description') or plant_description)
        final_plant_type = str(groq_details.get('plant_type') or 'Unknown')
        final_bloom_season = str(groq_details.get('bloom_season') or bloom_profile.get('bloom_season', 'Unknown'))
        final_toxicity = str(groq_details.get('toxicity') or 'Unknown - research before consumption')
        groq_regions = groq_details.get('native_regions')
        if isinstance(groq_regions, list) and groq_regions:
            final_native_regions = [str(r).strip() for r in groq_regions if str(r).strip()]
        else:
            final_native_regions = [genus_name] if genus_name else ['Unknown']

        identified_by = 'PlantNet API + Groq enrichment' if groq_details else 'PlantNet API'
        
        return {
            'plant_name': common_name,
            'scientific_name': scientific_name,
            'plant_type': final_plant_type,
            'confidence': round(score, 2),
            'description': final_description,
            'identified_by': identified_by,
            'bloom_season': final_bloom_season,
            'bloom_source': bloom_profile.get('bloom_source', 'Estimated from species data.'),
            'care_tips': [
                'Research specific care requirements for this species',
                'Check soil moisture needs',
                'Provide appropriate sunlight',
                'Maintain suitable temperature'
            ],
            'toxicity': final_toxicity,
            'native_regions': final_native_regions,
            'genus': genus_name,
            'family': family_name
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
