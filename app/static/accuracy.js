// ForecastBridge: "How accurate?" page.
// Shows GET /accuracy for a featured city: saved forecasts compared with what actually happened.

const select = document.getElementById("location-select");
const daysSelect = document.getElementById("days-select");
const statusEl = document.getElementById("status");

const DEFAULT_PLACE_NAME = "london";
const DAY_AHEAD_BAND = 13; // the "13 to 24 hours ahead" band is what the cards call "a day ahead"
let comparisonChart = null;
let latestRequest = 0;     // a slow older answer mustn't replace a newer one

// Read a saved setting from the main page (last place, units); storage can be blocked
function readStored(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

// Units chosen on the main page. The API always sends metric; the page converts.
const imperial = readStored("forecastbridge:units") === "imperial";
const tempUnit = imperial ? "°F" : "°C";
const toTemp = (celsius) => (imperial ? Math.round((celsius * 9 / 5 + 32) * 10) / 10 : celsius);
// A temperature *difference* converts without the +32 offset
const toTempDiff = (celsius) => (imperial ? Math.round(celsius * 9 / 5 * 10) / 10 : celsius);

function showStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

const percentText = (value) => (value == null ? "–" : `${value} %`);
const errorText = (value) => (value == null ? "–" : `±${toTempDiff(value)} ${tempUnit}`);

function biasText(value) {
  if (value == null) return "";
  if (value === 0) return "no bias";
  return `${value > 0 ? "+" : ""}${toTempDiff(value)} ${tempUnit} (forecasts ran ${value > 0 ? "warm" : "cold"})`;
}

// "2026-10-27T15:00" -> "Tue 15:00"
function formatHour(time) {
  return new Date(time).toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit" });
}

// --- Loading ------------------------------------------------------------------------

async function loadAccuracy() {
  const requestNumber = ++latestRequest;
  const days = daysSelect.value;
  showStatus("Comparing saved forecasts with what happened… (this can take a few seconds)");

  let report;
  try {
    const response = await fetch(`/accuracy?location=${encodeURIComponent(select.value)}&days=${days}`);
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail ?? `Request failed: ${response.status}`);
    }
    report = await response.json();
  } catch (error) {
    if (requestNumber === latestRequest) showStatus(`Error: ${error.message}`, true);
    return;
  }
  if (requestNumber !== latestRequest) return;

  document.getElementById("period").textContent = `Last ${days} days`;
  showCards(report);
  showLeadTable(report.by_lead);
  drawComparison(report.series);
  showStatus(report.compared_hours === 0 ? "No saved forecasts to compare for this period yet." : "");
}

// --- Cards --------------------------------------------------------------------------

function showCards(report) {
  const dayAhead = report.by_lead.find((band) => band.min_hours === DAY_AHEAD_BAND);
  const totalForecasts = report.by_lead.reduce((sum, band) => sum + band.forecasts, 0);

  document.getElementById("acc-hours").textContent = report.compared_hours;
  document.getElementById("acc-forecasts").textContent = `${totalForecasts.toLocaleString("en-GB")} forecasts checked`;
  document.getElementById("acc-error").textContent = errorText(dayAhead.mean_error_c);
  document.getElementById("acc-bias").textContent = biasText(dayAhead.bias_c);
  document.getElementById("acc-within").textContent = percentText(dayAhead.within_2c_percent);
  document.getElementById("acc-rain").textContent = percentText(dayAhead.rain_likely_correct_percent);
  document.getElementById("acc-dry").textContent =
    dayAhead.dry_correct_percent == null ? "" : `"Dry" was right ${dayAhead.dry_correct_percent} %`;
}

// --- Table: one row per distance ahead -------------------------------------------------

function showLeadTable(bands) {
  const rows = document.getElementById("lead-rows");
  rows.replaceChildren();

  bands.forEach((band) => {
    const row = document.createElement("tr");
    [
      band.label,
      band.forecasts.toLocaleString("en-GB"),
      errorText(band.mean_error_c),
      band.bias_c == null ? "–" : `${band.bias_c > 0 ? "+" : ""}${toTempDiff(band.bias_c)} ${tempUnit}`,
      percentText(band.within_2c_percent),
      percentText(band.rain_likely_correct_percent),
      percentText(band.dry_correct_percent),
    ].forEach((text) => {
      const cell = document.createElement("td");
      cell.textContent = text;
      row.appendChild(cell);
    });
    rows.appendChild(row);
  });
}

// --- Chart: actual temperature vs the forecast made about a day before ------------------

function drawComparison(series) {
  const labels = series.map((p) => formatHour(p.time));
  const actual = series.map((p) => toTemp(p.actual_c));
  const forecast = series.map((p) => toTemp(p.forecast_c));
  const rained = series.map((p) => (p.rained ? 100 : 0));

  if (comparisonChart) {
    comparisonChart.data.labels = labels;
    comparisonChart.data.datasets[0].data = actual;
    comparisonChart.data.datasets[1].data = forecast;
    comparisonChart.data.datasets[2].data = rained;
    comparisonChart.update();
    return;
  }

  comparisonChart = new Chart(document.getElementById("comparison-chart").getContext("2d"), {
    data: {
      labels,
      datasets: [
        {
          type: "line",
          label: `What happened (${tempUnit})`,
          data: actual,
          yAxisID: "temp",
          borderColor: "rgba(230, 234, 240, 0.9)",
          backgroundColor: "rgba(230, 234, 240, 0.9)",
          pointRadius: 0,
          borderWidth: 2,
        },
        {
          type: "line",
          label: `Forecast a day before (${tempUnit})`,
          data: forecast,
          yAxisID: "temp",
          borderColor: "rgba(75, 192, 192, 1)",
          backgroundColor: "rgba(75, 192, 192, 0.2)",
          pointRadius: 0,
          borderWidth: 2,
        },
        {
          type: "bar",
          label: "It rained",
          data: rained,
          yAxisID: "rain",
          backgroundColor: "rgba(54, 120, 220, 0.25)",
          barPercentage: 1,
          categoryPercentage: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        tooltip: {
          callbacks: {
            // Rain bars are 100 or 0 only to draw them; say yes or no instead
            label: (item) =>
              item.dataset.yAxisID === "rain"
                ? `It rained: ${item.raw ? "yes" : "no"}`
                : `${item.dataset.label}: ${item.formattedValue}`,
          },
        },
      },
      scales: {
        x: { title: { display: true, text: "Time" } },
        temp: { position: "left", title: { display: true, text: `Temperature (${tempUnit})` } },
        rain: { position: "right", min: 0, max: 100, display: false },
      },
    },
  });
}

// --- Start ----------------------------------------------------------------------------

async function start() {
  let places;
  try {
    places = await (await fetch("/locations")).json();
  } catch {
    showStatus("Can't reach the ForecastBridge server. Is it running?", true);
    return;
  }

  // Featured cities only: they're the ones with a full hourly history of saved forecasts
  places.forEach((place) => select.add(new Option(place.label, place.name)));

  // Open on the main page's last place if it's a featured city, otherwise London
  let lastName = null;
  try {
    lastName = JSON.parse(readStored("forecastbridge:lastPlace"))?.name;
  } catch {
    // Unreadable: use the default
  }
  select.value = places.some((p) => p.name === lastName) ? lastName : DEFAULT_PLACE_NAME;

  select.addEventListener("change", loadAccuracy);
  daysSelect.addEventListener("change", loadAccuracy);
  loadAccuracy();
}

start();
