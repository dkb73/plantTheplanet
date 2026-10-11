// PlantMyPlanet Application State
let token = localStorage.getItem("plantmyplanet_token");
let currentUser = null;
let currentCrops = [];
let selectedCategory = "all";
let selectedScale = "home_garden";
let pendingPlant = null;
let activePlanting = null;
let authMode = "login";
let activeCropDetail = null;

const API = "/api/v1";

document.addEventListener("DOMContentLoaded", () => {
  // Set default date for planting modal
  const dateInput = document.getElementById("confirm-date-input");
  if (dateInput) {
    dateInput.value = new Date().toISOString().split("T")[0];
  }

  // Check auth
  if (token) {
    fetchCurrentUser();
  } else {
    renderHeaderAuth();
  }

  // Pre-fetch recommendations for initial coordinates
  loadRecommendations(false);
});

// View Navigation
function navigateTo(view) {
  document.getElementById("view-landing").classList.add("hidden");
  document.getElementById("view-discovery").classList.add("hidden");
  document.getElementById("view-garden").classList.add("hidden");
  document.getElementById("view-plant-detail").classList.add("hidden");

  // Reset nav highlights
  document.querySelectorAll("#main-nav .nav-link").forEach(btn => {
    btn.className = "nav-link font-label-md text-sm text-slate-600 hover:text-slate-900 hover:bg-slate-100 px-4 py-1.5 rounded-full transition-all whitespace-nowrap cursor-pointer";
  });

  if (view === "landing") {
    document.getElementById("view-landing").classList.remove("hidden");
    const el = document.getElementById("nav-landing");
    if (el) el.className = "nav-link bg-emerald-800 text-white font-label-md text-sm rounded-full px-4 py-1.5 shadow-sm transition-all whitespace-nowrap cursor-pointer";
  } else if (view === "discovery") {
    document.getElementById("view-discovery").classList.remove("hidden");
    const el = document.getElementById("nav-discovery");
    if (el) el.className = "nav-link bg-emerald-800 text-white font-label-md text-sm rounded-full px-4 py-1.5 shadow-sm transition-all whitespace-nowrap cursor-pointer";
  } else if (view === "garden") {
    document.getElementById("view-garden").classList.remove("hidden");
    const el = document.getElementById("nav-garden");
    if (el) el.className = "nav-link bg-emerald-800 text-white font-label-md text-sm rounded-full px-4 py-1.5 shadow-sm transition-all whitespace-nowrap cursor-pointer";
    loadGarden();
  } else if (view === "plant-detail") {
    document.getElementById("view-plant-detail").classList.remove("hidden");
  }

  window.scrollTo({ top: 0, behavior: "smooth" });
}

