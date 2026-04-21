
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

// IP Camera elements
const ipCameraUrl = document.getElementById('ipCameraUrl');
const ipCameraStream = document.getElementById('ipCameraStream');
const ipCameraStatus = document.getElementById('ipCameraStatus');
const connectIpCamera = document.getElementById('connectIpCamera');

let ipCameraRefreshInterval = null;

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

function displayPlantResults(data) {
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

  emptyState.style.display = 'none';
  plantResults.classList.remove('hidden');
}

function clearResults() {
  plantResults.classList.add('hidden');
  emptyState.style.display = 'flex';
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