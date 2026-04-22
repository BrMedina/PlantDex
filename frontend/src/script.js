
const API_BASE_URL = 'http://localhost:5000';

const navItems = Array.from(document.querySelectorAll('.nav-item'));
const panels = Array.from(document.querySelectorAll('.tab-panel'));
const fabButton = document.getElementById('fabButton');
const cameraPanel = document.getElementById('cameraPanel');
const shutterButton = document.getElementById('shutterButton');
const photoCanvas = document.getElementById('photoCanvas');
const plantResults = document.getElementById('plantResults');
const emptyState = document.getElementById('emptyState');
const clearResultsBtn = document.getElementById('clearResultsBtn');
const clearAllHistoryBtn = document.getElementById('clearAllHistoryBtn');
const addToCollectionBtn = document.getElementById('addToCollectionBtn');
const scanHistoryList = document.getElementById('scanHistoryList');
const collectionsList = document.getElementById('collectionsList');
const collectionsEmpty = document.getElementById('collectionsEmpty');
const collectionDetailModal = document.getElementById('collectionDetailModal');
const collectionDetailBackdrop = document.getElementById('collectionDetailBackdrop');
const collectionDetailCloseBtn = document.getElementById('collectionDetailCloseBtn');
const collectionDetailContent = document.getElementById('collectionDetailContent');
const openChatBtn = document.getElementById('openChatBtn');
const chatBackBtn = document.getElementById('chatBackBtn');
const plantDetailsView = document.getElementById('plantDetailsView');
const plantChatPanel = document.getElementById('plantChatPanel');
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendChatBtn = document.getElementById('sendChatBtn');
const resultPhotoWrap = document.getElementById('resultPhotoWrap');
const resultPlantPhoto = document.getElementById('resultPlantPhoto');

const STORAGE_KEYS = {
  latestScan: 'plantdex.latestScan',
  scanHistory: 'plantdex.scanHistory',
  collections: 'plantdex.collections'
};

// IP Camera elements
const ipCameraUrl = document.getElementById('ipCameraUrl');
const ipCameraStream = document.getElementById('ipCameraStream');
const ipCameraStatus = document.getElementById('ipCameraStatus');
const connectIpCamera = document.getElementById('connectIpCamera');

let ipCameraRefreshInterval = null;
let currentPlantContext = '';
let latestScanData = null;
let scanHistory = [];
let collectionPlants = [];

function loadStoredJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

function persistState() {
  localStorage.setItem(STORAGE_KEYS.latestScan, JSON.stringify(latestScanData));
  localStorage.setItem(STORAGE_KEYS.scanHistory, JSON.stringify(scanHistory));
  localStorage.setItem(STORAGE_KEYS.collections, JSON.stringify(collectionPlants));
}

function formatShortDate(isoDate) {
  try {
    return new Date(isoDate).toLocaleString();
  } catch {
    return 'Unknown time';
  }
}

function renderScanHistory() {
  scanHistoryList.innerHTML = '';

  if (!scanHistory.length) {
    const li = document.createElement('li');
    li.className = 'history-empty';
    li.textContent = 'No scans yet.';
    scanHistoryList.appendChild(li);
    return;
  }

  scanHistory.forEach((entry) => {
    const li = document.createElement('li');
    li.className = 'history-item';

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'history-item-btn';
    button.innerHTML = `
      <span class="history-name">${entry.plant_name || 'Unknown Plant'}</span>
      <span class="history-meta">${entry.scientific_name || 'Unknown'} · ${formatShortDate(entry.scanned_at)}</span>
    `;

    button.addEventListener('click', () => {
      latestScanData = entry.data;
      persistState();
      displayPlantResults(entry.data, { recordHistory: false });
      setActiveTab('home');
    });

    li.appendChild(button);
    scanHistoryList.appendChild(li);
  });
}