// User & Auth Management
async function fetchCurrentUser() {
  try {
    const res = await fetch(`${API}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (res.ok) {
      currentUser = await res.json();
      renderHeaderAuth();
      loadGardenCount();
    } else {
      logout();
    }
  } catch (err) {
    logout();
  }
}

function renderHeaderAuth() {
  const container = document.getElementById("auth-header-container");
  if (currentUser) {
    const username = currentUser.email.split('@')[0];
    container.innerHTML = `
      <div class="flex items-center gap-2">
        <span class="text-xs text-slate-700 font-semibold bg-slate-100 border border-slate-200 px-3 py-1 rounded-full flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full bg-emerald-600"></span>
          <span>${username}</span>
        </span>
        <button class="text-slate-400 hover:text-slate-700 text-xs p-1 cursor-pointer" onclick="logout()" title="Sign Out">
          <span class="material-symbols-outlined text-[18px]">logout</span>
        </button>
      </div>
    `;
  } else {
    container.innerHTML = `
      <button class="py-1.5 px-4 rounded-full bg-emerald-800 hover:bg-emerald-700 text-white text-xs font-semibold shadow-sm transition-all flex items-center gap-1 cursor-pointer" onclick="openAuthModal('login')">
        <span class="material-symbols-outlined text-[16px]">login</span>
        <span>Sign In</span>
      </button>
    `;
  }
}

function logout() {
  localStorage.removeItem("plantmyplanet_token");
  token = null;
  currentUser = null;
  renderHeaderAuth();
  document.getElementById("garden-count").innerText = "0";
  navigateTo("landing");
}

function openAuthModal(mode) {
  authMode = mode;
  setAuthMode(mode);
  document.getElementById("modal-auth").classList.remove("hidden");
}

function closeAuthModal() {
  document.getElementById("modal-auth").classList.add("hidden");
}

function setAuthMode(mode) {
  authMode = mode;
  document.getElementById("auth-modal-title").innerText = mode === "login" ? "Sign In to PlantMyPlanet" : "Create a PlantMyPlanet Account";
  document.getElementById("auth-submit-text").innerText = mode === "login" ? "Sign In" : "Register & Continue";
  document.getElementById("auth-tab-login").className = mode === "login" ? "flex-1 py-1.5 rounded-full bg-emerald-800 text-white text-xs font-semibold transition-all cursor-pointer" : "flex-1 py-1.5 rounded-full bg-slate-100 text-slate-700 hover:bg-slate-200 text-xs font-semibold transition-all cursor-pointer";
  document.getElementById("auth-tab-register").className = mode === "register" ? "flex-1 py-1.5 rounded-full bg-emerald-800 text-white text-xs font-semibold transition-all cursor-pointer" : "flex-1 py-1.5 rounded-full bg-slate-100 text-slate-700 hover:bg-slate-200 text-xs font-semibold transition-all cursor-pointer";
  document.getElementById("auth-error-msg").classList.add("hidden");
}

async function handleAuthSubmit(e) {
  e.preventDefault();
  const email = document.getElementById("auth-email-input").value.trim();
  const password = document.getElementById("auth-password-input").value;
  const errorEl = document.getElementById("auth-error-msg");
  const spinner = document.getElementById("auth-submit-spinner");
  const btnText = document.getElementById("auth-submit-text");

  errorEl.classList.add("hidden");
  spinner.classList.remove("hidden");
  btnText.classList.add("hidden");

  try {
    const endpoint = authMode === "login" ? `${API}/auth/login` : `${API}/auth/register`;
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Authentication error");
    }

    token = data.access_token;
    localStorage.setItem("plantmyplanet_token", token);
    currentUser = data.user;
    closeAuthModal();
    renderHeaderAuth();
    loadGardenCount();

    if (pendingPlant) {
      openConfirmModal(pendingPlant);
      pendingPlant = null;
    }
  } catch (err) {
    errorEl.innerText = err.message;
    errorEl.classList.remove("hidden");
  } finally {
    spinner.classList.add("hidden");
    btnText.classList.remove("hidden");
  }
}

// GPS / Location
function detectGPSLocation() {
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        document.getElementById("input-lat").value = pos.coords.latitude.toFixed(4);
        document.getElementById("input-lon").value = pos.coords.longitude.toFixed(4);
        loadRecommendations(true);
      },
      () => alert("Unable to detect coordinates. Using default location.")
    );
  }
}

function selectScale(btn) {
  document.querySelectorAll("#landing-scale-pills .scale-pill").forEach(b => {
    b.className = "scale-pill py-2 px-2 text-center rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 text-xs font-semibold transition-all cursor-pointer";
  });
  btn.className = "scale-pill py-2 px-2 text-center rounded-lg bg-emerald-800 text-white text-xs font-semibold shadow-sm transition-all cursor-pointer";
  selectedScale = btn.dataset.scale;
}

// Plant Discovery
async function loadRecommendations(navigateToDiscovery = false) {
  const lat = parseFloat(document.getElementById("input-lat").value);
  const lon = parseFloat(document.getElementById("input-lon").value);

  // Update header text strictly on 1 line
  document.getElementById("header-coords").innerText = `${lat.toFixed(2)}° N, ${lon.toFixed(2)}° E`;
  document.getElementById("discovery-loc-label").innerText = `Active Coordinates: ${lat.toFixed(2)}° N, ${lon.toFixed(2)}° E`;

  const spinner = document.getElementById("btn-explore-spinner");
  const btnText = document.getElementById("btn-explore-text");
  if (spinner && btnText) {
    spinner.classList.remove("hidden");
    btnText.innerText = "Analyzing Microclimate...";
  }

  const grid = document.getElementById("discovery-crops-grid");
  if (grid) {
    grid.innerHTML = `
      <div class="col-span-full py-16 text-center text-slate-500">
        <div class="inline-block w-8 h-8 border-3 border-emerald-600/30 border-t-emerald-700 rounded-full animate-spin mb-3"></div>
        <p class="text-sm font-semibold text-slate-800">Calibrating Soil Profile & Climate Suitability...</p>
        <p class="text-xs text-slate-400 mt-1">Cross-referencing soil chemistry, rainfall tolerance, and temperature windows.</p>
      </div>
    `;
  }

  try {
    const res = await fetch(`${API}/discovery/recommendations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ latitude: lat, longitude: lon, category: null, limit: 30 })
    });
    currentCrops = await res.json();
    renderDiscoveryCrops(currentCrops);

    // If first crop exists, open in side panel by default
    if (currentCrops.length > 0) {
      inspectCropDetails(currentCrops[0].ecoport_code);
    }

    if (navigateToDiscovery) {
      navigateTo("discovery");
    }
  } catch (err) {
    if (grid) {
      grid.innerHTML = `<div class="col-span-full py-8 text-center text-rose-600 text-xs">Failed to calculate crop recommendations. Please verify coordinates.</div>`;
    }
  } finally {
    if (spinner && btnText) {
      spinner.classList.add("hidden");
      btnText.innerText = "Explore Location Recommendations";
    }
  }
}

function selectCategory(cat, btn) {
  selectedCategory = cat;
  document.querySelectorAll("#discovery-categories-bar .cat-pill").forEach(b => {
    b.className = "cat-pill px-3.5 py-1 rounded-full bg-slate-100 text-slate-700 hover:bg-slate-200 text-xs font-semibold transition-all cursor-pointer whitespace-nowrap";
  });
  btn.className = "cat-pill px-3.5 py-1 rounded-full bg-emerald-800 text-white text-xs font-semibold shadow-sm transition-all cursor-pointer whitespace-nowrap";
  filterDiscoveryCrops();
}

