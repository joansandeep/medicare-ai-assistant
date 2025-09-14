let vitalsChart = null;
let trendsChart = null;

const datasetVisibility = { hr: true, temp: true };
const $ = (s) => document.querySelector(s);

function err(...a){ console.error('[metrics]', ...a); }

async function loadMetrics(){
  try{
    const res = await fetch('/api/health_metrics', { credentials:'same-origin' });
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    updateQuickStats(data);
    buildVitalsChart(data);
    buildTrendsChart(data);
  }catch(e){
    err('API load error; using fallback data:', e);
    const data = makeFallbackData();
    updateQuickStats(data);
    buildVitalsChart(data);
    buildTrendsChart(data);
  }
}

function updateQuickStats(data){
  const latest = data.latest || {};
  $('#heartRateValue') && ($('#heartRateValue').textContent = `${latest.heart_rate ?? '--'} BPM`);
  $('#bpValue') && ($('#bpValue').textContent = `${latest.systolic ?? '--'}/${latest.diastolic ?? '--'}`);
  $('#tempValue') && ($('#tempValue').textContent = `${latest.temperature ?? '--'} °C`);
  $('#healthScoreValue') && ($('#healthScoreValue').textContent = `${latest.health_score ?? '--'}%`);
}

/* Dynamic axis padding */
function calcRange(values, pad = 0.15){
  const clean = values.filter(v => v!=null && !Number.isNaN(v));
  if (!clean.length) return {};
  const min = Math.min(...clean);
  const max = Math.max(...clean);
  const span = Math.max(1, max - min);
  return { min: Math.floor(min - span*pad), max: Math.ceil(max + span*pad) };
}

function buildVitalsChart(data){
  if (!window.Chart) return;
  const ctx = document.getElementById('vitalsChart'); if(!ctx) return;

  const series = data.recent_series || [];
  const labels = series.map(r => r.time);
  const hr = series.map(r => r.heart_rate);
  const temp = series.map(r => r.temperature);

  if (vitalsChart) vitalsChart.destroy();

  const yRange = calcRange(hr, 0.15);
  const tRange = calcRange(temp, 0.15);

  vitalsChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label:'Heart Rate (BPM)', data:hr, borderColor:'#ef4444', backgroundColor:'rgba(239,68,68,0.12)', pointBackgroundColor:'#ef4444', borderWidth:2, tension:.3, hidden:!datasetVisibility.hr, yAxisID:'y' },
        { label:'Temperature (°C)', data:temp, borderColor:'#8b5cf6', backgroundColor:'rgba(139,92,246,0.12)', pointBackgroundColor:'#8b5cf6', borderWidth:2, tension:.3, hidden:!datasetVisibility.temp, yAxisID:'y2' }
      ]
    },
    options: {
      responsive:true, maintainAspectRatio:false,
      interaction:{ mode:'nearest', intersect:false },
      plugins:{
        legend:{ position:'top', labels:{ boxWidth:12 } },
        tooltip:{ callbacks:{ title:(items)=> items.length ? items[0].label : '' } },
        zoom:{ pan:{ enabled:false }, zoom:{ wheel:{enabled:false}, pinch:{enabled:false} } } // no controls
      },
      scales:{
        y:{ title:{display:true,text:'Heart Rate'}, suggestedMin:yRange.min, suggestedMax:yRange.max, ticks:{ maxTicksLimit:6 }, grid:{ color:'rgba(0,0,0,0.06)' } },
        y2:{ position:'right', title:{display:true,text:'Temperature (°C)'}, suggestedMin:tRange.min, suggestedMax:tRange.max, ticks:{ maxTicksLimit:6 }, grid:{ drawOnChartArea:false } },
        x:{ ticks:{ autoSkip:true, maxTicksLimit:8 }, grid:{ color:'rgba(0,0,0,0.04)' } }
      },
      elements:{ point:{ radius:2, hoverRadius:4 } }
    }
  });

  // Toggle pills
  document.querySelectorAll('.metric-pills .pill').forEach(pill=>{
    pill.onclick = ()=>{
      const key = pill.dataset.key;
      pill.classList.toggle('active');
      datasetVisibility[key] = pill.classList.contains('active');
      vitalsChart.data.datasets.forEach(ds=>{
        if (key==='hr'   && ds.label.startsWith('Heart Rate')) ds.hidden = !datasetVisibility[key];
        if (key==='temp' && ds.label.startsWith('Temperature')) ds.hidden = !datasetVisibility[key];
      });
      vitalsChart.update();
    };
  });
}

function buildTrendsChart(data){
  if (!window.Chart) return;
  const ctx = document.getElementById('trendsChart'); if(!ctx) return;

  const days = data.trend_days || [];
  const labels = days.map(d=>d.date);
  const score = days.map(d=>d.health_score);

  if (trendsChart) trendsChart.destroy();

  const sRange = calcRange(score, 0.1);
  const sMin = Math.max(0, sRange.min ?? 0);
  const sMax = Math.min(100, sRange.max ?? 100);

  trendsChart = new Chart(ctx, {
    type:'line',
    data:{ labels, datasets:[{ label:'Health Score', data:score, borderColor:'#00a4e4', backgroundColor:'rgba(0,164,228,0.18)', fill:true, borderWidth:2, tension:.3, pointRadius:2, pointHoverRadius:4 }]},
    options:{
      responsive:true, maintainAspectRatio:false,
      plugins:{ legend:{ display:false }, zoom:{ pan:{enabled:false}, zoom:{ wheel:{enabled:false}, pinch:{enabled:false} } } },
      scales:{
        y:{ suggestedMin:sMin, suggestedMax:sMax, title:{display:true,text:'Score (%)'}, ticks:{ maxTicksLimit:6 }, grid:{ color:'rgba(0,0,0,0.06)' } },
        x:{ ticks:{ autoSkip:true, maxTicksLimit:7 }, grid:{ color:'rgba(0,0,0,0.04)' } }
      }
    }
  });
}

/* Fallback data used when API is unavailable */
function makeFallbackData(){
  const now = new Date();
  const recent = [];
  for (let i = 23; i >= 0; i--) {
    const t = new Date(now.getTime() - i*60*60*1000);
    const hr = Math.round(70 + (Math.random()-0.5)*20);
    const temp = +(36.7 + (Math.random()-0.5)*0.6).toFixed(1);
    recent.push({ time: t.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}), heart_rate: hr, temperature: temp });
  }
  const latest = {
    time: now.toISOString().slice(0,16).replace('T',' '),
    heart_rate: recent.at(-1).heart_rate,
    systolic: 120, diastolic: 80,
    temperature: recent.at(-1).temperature,
    spo2: 98, respiration: 14,
    health_score: 72
  };
  const trend_days = [];
  for (let d = 6; d >= 0; d--) {
    const date = new Date(now.getTime() - d*86400000);
    trend_days.push({ date: date.toLocaleDateString('en-CA').slice(5), health_score: Math.round(65 + (Math.random()-0.5)*15) });
  }
  return { latest, recent_series: recent, trend_days };
}

document.addEventListener('DOMContentLoaded', loadMetrics);