function renderCollections() {
  collectionsList.innerHTML = '';

  if (!collectionPlants.length) {
    collectionsEmpty.style.display = 'block';
    return;
  }

  collectionsEmpty.style.display = 'none';

  collectionPlants.forEach((entry) => {
    const card = document.createElement('div');
    card.className = 'collection-card';

    const plantPhoto = entry.photo_data_url || (entry.data && entry.data.photo_data_url) || '';
    const imageMarkup = plantPhoto
      ? `<img class="collection-thumb" src="${plantPhoto}" alt="Saved photo of ${entry.plant_name || 'plant'}">`
      : '';

    card.innerHTML = `
      ${imageMarkup}
      <h4>${entry.plant_name || 'Unknown Plant'}</h4>
      <p class="collection-scientific">${entry.scientific_name || 'Unknown'}</p>
      <p class="collection-meta">Saved: ${formatShortDate(entry.saved_at)}</p>
      <div class="collection-actions">
        <button type="button" class="collection-open">Open</button>
        <button type="button" class="collection-remove">Remove</button>
      </div>
    `;

    card.querySelector('.collection-open').addEventListener('click', () => {
      openCollectionDetailModal(entry.data);
    });

    card.querySelector('.collection-remove').addEventListener('click', () => {
      collectionPlants = collectionPlants.filter((x) => x.id !== entry.id);
      persistState();
      renderCollections();
    });

    collectionsList.appendChild(card);
  });
}

function openCollectionDetailModal(data) {
  const nativeRegions = Array.isArray(data.native_regions) && data.native_regions.length
    ? data.native_regions.join(', ')
    : 'Unknown';

  const careTips = Array.isArray(data.care_tips) && data.care_tips.length
    ? data.care_tips.map((tip) => `<li>${tip}</li>`).join('')
    : '<li>No care tips available</li>';

  const photoMarkup = data.photo_data_url
    ? `<img class="detail-photo" src="${data.photo_data_url}" alt="Saved photo of ${data.plant_name || 'plant'}">`
    : '';

  collectionDetailContent.innerHTML = `
    ${photoMarkup}
    <h4 class="detail-name">${data.plant_name || 'Unknown Plant'}</h4>
    <p class="detail-scientific">${data.scientific_name || 'Unknown'}</p>
    <p class="detail-identified">Identified by: ${data.identified_by || 'PlantDex model'}</p>
    <div class="detail-grid">
      <div class="detail-item"><span>Plant Type</span><p>${data.plant_type || 'Unknown'}</p></div>
      <div class="detail-item"><span>Bloom Season</span><p>${data.bloom_season || 'Unknown'}</p></div>
      <div class="detail-item"><span>Toxicity</span><p>${data.toxicity || 'Unknown'}</p></div>
      <div class="detail-item"><span>Confidence</span><p>${Math.round((data.confidence || 0) * 100)}%</p></div>
    </div>
    <div class="detail-block">
      <h5>Description</h5>
      <p>${data.description || 'No description available.'}</p>
    </div>
    <div class="detail-block">
      <h5>Native Regions</h5>
      <p>${nativeRegions}</p>
    </div>
    <div class="detail-block">
      <h5>Care Tips</h5>
      <ul class="detail-care-list">${careTips}</ul>
    </div>
  `;

  collectionDetailModal.classList.remove('is-hidden');
  collectionDetailModal.setAttribute('aria-hidden', 'false');
}

function compressImageDataUrl(imageDataUrl, maxDimension = 720, quality = 0.82) {
  return new Promise((resolve) => {
    const image = new Image();

    image.onload = () => {
      const width = image.naturalWidth || image.width;
      const height = image.naturalHeight || image.height;

      if (!width || !height) {
        resolve(imageDataUrl);
        return;
      }

      const scale = Math.min(1, maxDimension / Math.max(width, height));
      const targetWidth = Math.max(1, Math.round(width * scale));
      const targetHeight = Math.max(1, Math.round(height * scale));

      const canvas = document.createElement('canvas');
      canvas.width = targetWidth;
      canvas.height = targetHeight;

      const context = canvas.getContext('2d');
      if (!context) {
        resolve(imageDataUrl);
        return;
      }

      context.drawImage(image, 0, 0, targetWidth, targetHeight);
      resolve(canvas.toDataURL('image/jpeg', quality));
    };

    image.onerror = () => {
      resolve(imageDataUrl);
    };

    image.src = imageDataUrl;
  });
}

function closeCollectionDetailModal() {
  collectionDetailModal.classList.add('is-hidden');
  collectionDetailModal.setAttribute('aria-hidden', 'true');
}

function initializeStoredState() {
  latestScanData = loadStoredJson(STORAGE_KEYS.latestScan, null);
  scanHistory = loadStoredJson(STORAGE_KEYS.scanHistory, []);
  collectionPlants = loadStoredJson(STORAGE_KEYS.collections, []);

  renderScanHistory();
  renderCollections();

  if (latestScanData) {
    displayPlantResults(latestScanData, { recordHistory: false });
  }
}

