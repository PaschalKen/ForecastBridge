// ForecastBridge front end.
// Fill in the TODOs. Open the browser's DevTools console (Cmd+Option+J) to see errors and console.log output.

const select = document.getElementById("location-select");
const statusEl = document.getElementById("status");
let chart = null; // the Chart.js chart, kept so we can update it when the location changes

function showStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.classList.toggle("error", isError);
}

// 1. Fill the dropdown from GET /locations
async function loadLocations() {
  // TODO: fetch("/locations"), turn the response into JSON,
  //       and add one <option> per name to `select`.
}

// 2. Get the forecast for one location from GET /forecast?location=...
async function loadForecast(name) {
  showStatus("Loading…");
  // TODO: fetch the forecast for `name`.
  //       If the response is not ok (404, 503), read its JSON `detail` and call showStatus(detail, true), then return.
  //       Otherwise turn it into JSON, then call showNow(records) and drawChart(records), and clear the status.
}

// 3. Fill the three "right now" cards from the first record
function showNow(records) {
  // TODO: set the text of #now-temp, #now-rain and #now-wind from records[0].
  //       e.g. "12.4 °C", "20 %", "15.2 km/h"
}

// 4. Draw (or redraw) the 48-hour chart
function drawChart(records) {
  // TODO: build labels and datasets from `records`, then create or update the Chart.js chart.
}

// Start: load locations, then the forecast for the first one, and reload when the dropdown changes
select.addEventListener("change", () => loadForecast(select.value));
loadLocations().then(() => loadForecast(select.value));
