// ForecastBridge front end.
// Open the browser's DevTools console (Cmd+Option+J) to see errors and console.log output.

const statusEl = document.getElementById("status");
const searchInput = document.getElementById("place-search");
const resultsList = document.getElementById("place-results");
const featuredNav = document.getElementById("featured");
const placeLabel = document.getElementById("place-label");

// A place is { name, label, timezone, ... } as sent by /locations and /places.
// `name` goes in API calls ("london" or "place-2654710"), `label` is shown to people.
const DEFAULT_PLACE_NAME = "london";             // first visit, or if the saved place stops working
const STORAGE_KEY = "forecastbridge:lastPlace";  // where the last viewed place is remembered
let currentPlace = null;
const nowButton = document.getElementById("now-button");
let chart = null; // the Chart.js chart, kept so we can update it when the location changes

// How long the "Now" highlight stays, and how long it takes to fade out (milliseconds)
const NOW_SHOW_MS = 2500;
const NOW_FADE_MS = 600;
let nowTimer = null;     // the setTimeout that starts the fade
let nowAnimation = null; // the requestAnimationFrame running the fade

// Where "now" is on the chart and how visible its line is (0 = hidden, 1 = fully shown).
// Kept in our own variable, not chart.options: Chart.js only re-reads options on chart.update(),
// so a fade that changed chart.options and called chart.draw() kept drawing the old opacity.
const nowHighlight = { index: null, opacity: 0 };

const chartScroll = document.getElementById("chart-scroll");

function showStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

// --- Remembering the last place ------------------------------------------------
// localStorage can be unavailable (private browsing, blocked storage), so every access is wrapped.

function savePlace(place) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(place));
  } catch {
    // Not remembering the place is fine; the page still works
  }
}

function readSavedPlace() {
  try {
    const place = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (place?.name && place?.label && place?.timezone) return place;
  } catch {
    // Missing or unreadable: treat as a first visit
  }
  return null;
}

function forgetSavedPlace() {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing to do
  }
}

// --- Featured cities: quick buttons from GET /locations --------------------------

async function loadFeatured() {
  const response = await fetch("/locations");
  const places = await response.json();

  places.forEach((place) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip";
    button.dataset.name = place.name;
    button.textContent = place.label;
    button.addEventListener("click", () => selectPlace(place));
    featuredNav.appendChild(button);
  });
  return places;
}

// Mark the current place's button as pressed (none, for a searched place)
function highlightFeatured(name) {
  featuredNav.querySelectorAll("button").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.name === name));
  });
}

// --- Choosing a place ------------------------------------------------------------

// Show a place's forecast; remember it if it loaded. Returns true if it loaded.
async function selectPlace(place) {
  currentPlace = place;
  placeLabel.textContent = place.label;
  highlightFeatured(place.name);

  const loaded = await loadForecast(place);
  if (loaded) savePlace(place);
  return loaded;
}

// --- Searching any place: GET /places?query=... -----------------------------------

const SEARCH_DELAY_MS = 300; // wait until typing pauses, rather than searching on every key
let searchTimer = null;
let latestSearch = 0;        // numbers each search, so a slow older answer can't overwrite a newer one

function hideResults() {
  resultsList.hidden = true;
  resultsList.replaceChildren();
  searchInput.setAttribute("aria-expanded", "false");
}

function showResults(places, emptyMessage) {
  resultsList.replaceChildren();

  if (places.length === 0) {
    const item = document.createElement("li");
    item.className = "place-results-empty";
    item.textContent = emptyMessage;
    resultsList.appendChild(item);
  }

  places.forEach((place) => {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = place.label;
    button.addEventListener("click", () => {
      searchInput.value = "";
      hideResults();
      selectPlace(place);
    });
    item.appendChild(button);
    resultsList.appendChild(item);
  });

  resultsList.hidden = false;
  searchInput.setAttribute("aria-expanded", "true");
}

async function searchPlaces() {
  const query = searchInput.value.trim();
  if (query.length < 2) {
    hideResults();
    return;
  }

  const searchNumber = ++latestSearch;
  let places;
  try {
    const response = await fetch(`/places?query=${encodeURIComponent(query)}`);
    if (!response.ok) throw new Error(`Search failed: ${response.status}`);
    places = await response.json();
  } catch {
    if (searchNumber === latestSearch) showResults([], "Search isn't available right now");
    return;
  }

  // The user kept typing while this search was in flight: a newer search owns the list
  if (searchNumber !== latestSearch) return;
  showResults(places, `No places found for "${query}"`);
}

searchInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(searchPlaces, SEARCH_DELAY_MS);
});

searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    hideResults();
  } else if (event.key === "Enter") {
    // Enter picks the first suggestion, if there is one
    resultsList.querySelector("button")?.click();
  } else if (event.key === "ArrowDown") {
    // Down arrow moves into the suggestions (then Tab/Shift+Tab or arrows move between them)
    event.preventDefault();
    resultsList.querySelector("button")?.focus();
  }
});

