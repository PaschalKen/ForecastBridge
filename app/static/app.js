// ForecastBridge front end.
// Open the browser's DevTools console (Cmd+Option+J) to see errors and console.log output.

const select = document.getElementById("location-select");
const statusEl = document.getElementById("status");
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

// 1. Fill the dropdown from GET /locations
async function loadLocations() {
  const response = await fetch("/locations");

  const locations = await response.json();

  locations.forEach((name) => {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    select.appendChild(option);
  });
}

// 2. Get the forecast for one location from GET /forecast?location=...
async function loadForecast(name) {
  showStatus("Loading…");

  let response;
  try {
    response = await fetch(`/forecast?location=${encodeURIComponent(name)}`);
  } catch {
    // fetch only throws when the server can't be reached at all (e.g. uvicorn isn't running)
    showStatus("Can't reach the ForecastBridge server. Is it running?", true);
    return;
  }

  if (!response.ok) {
    const error = await response.json();
    showStatus(`Error: ${error.detail}`, true);
    return;
  }

  const records = await response.json();
  const nowIndex = findNowIndex(records);
  showNow(records, nowIndex);
  drawChart(records, nowIndex);
  showStatus("");
  loadAdvice(name);
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

// The current hour in UK time, in the same format as the API: "2026-10-19T18:00"
function currentHourKey() {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", hourCycle: "h23",
  }).formatToParts(new Date());
  const part = (type) => parts.find((p) => p.type === type).value;
  return `${part("year")}-${part("month")}-${part("day")}T${part("hour")}:00`;
}

// Which record is "now"? The forecast starts at midnight, so it's usually not the first one.
function findNowIndex(records) {
  const index = records.findIndex((r) => r.time === currentHourKey());
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

// "2026-10-19T09:00" -> "Mon 09:00" (the API's times are already UK local time)
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

// Start: load locations, then the forecast for the first one, and reload when the dropdown changes
nowButton.addEventListener("click", flashNow);
select.addEventListener("change", () => loadForecast(select.value));
loadLocations().then(() => loadForecast(select.value));