function filterDiscoveryCrops() {
  const query = (document.getElementById("search-crop-input")?.value || "").toLowerCase().trim();
  const filtered = currentCrops.filter(c => {
    const nameMatch = c.scientific_name.toLowerCase().includes(query) || (c.common_name && c.common_name.toLowerCase().includes(query));
    const catMatch = selectedCategory === "all" || (c.category && c.category.toLowerCase().includes(selectedCategory));
    return nameMatch && catMatch;
  });
  renderDiscoveryCrops(filtered);
}

function formatWhereToGrow(val) {
  if (!val) return "Garden Beds, Containers, Raised Planters";
  const lower = val.toLowerCase();
  if (lower.includes("small scale")) return "Home Garden Beds, Raised Beds, Large Patio Containers";
  if (lower.includes("wild")) return "Open Garden Beds, Naturalized Borders, Semi-Shaded Ground";
  if (lower.includes("home garden")) return "Home Beds, Kitchen Gardens, Patio Planters";
  return val.split(',').map(s => s.trim()).map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(', ');
}

function formatLifeForm(val) {
  if (!val) return "Herbaceous Plant";
  const lower = val.toLowerCase();
  if (lower.includes("herb")) return "Herb (Soft-stemmed)";
  if (lower.includes("shrub")) return "Shrub (Woody / Bush)";
  if (lower.includes("tree")) return "Tree (Arboreal)";
  if (lower.includes("vine") || lower.includes("climber")) return "Vine / Climber";
  if (lower.includes("grass")) return "Grass / Groundcover";
  return val.charAt(0).toUpperCase() + val.slice(1);
}

function formatLifeSpan(val) {
  if (!val) return "Perennial (Multi-Year)";
  const lower = val.toLowerCase();
  if (lower.includes("annual")) return "Annual (Single Season)";
  if (lower.includes("biennial")) return "Biennial (Two Seasons)";
  if (lower.includes("perennial")) return "Perennial (Multi-Year)";
  return val.charAt(0).toUpperCase() + val.slice(1);
}

function formatHabit(val) {
  if (!val) return "Erect / Upright";
  const lower = val.toLowerCase();
  if (lower.includes("erect")) return "Erect / Upright";
  if (lower.includes("spread")) return "Spreading / Bushy";
  if (lower.includes("climb")) return "Climbing / Trellised";
  if (lower.includes("prostrate") || lower.includes("creep")) return "Creeping / Ground Cover";
  return val.charAt(0).toUpperCase() + val.slice(1);
}

function renderDiscoveryCrops(crops) {
  const grid = document.getElementById("discovery-crops-grid");
  if (!grid) return;

  if (!crops || crops.length === 0) {
    grid.innerHTML = `<div class="col-span-full py-12 text-center text-slate-400 text-xs">No crops match the selected category. Try selecting 'All Crops' or another search query.</div>`;
    return;
  }

  grid.innerHTML = crops.map(crop => {
    const comName = crop.common_name ? crop.common_name.split(",")[0].trim() : crop.scientific_name;
    const cat = crop.category || "General Crop";
    const days = crop.growing_days_max ? `${crop.growing_days_min || "?"}–${crop.growing_days_max} Days` : "Varies";
    const lifeForm = formatLifeForm(crop.life_form);
    const habit = formatHabit(crop.growth_habit || crop.life_span);

    const optimalTags = (crop.optimal_matches || []).slice(0, 2).map(m => `
      <span class="px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-[11px] font-medium">✓ ${m}</span>
    `).join("");

    return `
      <div class="group relative flex flex-col bg-white rounded-xl p-4 shadow-sm hover:shadow-md border border-slate-200 transition-all duration-200 cursor-pointer" onclick="inspectCropDetails(${crop.ecoport_code})">
        <div class="flex items-start justify-between gap-2">
          <div class="flex flex-col">
            <div class="flex items-center gap-1.5 flex-wrap">
              <span class="text-[10px] font-bold uppercase tracking-wider text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">${lifeForm}</span>
              <span class="text-[10px] text-slate-500">• ${habit}</span>
            </div>
            <h3 class="font-headline-sm text-base font-bold text-slate-900 group-hover:text-emerald-800 transition-colors mt-1">${comName}</h3>
            <span class="text-xs text-slate-500 italic font-display">${crop.scientific_name}</span>
          </div>
          <span class="px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 text-xs font-bold flex items-center gap-1 flex-shrink-0">
            <span class="material-symbols-outlined text-[13px]">verified</span> ${crop.suitability_score}%
          </span>
        </div>

        <div class="flex items-center gap-1.5 my-3 flex-wrap">
          <span class="px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200 text-[11px] font-semibold">${days}</span>
          ${optimalTags}
        </div>

        <div class="mt-auto pt-2.5 flex items-center justify-between gap-2 border-t border-slate-100">
          <button class="flex-1 py-1.5 rounded-full bg-emerald-800 hover:bg-emerald-700 text-white text-xs font-semibold shadow-sm transition-all flex items-center justify-center gap-1 cursor-pointer" onclick="event.stopPropagation(); onPlantItToday(${crop.ecoport_code})">
            <span class="material-symbols-outlined text-[15px]">psychiatry</span>
            <span>Plant It Today</span>
          </button>
          <button class="px-3 py-1.5 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 text-xs font-semibold transition-colors cursor-pointer" onclick="event.stopPropagation(); inspectCropDetails(${crop.ecoport_code})">
            Details
          </button>
        </div>
      </div>
    `;
  }).join("");
}