resultsList.addEventListener("keydown", (event) => {
  const buttons = [...resultsList.querySelectorAll("button")];
  const index = buttons.indexOf(document.activeElement);
  if (event.key === "ArrowDown" && index < buttons.length - 1) {
    event.preventDefault();
    buttons[index + 1].focus();
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    (index > 0 ? buttons[index - 1] : searchInput).focus();
  } else if (event.key === "Escape") {
    hideResults();
    searchInput.focus();
  }
});

// Clicking anywhere outside the search closes the suggestions
document.addEventListener("click", (event) => {
  if (!event.target.closest(".search")) hideResults();
});

// --- Forecast: GET /forecast?location=... -------------------------------------------

let latestForecast = 0; // like latestSearch: switching place quickly mustn't show an older place's data

// Load and show a place's forecast. Returns true if it loaded.
async function loadForecast(place) {
  showStatus("Loading…");
  const requestNumber = ++latestForecast;

  let response;
  try {
    response = await fetch(`/forecast?location=${encodeURIComponent(place.name)}`);
  } catch {
    // fetch only throws when the server can't be reached at all (e.g. uvicorn isn't running)
    showStatus("Can't reach the ForecastBridge server. Is it running?", true);
    return false;
  }
  if (requestNumber !== latestForecast) return false; // another place was chosen meanwhile

  if (!response.ok) {
    const error = await response.json();
    showStatus(`Error: ${error.detail}`, true);
    return false;
  }

  const records = await response.json();
  if (requestNumber !== latestForecast) return false;

  const nowIndex = findNowIndex(records, place.timezone);
  showNow(records, nowIndex);
  drawChart(records, nowIndex);
  showStatus("");
  loadAdvice(place.name);
  return true;
}

// An emoji for each kind of advice the API sends back
const ADVICE_ICONS = {
  rain: "🌧️",
  "rain-possible": "🌦️",
  dry: "☀️",
  umbrella: "☂️",
  cold: "🌡️",
  jacket: "🧥",
  wind: "💨",
};

// Fill the "Next 12 hours" list from GET /advice?location=...
// The advice is a bonus: if it fails, the rest of the page still works, so just hide the list.
async function loadAdvice(name) {
  const list = document.getElementById("advice-list");
  list.replaceChildren(); // clear the previous location's advice

  let advice;
  try {
    const response = await fetch(`/advice?location=${encodeURIComponent(name)}`);
    if (!response.ok) return;
    advice = await response.json();
  } catch {
    return;
  }

  advice.forEach(({ kind, message }) => {
    const item = document.createElement("li");
    item.className = `advice advice-${kind}`;
    item.textContent = `${ADVICE_ICONS[kind] ?? "•"} ${message}`;
    list.appendChild(item);
  });
}

// The current hour in the place's time zone, in the same format as the API: "2026-10-19T18:00"
function currentHourKey(timeZone) {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date());
  const part = (type) => parts.find((p) => p.type === type).value;
  return `${part("year")}-${part("month")}-${part("day")}T${part("hour")}:00`;
}

// Which record is "now"? The forecast starts at midnight, so it's usually not the first one.
function findNowIndex(records, timeZone) {
  const nowKey = currentHourKey(timeZone);
  const index = records.findIndex((r) => r.time === nowKey);
  return index === -1 ? 0 : index; // fall back to the first hour if now isn't in the data
}

// 3. Fill the three "right now" cards from the current hour's record
function showNow(records, nowIndex) {
  if (records.length === 0) {
    showStatus("No forecast records available.", true);
    return;
  }

  const now = records[nowIndex];
  document.getElementById("now-time").textContent = formatHour(now.time);
  document.getElementById("now-temp").textContent = `${now.temperature_c} °C`;
  document.getElementById("now-rain").textContent = `${now.rain_chance_percent} %`;
  document.getElementById("now-wind").textContent = `${now.wind_kph} km/h`;
}

// "2026-10-19T09:00" -> "Mon 09:00" (the API's times are already in the place's local time)
function formatHour(time) {
  return new Date(time).toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit" });
}

// A small Chart.js plugin: draws a dashed "Now" line on top of the chart.
// It's invisible until the button sets nowHighlight.opacity above 0; the fade lowers it back to 0.
const nowLinePlugin = {
  id: "nowLine",
  afterDatasetsDraw(chart) {
    const { index, opacity } = nowHighlight;
    if (index == null || opacity <= 0) return;

    const x = chart.scales.x.getPixelForValue(index);
    const { top, bottom } = chart.chartArea;
    const color = getComputedStyle(document.documentElement).getPropertyValue("--text").trim();
    const ctx = chart.ctx;

    ctx.save();
    ctx.globalAlpha = opacity;
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, bottom);
    ctx.stroke();

    ctx.setLineDash([]);
    ctx.fillStyle = color;
    ctx.font = "600 12px system-ui, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("Now", x, top - 6);
    ctx.restore();
  },
};

