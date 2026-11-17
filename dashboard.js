let trendChart, weeklyChart, map, markers = {};

const $ = (id) => document.getElementById(id);
const colorFor = (status) => status === "Critical" ? "#e64b55" : status === "Warning" ? "#e69b24" : "#28a879";

function renderBins(bins) {
  $("binList").innerHTML = bins.map(bin => `
    <div class="bin-row">
      <div class="bin-top">
        <div class="bin-symbol">${bin.status === "Critical" ? "🗑️" : "♻️"}</div>
        <div class="bin-info">
          <div class="bin-name">${bin.id} – ${escapeHtml(bin.location)}</div>
          <div class="bin-level">${bin.fill}%</div>
          <div class="bar"><span style="width:${bin.fill}%;background:${colorFor(bin.status)}"></span></div>
        </div>
        <span class="status ${bin.status}">${bin.status}</span>
      </div>
      <div class="bin-meta">
        <span>Moisture: ${bin.moisture}%</span>
        <span>Gas index: ${bin.gas}</span>
        <button class="collect-btn" onclick="markCollected('${bin.id}')">Mark collected</button>
      </div>
    </div>`).join("");
}

function renderAlerts(alerts) {
  const active = alerts.filter(a => !a.acknowledged);
  $("alertList").innerHTML = alerts.length ? alerts.slice(0,6).map(a => `
    <div class="alert-row">
      <i class="alert-dot" style="background:${colorFor(a.severity)}"></i>
      <span class="alert-time">${a.created_at.slice(11,16)}</span>
      <span class="alert-message"><b>${a.bin_id}</b> (${escapeHtml(a.location)}): ${escapeHtml(a.message)}</span>
      <span class="status ${a.severity}">${a.severity}</span>
      ${!a.acknowledged ? `<button class="ack-btn" onclick="acknowledge(${a.id})">Done</button>` : ""}
    </div>`).join("") : '<p class="muted">No alerts yet. All bins look good!</p>';
  $("sideAlertCount").textContent = active.length;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

function updateCharts(data) {
  const labels = data.trend.map(x => x.minute.slice(11));
  const values = data.trend.map(x => x.average);
  if (trendChart) {
    trendChart.data.labels = labels;
    trendChart.data.datasets[0].data = values;
    trendChart.update();
  } else {
    trendChart = new Chart($("trendChart"), {
      type:"line",
      data:{labels,datasets:[{label:"Average fill level (%)",data:values,borderColor:"#3478eb",backgroundColor:"rgba(52,120,235,.12)",fill:true,tension:.35,pointRadius:3}]},
      options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{min:0,max:100,ticks:{stepSize:20}},x:{grid:{display:false}}}}
    });
  }
  const weekLabels = data.weekly.map(x => x.day.slice(5));
  const weekValues = data.weekly.map(x => x.average);
  if (weeklyChart) {
    weeklyChart.data.labels = weekLabels;
    weeklyChart.data.datasets[0].data = weekValues;
    weeklyChart.update();
  } else {
    weeklyChart = new Chart($("weeklyChart"), {
      type:"bar",
      data:{labels:weekLabels,datasets:[{label:"Average fill (%)",data:weekValues,backgroundColor:"#4c89ed",borderRadius:5}]},
      options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{min:0,max:100},x:{grid:{display:false}}}}
    });
  }
}

function updateMap(bins) {
  if (!window.L) return;
  if (!map) {
    map = L.map("map").setView([26.8505,75.8005],15);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution:'&copy; OpenStreetMap contributors', maxZoom:19
    }).addTo(map);
  }
  bins.forEach(bin => {
    const lat = Number(bin.lat), lon = Number(bin.lon);
    const popup = `<b>${escapeHtml(bin.id)} – ${escapeHtml(bin.location)}</b><br>${bin.fill}% full<br>${bin.status}`;
    if (markers[bin.id]) {
      markers[bin.id].setLatLng([lat,lon]).setPopupContent(popup);
    } else {
      markers[bin.id] = L.circleMarker([lat,lon], {
        radius:10, color:colorFor(bin.status), fillColor:colorFor(bin.status), fillOpacity:.85
      }).addTo(map).bindPopup(popup);
    }
  });
  setTimeout(() => map.invalidateSize(), 100);
}

async function refreshDashboard() {
  try {
    const response = await fetch("/api/dashboard");
    const data = await response.json();
    $("totalBins").textContent = data.summary.total;
    $("criticalBins").textContent = data.summary.critical;
    $("normalBins").textContent = data.summary.normal;
    $("activeAlerts").textContent = data.summary.active_alerts;
    $("updated").textContent = data.updated;
    renderBins(data.bins);
    renderAlerts(data.alerts);
    updateCharts(data);
    updateMap(data.bins);
    const selected = data.bins.find(b => b.status === "Critical") || data.bins[0];
    if (selected) {
      $("gFill").textContent = selected.fill + "%";
      $("gMoist").textContent = selected.moisture + "%";
      $("gGas").textContent = selected.gas;
      $("fillGauge").style.borderTopColor = colorFor(selected.status);
    }
  } catch (err) {
    console.error(err);
  }
}

async function markCollected(id) {
  if (!confirm(`Mark ${id} as collected and reset its fill level?`)) return;
  await fetch(`/api/collect/${id}`, {method:"POST"});
  refreshDashboard();
}
async function acknowledge(id) {
  await fetch(`/api/alerts/acknowledge/${id}`, {method:"POST"});
  refreshDashboard();
}

$("addBinBtn").addEventListener("click", async () => {
  const location = prompt("Enter a location name for the new virtual bin:");
  if (!location || !location.trim()) return;
  const response = await fetch("/api/bins", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body:JSON.stringify({location:location.trim()})
  });
  const result = await response.json();
  if (!response.ok) alert(result.error || "Could not add bin.");
  refreshDashboard();
});

document.querySelectorAll(".nav-link").forEach(link => {
  link.addEventListener("click", () => {
    document.querySelectorAll(".nav-link").forEach(x => x.classList.remove("active"));
    link.classList.add("active");
  });
});

refreshDashboard();
setInterval(refreshDashboard, 5000);