// Side Panel: Detailed Crop Inspection (Rich Botanical Attributes)
async function inspectCropDetails(ecoportCode) {
  const panel = document.getElementById("side-panel-content");
  if (!panel) return;

  panel.innerHTML = `
    <div class="py-12 text-center text-slate-400">
      <div class="inline-block w-6 h-6 border-2 border-emerald-600/30 border-t-emerald-700 rounded-full animate-spin mb-2"></div>
      <p class="text-xs font-semibold">Loading complete botanical attributes...</p>
    </div>
  `;

  try {
    const res = await fetch(`${API}/discovery/crops/${ecoportCode}`);
    const crop = await res.json();
    activeCropDetail = crop;

    const comName = crop.common_name ? crop.common_name.split(",")[0].trim() : crop.scientific_name;
    const lifeForm = formatLifeForm(crop.life_form);
    const habit = formatHabit(crop.growth_habit);
    const lifespan = formatLifeSpan(crop.life_span);
    const whereToGrow = formatWhereToGrow(crop.where_to_grow);
    const soilDepth = crop.soil_depth || "Medium root system (50–150 cm)";
    const tolerance = crop.abiotic_tolerance || "Standard moisture & temperature resilience";

    panel.innerHTML = `
      <div>
        <!-- Category & Suitability Header -->
        <div class="flex items-center justify-between gap-2 pb-2.5 border-b border-slate-100 mb-3">
          <span class="text-[11px] uppercase tracking-wider text-emerald-800 font-bold bg-emerald-50 px-2.5 py-0.5 rounded border border-emerald-200">
            ${crop.category || 'Botanical Cultivar'}
          </span>
          <span class="px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 text-xs font-bold">
            ${crop.suitability_score}% Match
          </span>
        </div>

        <h2 class="font-headline-lg text-2xl font-bold text-slate-900 tracking-tight leading-tight">${comName}</h2>
        <p class="font-display italic text-xs text-slate-500 mb-3">${crop.scientific_name}</p>

        <!-- SECTION 1: BOTANICAL CLASSIFICATION & MORPHOLOGY -->
        <div class="mb-3.5 p-3.5 rounded-xl bg-slate-50 border border-slate-200">
          <div class="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2.5 flex items-center gap-1.5">
            <span class="material-symbols-outlined text-[14px] text-emerald-700">nature</span>
            <span>Botanical Morphology & Type</span>
          </div>
          <div class="grid grid-cols-2 gap-2.5 text-xs">
            <div class="bg-white p-2 rounded-lg border border-slate-200">
              <span class="text-slate-400 block text-[10px] uppercase font-semibold">Plant Type / Form</span>
              <strong class="text-slate-800 font-bold mt-0.5 block">${lifeForm}</strong>
            </div>
            <div class="bg-white p-2 rounded-lg border border-slate-200">
              <span class="text-slate-400 block text-[10px] uppercase font-semibold">Growth Habit</span>
              <strong class="text-slate-800 font-bold mt-0.5 block">${habit}</strong>
            </div>
            <div class="bg-white p-2 rounded-lg border border-slate-200">
              <span class="text-slate-400 block text-[10px] uppercase font-semibold">Lifecycle Span</span>
              <strong class="text-slate-800 font-bold mt-0.5 block">${lifespan}</strong>
            </div>
            <div class="bg-white p-2 rounded-lg border border-slate-200">
              <span class="text-slate-400 block text-[10px] uppercase font-semibold">Root Depth</span>
              <strong class="text-slate-800 font-bold mt-0.5 block">${soilDepth}</strong>
            </div>
          </div>
        </div>

        <!-- SECTION 2: WHERE TO GROW & BEST SETUP -->
        <div class="mb-3.5 p-3.5 rounded-xl bg-emerald-50/60 border border-emerald-200">
          <div class="text-[10px] font-bold uppercase tracking-wider text-emerald-800 mb-1 flex items-center gap-1.5">
            <span class="material-symbols-outlined text-[14px]">potted_plant</span>
            <span>Where to Grow & Cultivation Setting</span>
          </div>
          <p class="text-xs text-slate-800 font-medium leading-relaxed">${whereToGrow}</p>
        </div>

        <!-- SECTION 3: ENVIRONMENTAL REQUIREMENTS (Varied High Contrast Chips) -->
        <div class="grid grid-cols-2 gap-2 my-3">
          <div class="bg-amber-50/80 border border-amber-200 p-2.5 rounded-lg flex flex-col">
            <span class="text-[10px] uppercase tracking-wider text-amber-700 font-bold">🌡️ Optimal Temp</span>
            <span class="text-xs font-bold text-slate-900 mt-0.5">${crop.temperature_range || '15–30 °C'}</span>
          </div>
          <div class="bg-purple-50/80 border border-purple-200 p-2.5 rounded-lg flex flex-col">
            <span class="text-[10px] uppercase tracking-wider text-purple-700 font-bold">🧪 Soil pH Range</span>
            <span class="text-xs font-bold text-slate-900 mt-0.5">${crop.ph_range || '5.5–7.5'}</span>
          </div>
          <div class="bg-sky-50/80 border border-sky-200 p-2.5 rounded-lg flex flex-col">
            <span class="text-[10px] uppercase tracking-wider text-sky-700 font-bold">💧 Annual Rainfall</span>
            <span class="text-xs font-bold text-slate-900 mt-0.5">${crop.rainfall_range || '500–1200 mm'}</span>
          </div>
          <div class="bg-orange-50/80 border border-orange-200 p-2.5 rounded-lg flex flex-col">
            <span class="text-[10px] uppercase tracking-wider text-orange-700 font-bold">☀️ Sunlight</span>
            <span class="text-xs font-bold text-slate-900 mt-0.5">${crop.light || 'Bright indirect to full sun'}</span>
          </div>
        </div>

        <!-- SECTION 4: SOIL TEXTURE, FERTILITY & DRAINAGE -->
        <div class="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 flex flex-col gap-1.5 my-3">
          <div class="flex items-center justify-between pb-1 border-b border-slate-200/60">
            <span class="text-slate-400">Texture:</span>
            <strong class="text-slate-800 capitalize">${crop.soil_texture || 'Loam / Sand'}</strong>
          </div>
          <div class="flex items-center justify-between pb-1 border-b border-slate-200/60">
            <span class="text-slate-400">Fertility Requirement:</span>
            <strong class="text-slate-800 capitalize">${crop.soil_fertility || 'Moderate'}</strong>
          </div>
          <div class="flex items-center justify-between pb-1 border-b border-slate-200/60">
            <span class="text-slate-400">Drainage:</span>
            <strong class="text-slate-800 capitalize">${crop.soil_drainage || 'Well-drained'}</strong>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-slate-400">Resilience:</span>
            <strong class="text-slate-800 capitalize">${tolerance}</strong>
          </div>
        </div>

        <!-- ACTION -->
        <button class="w-full mt-2 py-3 rounded-full bg-emerald-800 hover:bg-emerald-700 text-white text-xs font-semibold shadow-sm transition-all flex items-center justify-center gap-2 cursor-pointer" onclick="onPlantItToday(${crop.ecoport_code})">
          <span class="material-symbols-outlined text-[17px]">psychiatry</span>
          <span>Plant It Today</span>
        </button>
      </div>
    `;
  } catch (err) {
    panel.innerHTML = `<div class="text-rose-600 text-center py-6 text-xs">Failed to load detailed specs.</div>`;
  }
}

