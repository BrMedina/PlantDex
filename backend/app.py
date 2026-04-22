import os
import json
import base64
import hashlib
import random
import requests
from datetime import datetime
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
PLANTNET_BASE_URL = os.getenv("PLANTNET_BASE_URL", "https://my-api.plantnet.org").strip().rstrip('/')

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

PROGRESS_FILE = os.path.join(os.path.dirname(__file__), 'user_progress.json')

BEGINNER_ACHIEVEMENTS = [
    {
        'id': 'first_scan',
        'title': 'First Sprout',
        'description': 'Complete your first plant scan.',
        'stat_key': 'scans_count',
        'target': 1
    },
    {
        'id': 'scan_streak_3',
        'title': 'Leaf Explorer',
        'description': 'Complete 3 total plant scans.',
        'stat_key': 'scans_count',
        'target': 3
    },
    {
        'id': 'chat_once',
        'title': 'Curious Botanist',
        'description': 'Send your first chat message to BotanistAI.',
        'stat_key': 'chat_count',
        'target': 1
    },
    {
        'id': 'save_once',
        'title': 'Seed Keeper',
        'description': 'Save one plant to your collection.',
        'stat_key': 'collections_count',
        'target': 1
    },
    {
        'id': 'collector_5',
        'title': 'Garden Starter',
        'description': 'Save 5 plants to your collection.',
        'stat_key': 'collections_count',
        'target': 5
    }
]

DAILY_CHALLENGE_POOL = [
    {
        'id': 'daily_scan_1',
        'title': 'Daily Scan',
        'description': 'Scan 1 plant today.',
        'event_type': 'scan_completed',
        'target': 1
    },
    {
        'id': 'daily_scan_2',
        'title': 'Scan Warmup',
        'description': 'Scan 2 plants today.',
        'event_type': 'scan_completed',
        'target': 2
    },
    {
        'id': 'daily_chat_1',
        'title': 'Ask BotanistAI',
        'description': 'Send 1 chat message today.',
        'event_type': 'chat_message_sent',
        'target': 1
    },
    {
        'id': 'daily_save_1',
        'title': 'Save a Discovery',
        'description': 'Add 1 plant to your collection today.',
        'event_type': 'collection_saved',
        'target': 1
    }
]

EVENT_TO_STAT_KEY = {
    'scan_completed': 'scans_count',
    'chat_message_sent': 'chat_count',
    'collection_saved': 'collections_count'
}


def utc_today_string():
    return datetime.utcnow().strftime('%Y-%m-%d')


def default_progress_state():
    return {
        'stats': {
            'scans_count': 0,
            'chat_count': 0,
            'collections_count': 0
        },
        'achievement_unlocks': {},
        'daily': {
            'date': '',
            'items': []
        }
    }


def ensure_progress_schema(progress):
    safe = progress if isinstance(progress, dict) else {}

    stats = safe.get('stats') if isinstance(safe.get('stats'), dict) else {}
    safe['stats'] = {
        'scans_count': int(stats.get('scans_count', 0) or 0),
        'chat_count': int(stats.get('chat_count', 0) or 0),
        'collections_count': int(stats.get('collections_count', 0) or 0)
    }

    unlocks = safe.get('achievement_unlocks')
    safe['achievement_unlocks'] = unlocks if isinstance(unlocks, dict) else {}

    daily = safe.get('daily') if isinstance(safe.get('daily'), dict) else {}
    date_value = daily.get('date', '')
    items_value = daily.get('items', [])
    safe['daily'] = {
        'date': str(date_value) if date_value else '',
        'items': items_value if isinstance(items_value, list) else []
    }

    return safe


def load_progress_state():
    if not os.path.exists(PROGRESS_FILE):
        return default_progress_state()

    try:
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as handle:
            return ensure_progress_schema(json.load(handle))
    except Exception as error:
        print(f"Progress load error: {error}")
        return default_progress_state()


def save_progress_state(progress):
    try:
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as handle:
            json.dump(progress, handle, indent=2)
    except Exception as error:
        print(f"Progress save error: {error}")


def pick_daily_challenges(day_string):
    seed_value = int(hashlib.sha256(day_string.encode('utf-8')).hexdigest(), 16)
    rng = random.Random(seed_value)
    picks = rng.sample(DAILY_CHALLENGE_POOL, k=min(2, len(DAILY_CHALLENGE_POOL)))

    daily_items = []
    for challenge in picks:
        daily_items.append({
            'id': challenge['id'],
            'title': challenge['title'],
            'description': challenge['description'],
            'event_type': challenge['event_type'],
            'target': int(challenge['target']),
            'progress': 0,
            'completed': False
        })

    return daily_items


def refresh_daily_if_needed(progress):
    today = utc_today_string()
    if progress['daily'].get('date') == today and progress['daily'].get('items'):
        return

    progress['daily'] = {
        'date': today,
        'items': pick_daily_challenges(today)
    }