// 4. Draw (or redraw) the 48-hour chart
function drawChart(records, nowIndex) {
  const ctx = document.getElementById("forecast-chart").getContext("2d");
  const labels = records.map((r) => formatHour(r.time));
  const temperatures = records.map((r) => r.temperature_c);
  const rainChances = records.map((r) => r.rain_chance_percent);

  nowHighlight.index = nowIndex;

  if (chart) {
    hideNow(); // a new location starts with the highlight hidden
    chart.data.labels = labels;
    chart.data.datasets[0].data = temperatures;
    chart.data.datasets[1].data = rainChances;
    chart.update();
  } else {
    chart = new Chart(ctx, {
      plugins: [nowLinePlugin],
      data: {
        labels: labels,
        datasets: [
          {
            type: "line",
            label: "Temperature (°C)",
            data: temperatures,
            yAxisID: "temp",
            borderColor: "rgba(75, 192, 192, 1)",
            backgroundColor: "rgba(75, 192, 192, 0.2)",
            fill: true,
          },
          {
            type: "bar",
            label: "Chance of rain (%)",
            data: rainChances,
            yAxisID: "rain",
            backgroundColor: "rgba(54, 120, 220, 0.35)",
            maxBarThickness: 14, // keeps bars slim on the wide phone chart; desktop bars are already about this size
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false, // fill the 360px-high box from style.css
        layout: { padding: { top: 20 } }, // room above the chart for the "Now" label
        // Hovering anywhere in an hour's column shows both temperature and rain for that hour
        interaction: { mode: "index", intersect: false },
        scales: {
          x: { title: { display: true, text: "Time" } },
          temp: { position: "left", title: { display: true, text: "Temperature (°C)" } },
          rain: {
            position: "right",
            min: 0,
            max: 100,
            // cursor: "pointer",
            title: { display: true, text: "Chance of rain (%)" },
            grid: { drawOnChartArea: false }, // only the temperature axis draws grid lines
          },
        },
      },
    });
  }

  nowButton.disabled = false;
  scrollToNow("auto"); // on phones, open the scrolled chart at the current hour
}

// On narrow screens the chart is wider than the page: scroll it so "now" is in the middle
function scrollToNow(behavior = "smooth") {
  if (nowHighlight.index == null) return;
  const x = chart.scales.x.getPixelForValue(nowHighlight.index);
  chartScroll.scrollTo({ left: x - chartScroll.clientWidth / 2, behavior });
}

// Point the chart's tooltip at the "now" hour (or clear it when index is null)
function setTooltip(index) {
  const active = index == null ? [] : chart.data.datasets.map((_, datasetIndex) => ({ datasetIndex, index }));
  chart.setActiveElements(active);
  chart.tooltip.setActiveElements(active, { x: 0, y: 0 });
}

// Stop any running timer or fade, so clicking again restarts cleanly
function stopNowTimers() {
  clearTimeout(nowTimer);
  cancelAnimationFrame(nowAnimation);
}

// Hide the highlight straight away
function hideNow() {
  stopNowTimers();
  nowHighlight.opacity = 0;
  setTooltip(null);
}

// Button click: show the line and tooltip at "now", then fade them out
function flashNow() {
  stopNowTimers();
  scrollToNow();

  nowHighlight.opacity = 1;
  setTooltip(nowHighlight.index);
  chart.update();

  nowTimer = setTimeout(() => {
    setTooltip(null); // Chart.js fades the tooltip out by itself
    chart.update();
    const fadeStart = performance.now();

    // Each animation frame: lower the line's opacity a little and redraw
    const fade = (time) => {
      nowHighlight.opacity = Math.max(0, 1 - (time - fadeStart) / NOW_FADE_MS);
      chart.draw();
      if (nowHighlight.opacity > 0) nowAnimation = requestAnimationFrame(fade);
    };
    nowAnimation = requestAnimationFrame(fade);
  }, NOW_SHOW_MS);
}

// Phones have no "mouse leaves the chart" event, so a tapped tooltip would stay forever.
// Clear it shortly after the finger lifts.
let touchTimer = null;
document.getElementById("forecast-chart").addEventListener("touchend", () => {
  clearTimeout(touchTimer);
  touchTimer = setTimeout(() => {
    if (nowHighlight.opacity > 0) return; // leave it alone while "Show now" is running
    setTooltip(null);
    chart.update();
  }, 1500);
});

// Start: show the featured cities, then open the last viewed place (or London on a first visit)
nowButton.addEventListener("click", flashNow);

async function start() {
  let featured = [];
  try {
    featured = await loadFeatured();
  } catch {
    showStatus("Can't reach the ForecastBridge server. Is it running?", true);
    return;
  }

  const saved = readSavedPlace();
  if (saved && (await selectPlace(saved))) return;
  if (saved) forgetSavedPlace(); // the saved place no longer loads: fall back quietly

  const fallback = featured.find((place) => place.name === DEFAULT_PLACE_NAME) ?? featured[0];
  if (fallback) await selectPlace(fallback);
}

start();