// "Plant It Today" Workflow
function onPlantItToday(ecoportCode) {
  const crop = currentCrops.find(c => c.ecoport_code === ecoportCode) || activeCropDetail || { ecoport_code: ecoportCode, scientific_name: `Crop #${ecoportCode}` };

  if (!currentUser) {
    pendingPlant = crop;
    openAuthModal("login");
    return;
  }

  openConfirmModal(crop);
}

function openConfirmModal(crop) {
  const comName = crop.common_name ? crop.common_name.split(",")[0].trim() : crop.scientific_name;
  document.getElementById("confirm-crop-common").innerText = comName;
  document.getElementById("confirm-crop-sci").innerText = crop.scientific_name;
  document.getElementById("modal-confirm-plant").dataset.ecoportCode = crop.ecoport_code;
  document.getElementById("confirm-scale-select").value = selectedScale;
  document.getElementById("modal-confirm-plant").classList.remove("hidden");
}

function closeConfirmModal() {
  document.getElementById("modal-confirm-plant").classList.add("hidden");
}

async function handleConfirmPlantingSubmit(e) {
  e.preventDefault();
  const ecoportCode = parseInt(document.getElementById("modal-confirm-plant").dataset.ecoportCode);
  const scale = document.getElementById("confirm-scale-select").value;
  const plantingDate = document.getElementById("confirm-date-input").value;
  const lat = parseFloat(document.getElementById("input-lat").value);
  const lon = parseFloat(document.getElementById("input-lon").value);

  const spinner = document.getElementById("confirm-submit-spinner");
  const btnText = document.getElementById("confirm-submit-text");
  spinner.classList.remove("hidden");
  btnText.innerText = "Generating Personalized Plan...";

  try {
    const res = await fetch(`${API}/plantings`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({
        ecoport_code: ecoportCode,
        planting_date: plantingDate,
        latitude: lat,
        longitude: lon,
        growing_scale: scale
      })
    });
    const newPlanting = await res.json();
    if (!res.ok) throw new Error(newPlanting.detail || "Planting failed");

    closeConfirmModal();
    loadGardenCount();
    openPlantDashboard(newPlanting.id);
  } catch (err) {
    alert(`Could not create planting: ${err.message}`);
  } finally {
    spinner.classList.add("hidden");
    btnText.innerText = "Confirm & Generate Personalized Plan";
  }
}

