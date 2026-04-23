# PlantDex - AI-Powered Plant Identification App

A mobile-first web app that uses Pl@ntNet for plant identification and Groq for botanical chatbot conversations.

## Features

- 📸 **Real-time Plant Scanning**: Capture photos via mobile camera
- 🤖 **Pl@ntNet API Integration**: Accurate plant species identification  
- 💬 **Groq Chatbot**: Get detailed botanical information
- 📋 **Care Tips & Toxicity Info**: Get complete plant care details
- 📱 **Mobile-optimized UI**: Beautiful, responsive design

## Setup

### Backend

1. **Install dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **Create `.env` file** in `backend/`:
   ```
   GROQ_API_KEY=your_groq_api_key_here
   GEMINI_API_KEY=your_gemini_api_key_here
   PORT=5000
   ```

3. **Get API Keys**:
   - [Groq API](https://console.groq.com)
   - [Pl@ntNet API](https://my.plantnet.org/)

4. **Start server**:
   ```bash
   python app.py
   ```
   Server runs at `http://localhost:5000`

### Frontend

1. **Install dependencies** (if using npm build):
   ```bash
   cd frontend
   npm install
   ```

2. **Serve files**:
   - Open `frontend/src/index.html` in a local server or browser
   - Or use: `python -m http.server 8000` from `frontend/src/`

3. **API Configuration**:
   - Update `API_BASE_URL` in `script.js` if backend is on different port

## Endpoints

### POST `/api/scan-plant`
Scan and identify a plant from an image.

**Request**:
```json
{
  "image": "base64_encoded_jpeg",
  "location": "Northern Hemisphere"
}
```

**Response**:
```json
{
  "plant_name": "Tomato Plant",
  "scientific_name": "Solanum lycopersicum",
  "plant_type": "Vegetable",
  "confidence": 0.95,
  "description": "...",
  "bloom_season": "Spring-Summer",
  "bloom_season_by_location": {
    "northern_hemisphere": "May-August",
    "southern_hemisphere": "November-February"
  },
  "care_tips": ["Water daily", "Full sun", "Rich soil", "Warm temps"],
  "toxicity": "Unripe fruit is toxic",
  "native_regions": ["South America"]
}
```

### POST `/api/chat`
Chat with BotanistAI about plants.

**Request**:
```json
{
  "message": "What should I feed my rose plant?",
  "context": "Optional plant context from scan"
}
```

**Response**:
```json
{
  "reply": "Roses thrive with..."
}
```

### GET `/health`
Health check endpoint.

## Architecture

```
Frontend (HTML/CSS/JS)
    ↓
Mobile Camera Capture
    ↓
Flask Backend API
    ├→ Gemini Vision API (plant scanning)
    └→ Groq API (chatbot)
```

## How It Works

1. User opens app on mobile browser
2. Taps camera FAB button
3. Captures plant photo with shutter button
4. Frontend sends base64 image to `/api/scan-plant`
5. Pl@ntNet identifies plant and extracts details
6. Results displayed with confidence badge, care tips, blooming info
7. User can discuss plant further using chat feature

## File Structure

```
PlantDex/
├── backend/
│   ├── app.py (Flask server with endpoints)
│   └── requirements.txt (Python dependencies)
└── frontend/
    ├── src/
    │   ├── index.html (app structure)
    │   ├── script.js (camera & API logic)
    │   ├── input.css (custom styles)
    │   └── output.css (compiled styles)
    ├── assets/
    │   ├── Logo.png
    │   └── Shutter.png
    └── package.json
```

## Browser Support

- Chrome/Chromium (mobile & desktop)
- Firefox
- Safari
- Edge

Requires HTTPS or localhost for camera access.

## API Limits

- **Groq**: Free tier allows ~25 requests/minute
- **Pl@ntNet**: Check your quota at [Pl@ntNet](https://my.plantnet.org/)

## Troubleshooting

**Camera not working?**
- Check browser permissions
- Must be HTTPS or localhost
- Mobile browser needs camera permission

**API errors?**
- Verify API keys in `.env`
- Check CORS is enabled
- Ensure backend server is running

**Results not showing?**
- Check browser console for errors
- Verify image was captured
- Check API response in Network tab

## Future Enhancements

- [ ] Save plant scans to local history
- [ ] Barcode/QR code scanning
- [ ] Plant disease detection
- [ ] Watering reminders
- [ ] Community plant database
- [ ] Offline mode

## License

MIT