function setActiveTab(tabName) {
  navItems.forEach((item) => {
    item.classList.toggle('active', item.dataset.tab === tabName);
  });

  panels.forEach((panel) => {
    panel.classList.toggle('is-active', panel.dataset.panel === tabName);
  });
}

function stopIpCameraStream() {
  if (ipCameraRefreshInterval) {
    clearInterval(ipCameraRefreshInterval);
    ipCameraRefreshInterval = null;
  }
  ipCameraStream.src = '';
  ipCameraStatus.textContent = '';
}

function closeCamera() {
  cameraPanel.classList.remove('is-open');
  cameraPanel.setAttribute('aria-hidden', 'true');
  fabButton.classList.remove('is-open');
  stopIpCameraStream();
}

async function openCamera() {
  // Open camera panel (IP camera mode only)
  cameraPanel.classList.add('is-open');
  cameraPanel.setAttribute('aria-hidden', 'false');
  fabButton.classList.add('is-open');
}

function toggleCamera() {
  if (cameraPanel.classList.contains('is-open')) {
    closeCamera();
    return;
  }

  openCamera();
}

let currentIpCameraUrl = null;

async function capturePhotoFromVideo() {
  // If IP camera is connected, fetch the latest frame directly
  if (currentIpCameraUrl) {
    try {
      console.log('Fetching frame from:', currentIpCameraUrl);
      const response = await fetch(currentIpCameraUrl + '?t=' + Date.now(), {
        method: 'GET'
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: Failed to fetch frame`);
      }
      
      const blob = await response.blob();
      console.log('Fetched blob size:', blob.size, 'bytes');
      
      return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = () => {
          console.log('Base64 data length:', reader.result.length);
          resolve(reader.result);
        };
        reader.readAsDataURL(blob);
      });
    } catch (error) {
      console.error('Error fetching IP camera frame:', error);
      alert('Failed to fetch frame from IP camera. Check connection.');
      return null;
    }
  }
  
  // Fallback: try to capture from displayed image element
  const canvas = photoCanvas;
  const context = canvas.getContext('2d');

  let width = ipCameraStream.naturalWidth || ipCameraStream.width || 640;
  let height = ipCameraStream.naturalHeight || ipCameraStream.height || 480;

  if (width === 0) width = 640;
  if (height === 0) height = 480;

  canvas.width = width;
  canvas.height = height;
  
  try {
    context.drawImage(ipCameraStream, 0, 0, width, height);
  } catch (error) {
    console.error('Error drawing image:', error);
    alert('Failed to capture image. Make sure camera is connected.');
    return null;
  }

  return canvas.toDataURL('image/jpeg', 0.95);
}

function displayPlantResults(data, options = {}) {
  const { recordHistory = true } = options;

  const photoDataUrl = data.photo_data_url || '';
  if (photoDataUrl) {
    resultPlantPhoto.src = photoDataUrl;
    resultPhotoWrap.classList.remove('is-hidden');
  } else {
    resultPlantPhoto.src = '';
    resultPhotoWrap.classList.add('is-hidden');
  }

  document.getElementById('resultPlantName').textContent = data.plant_name || '---';
  document.getElementById('resultScientificName').textContent = `(${data.scientific_name || 'Unknown'})`;
  document.getElementById('resultIdentifiedBy').textContent = `Identified by: ${data.identified_by || 'PlantDex model'}`;
  document.getElementById('resultPlantType').textContent = data.plant_type || '---';
  document.getElementById('resultConfidence').textContent = `${Math.round((data.confidence || 0) * 100)}%`;
  document.getElementById('resultDescription').textContent = data.description || '---';
  document.getElementById('resultBloomSeason').textContent = data.bloom_season || '---';
  document.getElementById('resultToxicity').textContent = data.toxicity || 'Unknown';

  const careTipsList = document.getElementById('resultCareTips');
  careTipsList.innerHTML = '';
  if (Array.isArray(data.care_tips) && data.care_tips.length > 0) {
    data.care_tips.forEach((tip) => {
      const li = document.createElement('li');
      li.textContent = tip;
      careTipsList.appendChild(li);
    });
  } else {
    const li = document.createElement('li');
    li.textContent = 'No care tips available';
    careTipsList.appendChild(li);
  }

  const nativeRegions = data.native_regions || [];
  document.getElementById('resultNativeRegions').textContent =
    nativeRegions.length > 0 ? nativeRegions.join(', ') : 'Unknown';

  currentPlantContext = [
    `Plant Name: ${data.plant_name || 'Unknown'}`,
    `Scientific Name: ${data.scientific_name || 'Unknown'}`,
    `Plant Type: ${data.plant_type || 'Unknown'}`,
    `Bloom Season: ${data.bloom_season || 'Unknown'}`,
    `Toxicity: ${data.toxicity || 'Unknown'}`,
    `Native Regions: ${(nativeRegions.length > 0 ? nativeRegions.join(', ') : 'Unknown')}`,
    `Description: ${data.description || 'Unknown'}`
  ].join('\n');

  chatMessages.innerHTML = '';
  appendChatMessage('assistant', 'Ask me anything about this plant. I can help with care, bloom timing, and safety notes.');
  closePlantChat();

  latestScanData = data;
  if (recordHistory) {
    const newEntry = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
      scanned_at: new Date().toISOString(),
      plant_name: data.plant_name || 'Unknown Plant',
      scientific_name: data.scientific_name || 'Unknown',
      data
    };

    scanHistory = [newEntry, ...scanHistory].slice(0, 25);
  }

  persistState();
  renderScanHistory();

  emptyState.style.display = 'none';
  plantResults.classList.remove('hidden');
}

function appendChatMessage(role, text) {
  const bubble = document.createElement('div');
  bubble.className = `chat-message ${role}`;
  bubble.textContent = text;
  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function openPlantChat() {
  plantDetailsView.classList.add('is-hidden');
  plantChatPanel.classList.remove('is-hidden');
}

function closePlantChat() {
  plantChatPanel.classList.add('is-hidden');
  plantDetailsView.classList.remove('is-hidden');
}

async function sendPlantChatMessage() {
  const message = (chatInput.value || '').trim();
  if (!message) return;

  appendChatMessage('user', message);
  chatInput.value = '';
  sendChatBtn.disabled = true;

  try {
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        context: currentPlantContext
      })
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Chat request failed');
    }

    const payload = await response.json();
    appendChatMessage('assistant', payload.reply || 'No reply received.');
  } catch (error) {
    appendChatMessage('assistant', `I could not respond right now: ${error.message}`);
  } finally {
    sendChatBtn.disabled = false;
  }
}

function clearResults() {
  openCamera();
}

function clearAllHistory() {
  const shouldClear = window.confirm(
    'Clear all history? This will remove latest scan, scan history, and saved collections.'
  );

  if (!shouldClear) {
    return;
  }

  latestScanData = null;
  scanHistory = [];
  collectionPlants = [];

  persistState();
  renderScanHistory();
  renderCollections();

  closeCollectionDetailModal();
  closePlantChat();

  resultPlantPhoto.src = '';
  resultPhotoWrap.classList.add('is-hidden');

  plantResults.classList.add('hidden');
  emptyState.style.display = 'flex';

  setActiveTab('home');
}

function addCurrentPlantToCollection() {
  if (!latestScanData) {
    alert('Scan a plant first before adding to collections.');
    return;
  }

  const identity = `${latestScanData.scientific_name || ''}::${latestScanData.plant_name || ''}`.toLowerCase();
  const exists = collectionPlants.some((entry) => {
    const other = `${entry.scientific_name || ''}::${entry.plant_name || ''}`.toLowerCase();
    return other === identity;
  });

  if (exists) {
    alert('This plant is already in your collection.');
    return;
  }

  collectionPlants.unshift({
    id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    saved_at: new Date().toISOString(),
    plant_name: latestScanData.plant_name || 'Unknown Plant',
    scientific_name: latestScanData.scientific_name || 'Unknown',
    photo_data_url: latestScanData.photo_data_url || '',
    data: latestScanData
  });

  persistState();
  renderCollections();
  alert('Plant added to Collections.');
}

async function scanPlant(imageBase64) {
  if (!imageBase64) {
    alert('Failed to capture image. Please try again.');
    return;
  }

  shutterButton.disabled = true;
  shutterButton.textContent = 'Scanning...';

  try {
    const base64Data = imageBase64.split(',')[1] || imageBase64;
    const optimizedPhoto = await compressImageDataUrl(imageBase64);
    
    // Debug: Log image size and first 50 chars
    console.log('Captured image size:', base64Data.length, 'bytes');
    console.log('Image preview (first 50 chars):', base64Data.substring(0, 50));

    const response = await fetch(`${API_BASE_URL}/api/scan-plant`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        image: base64Data,
        location: 'Northern Hemisphere'
      })
    });

    console.log('Backend response status:', response.status);

    if (!response.ok) {
      const errorData = await response.json();
      console.error('Backend error:', errorData);
      throw new Error(errorData.error || 'Scan failed');
    }

    const plantData = await response.json();
    plantData.photo_data_url = optimizedPhoto;
    displayPlantResults(plantData);
    closeCamera();
    setActiveTab('home');
  } catch (error) {
    console.error('Scan error:', error);
    alert(`Failed to scan plant: ${error.message}`);
  } finally {
    shutterButton.disabled = false;
    shutterButton.innerHTML = '<img src="../assets/Shutter.png" alt="Shutter button">';
  }
}

navItems.forEach((item) => {
  item.addEventListener('click', () => {
    const nextTab = item.dataset.tab;
    setActiveTab(nextTab);
    closeCamera();
  });
});

fabButton.addEventListener('click', toggleCamera);

shutterButton.addEventListener('click', async () => {
  shutterButton.classList.add('is-pressed');
  setTimeout(() => shutterButton.classList.remove('is-pressed'), 140);

  const photoBase64 = await capturePhotoFromVideo();
  if (photoBase64) {
    await scanPlant(photoBase64);
  }
});

clearResultsBtn.addEventListener('click', clearResults);
clearAllHistoryBtn.addEventListener('click', clearAllHistory);
addToCollectionBtn.addEventListener('click', addCurrentPlantToCollection);
openChatBtn.addEventListener('click', openPlantChat);
chatBackBtn.addEventListener('click', closePlantChat);
collectionDetailCloseBtn.addEventListener('click', closeCollectionDetailModal);
collectionDetailBackdrop.addEventListener('click', closeCollectionDetailModal);
sendChatBtn.addEventListener('click', sendPlantChatMessage);
chatInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    sendPlantChatMessage();
  }
});

// IP Camera connection handler
connectIpCamera.addEventListener('click', () => {
  const url = ipCameraUrl.value.trim();
  if (!url) {
    ipCameraStatus.textContent = 'Enter IP camera URL';
    return;
  }
  connectToIpCamera(url);
});

function connectToIpCamera(url) {
  ipCameraStatus.textContent = 'Connecting...';
  
  // Normalize URL - if just base URL, try /shot.jpg for IP Webcam
  let streamUrl = url;
  if (!url.includes('/shot.jpg') && !url.includes('/video') && !url.includes('/mjpeg')) {
    streamUrl = url.replace(/\/$/, '') + '/shot.jpg';
  }
  
  // Test if the URL is accessible by trying to fetch one frame
  console.log('Testing IP camera URL:', streamUrl);
  
  fetch(streamUrl + '?t=' + Date.now(), { method: 'GET' })
    .then(response => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return response.blob();
    })
    .then(blob => {
      console.log('Successfully fetched frame, size:', blob.size, 'bytes');
      ipCameraStatus.textContent = 'Connected!';
      startIpCameraStream(streamUrl);
    })
    .catch(error => {
      console.error('Connection error:', error);
      ipCameraStatus.textContent = `Failed: ${error.message}. Try: http://192.168.1.x:8080/shot.jpg`;
    });
}

function startIpCameraStream(url) {
  // Store URL for direct frame fetching
  currentIpCameraUrl = url;
  
  // Also display the stream in the img element for preview
  ipCameraStream.src = url + '?t=' + Date.now();

  // Refresh preview every 200ms for smoother video effect (5 fps)
  if (ipCameraRefreshInterval) {
    clearInterval(ipCameraRefreshInterval);
  }

  ipCameraRefreshInterval = setInterval(() => {
    ipCameraStream.src = url + '?t=' + Date.now();
  }, 200);
}

function stopIpCameraStream() {
  if (ipCameraRefreshInterval) {
    clearInterval(ipCameraRefreshInterval);
    ipCameraRefreshInterval = null;
  }
  ipCameraStream.src = '';
  ipCameraStatus.textContent = '';
  currentIpCameraUrl = null;
}

window.addEventListener('beforeunload', () => {
  stopIpCameraStream();
});

initializeStoredState();