// Screen 3: My Garden
async function loadGardenCount() {
  if (!token) return;
  try {
    const res = await fetch(`${API}/plantings`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (res.ok) {
      const list = await res.json();
      document.getElementById("garden-count").innerText = list.length;
      const statActive = document.getElementById("stat-active-count");
      if (statActive) statActive.innerText = list.length;
    }
  } catch (err) {}
}

async function loadGarden() {
  const grid = document.getElementById("garden-grid");
  if (!grid) return;

  grid.innerHTML = `
    <div class="col-span-full py-16 text-center text-slate-500">
      <div class="inline-block w-8 h-8 border-3 border-emerald-600/30 border-t-emerald-700 rounded-full animate-spin mb-2"></div>
      <p class="text-sm font-semibold text-slate-800">Loading active plantings...</p>
    </div>
  `;

  const sortBy = document.getElementById("garden-sort-select")?.value || "planting_date";

  try {
    const res = await fetch(`${API}/plantings?sort_by=${sortBy}&order=desc`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const plantings = await res.json();

    if (!plantings || plantings.length === 0) {
      grid.innerHTML = `
        <div class="col-span-full py-16 px-6 text-center bg-white rounded-xl border border-slate-200">
          <span class="material-symbols-outlined text-4xl text-slate-400 mb-2">eco</span>
          <h3 class="font-headline-sm text-lg font-bold text-slate-900">No Plants in Your Garden Yet</h3>
          <p class="text-slate-500 text-xs max-w-sm mx-auto my-2.5">
            Explore climate-matched crops for your location and select "Plant It Today" to generate your first AI lifecycle timeline.
          </p>
          <button class="py-2 px-5 rounded-full bg-emerald-800 hover:bg-emerald-700 text-white text-xs font-semibold shadow-sm transition-all cursor-pointer" onclick="navigateTo('discovery')">
            Explore Suitable Plants
          </button>
        </div>
      `;
      return;
    }

    grid.innerHTML = plantings.map(p => {
      const comName = p.common_name ? p.common_name.split(",")[0].trim() : p.scientific_name;
      const harvestDate = p.estimated_harvest_date ? new Date(p.estimated_harvest_date).toLocaleDateString() : "Calculating";

      return `
        <div class="bg-white rounded-xl p-4 border border-slate-200 shadow-sm hover:shadow-md transition-all flex flex-col justify-between">
          <div>
            <div class="flex items-start justify-between gap-2">
              <div>
                <h3 class="font-headline-sm text-base font-bold text-slate-900">${comName}</h3>
                <span class="text-xs text-slate-500 italic font-display">${p.scientific_name}</span>
              </div>
              <span class="px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 text-xs font-bold">
                Day ${p.days_elapsed}
              </span>
            </div>

            <div class="bg-slate-50 p-3 rounded-lg my-3 border border-slate-200">
              <div class="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Current Stage</div>
              <div class="font-title-md font-bold text-emerald-800 text-xs mt-0.5">${p.current_stage_name}</div>
              <div class="text-xs text-slate-600 mt-2 flex items-center gap-1">
                <span class="material-symbols-outlined text-[14px] text-amber-600">checklist</span>
                <span><strong>Next:</strong> ${p.next_activity}</span>
              </div>
            </div>

            <div class="flex items-center justify-between text-xs text-slate-500">
              <span>Harvest: <strong class="text-slate-900">${harvestDate}</strong></span>
              <span>Completed: <strong class="text-emerald-700">${p.completed_stages_count}/${p.total_stages_count}</strong></span>
            </div>
          </div>

          <button class="w-full mt-3.5 py-2 rounded-full bg-emerald-800 hover:bg-emerald-700 text-white text-xs font-semibold shadow-sm transition-all flex items-center justify-center gap-1 cursor-pointer" onclick="openPlantDashboard('${p.id}')">
            <span>Open Dashboard & AI Advisor</span>
            <span class="material-symbols-outlined text-[15px]">arrow_forward</span>
          </button>
        </div>
      `;
    }).join("");
  } catch (err) {
    grid.innerHTML = `<div class="col-span-full py-8 text-center text-rose-600 text-xs">Could not load garden records.</div>`;
  }
}

function filterGardenPlantings() {
  const query = (document.getElementById("garden-search-input")?.value || "").toLowerCase().trim();
  document.querySelectorAll("#garden-grid > div").forEach(card => {
    const text = card.innerText.toLowerCase();
    card.style.display = text.includes(query) ? "flex" : "none";
  });
}

// Screen 4: Plant Dashboard & AI Companion
async function openPlantDashboard(plantingId) {
  navigateTo("plant-detail");

  try {
    const res = await fetch(`${API}/plantings/${plantingId}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    activePlanting = await res.json();
    renderPlantDashboardDetails(activePlanting);
    loadChatMessages(activePlanting.id);
  } catch (err) {
    alert("Could not load plant details.");
  }
}

function renderPlantDashboardDetails(p) {
  const comName = p.common_name ? p.common_name.split(",")[0].trim() : p.scientific_name;
  document.getElementById("detail-breadcrumb-name").innerText = `${comName} (Day ${p.days_elapsed})`;
  document.getElementById("detail-crop-name").innerText = comName;
  document.getElementById("detail-sci-name").innerText = p.scientific_name;
  document.getElementById("detail-growing-scale").innerText = p.growing_scale.replace('_', ' ').toUpperCase();
  document.getElementById("detail-days-elapsed").innerText = `Day ${p.days_elapsed}`;
  document.getElementById("detail-est-harvest").innerText = p.estimated_harvest_date ? `Harvest: ${new Date(p.estimated_harvest_date).toLocaleDateString()}` : "Harvest: Calculating";

  const plan = p.active_plan;
  document.getElementById("detail-plan-summary").innerText = plan ? plan.summary : "Personalized Growth Timeline";

  // Render Stages
  const stagesContainer = document.getElementById("detail-stages-container");
  const stages = plan ? plan.stages : [];

  stagesContainer.innerHTML = stages.map(s => {
    const isCurrent = s.start_day <= p.days_elapsed && p.days_elapsed <= s.end_day && !s.is_completed;
    const tasksHtml = (s.care_tasks || []).map(t => `
      <li class="flex items-start gap-2 text-xs">
        <input type="checkbox" id="task-${t.id}" ${t.is_completed ? "checked" : ""} onchange="toggleTask('${t.id}', this.checked)" class="mt-0.5 accent-emerald-700 w-3.5 h-3.5 rounded cursor-pointer">
        <label for="task-${t.id}" class="${t.is_completed ? 'line-through text-slate-400' : 'text-slate-800'} cursor-pointer">
          <strong>${t.task_name}</strong> (${t.frequency}) — <span class="text-slate-600">${t.description}</span>
        </label>
      </li>
    `).join("");

    return `
      <div class="rounded-xl p-4 border ${isCurrent ? 'border-emerald-600 bg-emerald-50/40 shadow-sm ring-1 ring-emerald-500/20' : 'border-slate-200 bg-white'} transition-all">
        <div class="flex items-center justify-between gap-2 pb-2 border-b border-slate-100">
          <div class="flex items-center gap-2">
            <input type="checkbox" id="stage-${s.id}" ${s.is_completed ? "checked" : ""} onchange="toggleStage('${s.id}', this.checked)" class="accent-emerald-700 w-4 h-4 rounded cursor-pointer">
            <div>
              <h4 class="font-headline-sm text-sm font-bold text-slate-900 ${s.is_completed ? 'line-through text-slate-400' : ''}">
                Stage ${s.stage_order}: ${s.stage_name}
              </h4>
              <span class="text-[11px] text-slate-500">Days ${s.start_day}–${s.end_day}</span>
            </div>
          </div>
          ${isCurrent ? '<span class="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 text-[10px] font-bold uppercase tracking-wider">CURRENT STAGE</span>' : (s.is_completed ? '<span class="text-xs text-emerald-700 font-bold flex items-center gap-1">✓ Completed</span>' : '')}
        </div>

        <p class="text-xs text-slate-600 my-2 leading-relaxed">${s.description}</p>

        <div class="mt-2.5">
          <div class="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">Actionable Care Checklist:</div>
          <ul class="flex flex-col gap-1.5">${tasksHtml}</ul>
        </div>
      </div>
    `;
  }).join("");

  // Render Observations
  renderObservationsList(p.observations || []);
}

function renderObservationsList(obsList) {
  const list = document.getElementById("detail-observations-list");
  if (!list) return;

  if (obsList.length === 0) {
    list.innerHTML = `<p class="text-xs text-slate-400 italic">No field observations recorded yet. Add your first note above!</p>`;
    return;
  }

  list.innerHTML = obsList.map(o => `
    <div class="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-800">
      <span class="text-emerald-700 font-semibold">${o.observation_date}:</span> ${o.note}
    </div>
  `).join("");
}

async function handleObservationSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("input-new-observation");
  const note = input.value.trim();
  if (!note || !activePlanting) return;

  try {
    const res = await fetch(`${API}/plantings/${activePlanting.id}/observations`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ note })
    });
    if (res.ok) {
      input.value = "";
      openPlantDashboard(activePlanting.id);
    }
  } catch (err) {}
}

function focusObservationInput() {
  document.getElementById("input-new-observation")?.focus();
}

async function retryPlantPlan() {
  if (!activePlanting) return;
  if (!confirm("Recalculate personalized lifecycle timeline with the latest weather and observation inputs?")) return;

  try {
    const res = await fetch(`${API}/plantings/${activePlanting.id}/retry-plan`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` }
    });
    if (res.ok) {
      openPlantDashboard(activePlanting.id);
    }
  } catch (err) {
    alert("Could not recalculate plan.");
  }
}