def evaluate_new_achievements(progress):
    unlocked_ids = progress.get('achievement_unlocks', {})
    stats = progress.get('stats', {})
    newly_unlocked = []

    for achievement in BEGINNER_ACHIEVEMENTS:
        if achievement['id'] in unlocked_ids:
            continue

        stat_value = int(stats.get(achievement['stat_key'], 0) or 0)
        if stat_value >= int(achievement['target']):
            unlocked_at = datetime.utcnow().isoformat(timespec='seconds') + 'Z'
            unlocked_ids[achievement['id']] = unlocked_at
            newly_unlocked.append({
                'id': achievement['id'],
                'title': achievement['title'],
                'unlocked_at': unlocked_at
            })

    progress['achievement_unlocks'] = unlocked_ids
    return newly_unlocked


def apply_progress_event(progress, event_type):
    refresh_daily_if_needed(progress)

    stat_key = EVENT_TO_STAT_KEY.get(event_type)
    if stat_key:
        progress['stats'][stat_key] = int(progress['stats'].get(stat_key, 0) or 0) + 1

    for daily_item in progress['daily'].get('items', []):
        if daily_item.get('event_type') != event_type or daily_item.get('completed'):
            continue

        next_value = int(daily_item.get('progress', 0) or 0) + 1
        target_value = int(daily_item.get('target', 1) or 1)
        daily_item['progress'] = min(next_value, target_value)
        daily_item['completed'] = daily_item['progress'] >= target_value

    return evaluate_new_achievements(progress)


def build_progress_payload(progress, newly_unlocked=None):
    refresh_daily_if_needed(progress)
    unlock_map = progress.get('achievement_unlocks', {})
    stats = progress.get('stats', {})

    achievements = []
    for achievement in BEGINNER_ACHIEVEMENTS:
        stat_value = int(stats.get(achievement['stat_key'], 0) or 0)
        target = int(achievement['target'])
        progress_value = min(stat_value, target)
        unlocked_at = unlock_map.get(achievement['id'])
        achievements.append({
            'id': achievement['id'],
            'title': achievement['title'],
            'description': achievement['description'],
            'target': target,
            'progress': progress_value,
            'unlocked': bool(unlocked_at),
            'unlocked_at': unlocked_at
        })

    daily_items = []
    for item in progress['daily'].get('items', []):
        daily_items.append({
            'id': item.get('id'),
            'title': item.get('title'),
            'description': item.get('description'),
            'target': int(item.get('target', 1) or 1),
            'progress': int(item.get('progress', 0) or 0),
            'completed': bool(item.get('completed'))
        })

    unlocked_count = len([item for item in achievements if item['unlocked']])
    completed_daily = len([item for item in daily_items if item['completed']])

    return {
        'today': progress['daily'].get('date', utc_today_string()),
        'stats': stats,
        'achievements': achievements,
        'daily_challenges': daily_items,
        'summary': {
            'unlocked_achievements': unlocked_count,
            'total_achievements': len(achievements),
            'completed_daily_challenges': completed_daily,
            'total_daily_challenges': len(daily_items)
        },
        'newly_unlocked': newly_unlocked or []
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
            error_code = 503 if 'could not connect' in plantnet_error.lower() else 400
            return jsonify({'error': plantnet_error}), error_code

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

        endpoint_candidates = [
            f"{PLANTNET_BASE_URL}/v2/identify/all",
            'https://my-api.plantnet.org/v2/identify/all',
            'https://api.plantnet.org/v2/identify/all'
        ]
        endpoint_candidates = list(dict.fromkeys(endpoint_candidates))
        organ_candidates = ['leaf', 'flower', 'fruit', 'bark', 'auto']

        response = None
        last_connection_error = None
        for endpoint in endpoint_candidates:
            for organ in organ_candidates:
                files = {'images': ('plant.jpg', BytesIO(image_data), 'image/jpeg')}

                try:
                    response = requests.post(
                        endpoint,
                        files=files,
                        data={'organs': organ},
                        params=params,
                        timeout=30
                    )
                except requests.exceptions.ConnectionError as conn_error:
                    last_connection_error = conn_error
                    print(f"PlantNet connection error at {endpoint}: {conn_error}")
                    response = None
                    break

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

            if response is not None and response.status_code == 200:
                break

        if response is None and last_connection_error is not None:
            return None, (
                'PlantNet could not connect. Check internet/firewall or allow HTTPS to '
                'my-api.plantnet.org:443 (and api.plantnet.org:443).'
            )

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


@app.route('/api/player-progress', methods=['GET'])
def get_player_progress():
    """Return beginner achievements and daily challenge state."""
    try:
        progress = load_progress_state()
        refresh_daily_if_needed(progress)
        save_progress_state(progress)
        return jsonify(build_progress_payload(progress)), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/player-progress/event', methods=['POST'])
def post_player_progress_event():
    """Track a user event and return updated progress."""
    try:
        data = request.json or {}
        event_type = str(data.get('event_type', '')).strip()

        if event_type not in EVENT_TO_STAT_KEY:
            return jsonify({'error': 'Unsupported event_type'}), 400

        progress = load_progress_state()
        newly_unlocked = apply_progress_event(progress, event_type)
        save_progress_state(progress)

        return jsonify(build_progress_payload(progress, newly_unlocked=newly_unlocked)), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok'}), 200


if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
