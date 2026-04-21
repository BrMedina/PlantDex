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
PLANTNET_API_KEY = os.getenv("PLANTNET_API_KEY", "")

BOTANIST_SYSTEM_PROMPT = """You are BotanistAI, a seasoned botanist with an insatiable passion for the intricate world of flora. Your role is to serve as a deeply knowledgeable and enthusiastic guide for users who are looking to identify, understand, and care for plants of all species. When a user presents you with a description or an image of a plant, you should approach the task with scientific rigor. You speak with a blend of academic precision and approachable warmth, often sharing fascinating facts about a plant's evolutionary history or its specific ecological niche. Your expertise extends to plant life cycles, blooming patterns, pollination methods, and environmental triggers. You are also tasked with offering practical advice on soil composition, light requirements, and hydration needs. You should be mindful of plant safety, always providing warnings if a species is toxic or invasive. Every response should foster a deeper appreciation for the natural world."""


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
        plantnet_results = query_plantnet(image_base64)
        
        if not plantnet_results:
            return jsonify({'error': 'Could not identify plant. Try a clearer image.'}), 400

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

        # PlantNet identify endpoint varies across older/newer docs; try known hosts.
        endpoint_candidates = [
            'https://my-api.plantnet.org/v2/identify/all',
            'https://api.plantnet.org/v2/identify/all'
        ]

        response = None
        for endpoint in endpoint_candidates:
            files = {'images': ('plant.jpg', BytesIO(image_data), 'image/jpeg')}
            response = requests.post(
                endpoint,
                files=files,
                data={'organs': 'auto'},
                params=params,
                timeout=30
            )

            print(f"PlantNet endpoint: {endpoint}")
            print(f"PlantNet response status: {response.status_code}")

            if response.status_code == 404:
                continue

            break

        if response is None or response.status_code != 200:
            status = response.status_code if response is not None else 'no-response'
            body = response.text if response is not None else 'No response body'
            print(f"PlantNet API error: {status}")
            print(f"Response: {body}")
            return None

        data = response.json()
        print(f"PlantNet results count: {len(data.get('results', []))}")
        print(f"PlantNet response: {json.dumps(data, indent=2)}")
        
        if not data.get('results'):
            return None

        top_result = data['results'][0]
        species = top_result.get('species', {})
        
        return {
            'plant_name': species.get('commonNames', ['Unknown'])[0],
            'scientific_name': species.get('scientificName', 'Unknown'),
            'plant_type': 'Unknown',
            'confidence': round(top_result.get('score', 0), 2),
            'description': f"Identified via PlantNet API. Genus: {species.get('genus', {}).get('name', 'Unknown')}",
            'bloom_season': 'Unknown',
            'bloom_season_by_location': {
                'northern_hemisphere': 'Unknown',
                'southern_hemisphere': 'Unknown',
                'user_location': 'Unknown'
            },
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
        }

    except Exception as e:
        print(f"PlantNet error: {e}")
        return None


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