// Stage & Task Toggles
async function toggleStage(stageId, completed) {
  try {
    await fetch(`${API}/plantings/stages/${stageId}/complete?completed=${completed}`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}` }
    });
    loadGardenCount();
  } catch (err) {}
}

async function toggleTask(taskId, completed) {
  try {
    await fetch(`${API}/plantings/tasks/${taskId}/complete?completed=${completed}`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}` }
    });
  } catch (err) {}
}

// AI Botanical Chat Markdown Helper
function formatAssistantMessage(content) {
  if (!content) return "";
  try {
    if (window.marked && typeof window.marked.parse === "function") {
      return window.marked.parse(content);
    }
  } catch (e) {
    console.error("Marked render error:", e);
  }
  // Deterministic Markdown fallback
  return content
    .replace(/^### (.*$)/gim, '<h3 class="font-bold text-slate-900 mt-2 mb-1">$1</h3>')
    .replace(/^## (.*$)/gim, '<h2 class="font-bold text-slate-900 mt-2 mb-1">$1</h2>')
    .replace(/^# (.*$)/gim, '<h1 class="font-bold text-slate-900 mt-2 mb-1">$1</h1>')
    .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/gim, '<em>$1</em>')
    .replace(/^- (.*$)/gim, '<li class="ml-4 list-disc">$1</li>')
    .replace(/\n/gim, '<br/>');
}

// AI Companion Chat Stream (With Markdown Rendering)
async function loadChatMessages(plantingId) {
  const stream = document.getElementById("chat-stream");
  if (!stream) return;

  try {
    const res = await fetch(`${API}/plantings/${plantingId}/chat`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    const messages = await res.json();

    if (!messages || messages.length === 0) {
      stream.innerHTML = `
        <div class="self-start max-w-[90%] p-3.5 rounded-2xl bg-slate-100 text-slate-800 text-xs border border-slate-200 rounded-tl-sm">
          Hello! I am your PlantMyPlanet Botanical Advisor. I have calibrated my guidance to your plant's active growth stage (Day ${activePlanting?.days_elapsed || 0}) and local microclimate. How can I assist you?
        </div>
      `;
      return;
    }

    stream.innerHTML = messages.map(m => {
      const isUser = m.role === "user";
      if (isUser) {
        return `
          <div class="self-end max-w-[85%] p-3 rounded-2xl bg-emerald-800 text-white text-xs rounded-tr-sm">
            ${m.content}
          </div>
        `;
      } else {
        const html = formatAssistantMessage(m.content);
        return `
          <div class="self-start max-w-[90%] p-3.5 rounded-2xl bg-slate-50 text-slate-900 border border-slate-200 rounded-tl-sm text-xs shadow-xs chat-markdown">
            ${html}
          </div>
        `;
      }
    }).join("");

    stream.scrollTop = stream.scrollHeight;
  } catch (err) {}
}

function askPresetQuestion(text) {
  const input = document.getElementById("chat-user-input");
  if (input) {
    input.value = text;
    document.getElementById("chat-submit-btn").click();
  }
}

async function handleChatSubmit(e) {
  e.preventDefault();
  const input = document.getElementById("chat-user-input");
  const msg = input.value.trim();
  if (!msg || !activePlanting) return;

  const stream = document.getElementById("chat-stream");

  // Append user message immediately
  stream.innerHTML += `
    <div class="self-end max-w-[85%] p-3 rounded-2xl bg-emerald-800 text-white text-xs rounded-tr-sm">
      ${msg}
    </div>
  `;
  input.value = "";
  stream.scrollTop = stream.scrollHeight;

  // Append thinking bubble
  const placeholderId = `ai-bubble-${Date.now()}`;
  stream.innerHTML += `
    <div class="self-start max-w-[90%] p-3 rounded-2xl bg-slate-50 text-slate-800 text-xs border border-slate-200 rounded-tl-sm flex items-center gap-2" id="${placeholderId}">
      <span class="inline-block w-3 h-3 border-2 border-emerald-600/30 border-t-emerald-700 rounded-full animate-spin"></span>
      <span class="text-slate-400">Consulting agronomic knowledge base...</span>
    </div>
  `;
  stream.scrollTop = stream.scrollHeight;

  try {
    const res = await fetch(`${API}/plantings/${activePlanting.id}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ message: msg })
    });
    const data = await res.json();
    const bubble = document.getElementById(placeholderId);
    if (bubble) {
      const html = formatAssistantMessage(data.content);
      bubble.className = "self-start max-w-[90%] p-3.5 rounded-2xl bg-slate-50 text-slate-900 border border-slate-200 rounded-tl-sm text-xs shadow-xs chat-markdown";
      bubble.innerHTML = html;
    }
  } catch (err) {
    const bubble = document.getElementById(placeholderId);
    if (bubble) {
      bubble.innerText = "Apologies, I encountered a connection issue. Please retry your question.";
    }
  } finally {
    stream.scrollTop = stream.scrollHeight;
  }
}
