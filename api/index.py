import sys
from pathlib import Path
import re
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import trio

# Pastikan root project masuk ke sys.path agar modul 'holehe' terbaca di Vercel
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from holehe.core import import_submodules, get_functions, launch_module

app = FastAPI(title="Holehe OSINT Vercel")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

# Load modul Holehe saat startup
modules = import_submodules("holehe.modules")
all_websites = get_functions(modules)

async def run_holehe_async(email: str, target_websites, timeout: float = 3.5):
    out = []
    # Batasi timeout per request agar Vercel tidak mengalami 504 Gateway Timeout
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with trio.open_nursery() as nursery:
            for website in target_websites:
                nursery.start_soon(launch_module, website, email, client, out)
    return sorted(out, key=lambda i: i.get("name", ""))

@app.get("/", response_class=HTMLResponse)
def index():
    return """<!DOCTYPE html>
<html lang="id" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Holehe OSINT - Vercel Scanner</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen py-10 px-4 antialiased selection:bg-indigo-500 selection:text-white">
  <div class="max-w-4xl mx-auto">
    <!-- Header -->
    <div class="text-center mb-8">
      <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-400 text-xs font-medium border border-indigo-500/20 mb-3">
        <span>▲ Deployed on Vercel</span>
      </div>
      <h1 class="text-3xl font-extrabold text-white sm:text-5xl tracking-tight">Holehe OSINT Scanner</h1>
      <p class="mt-2 text-slate-400 text-sm sm:text-base">Periksa apakah email terdaftar di berbagai platform online.</p>
    </div>

    <!-- Scan Card -->
    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl">
      <form id="scanForm" class="flex flex-col gap-4">
        <div class="flex flex-col sm:flex-row gap-3">
          <input 
            type="email" 
            id="emailInput" 
            required 
            placeholder="Ketik email target (contoh: user@gmail.com)" 
            class="flex-1 px-4 py-3.5 bg-slate-950 border border-slate-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 text-white placeholder-slate-500 text-sm sm:text-base transition"
          />
          <button 
            type="submit" 
            id="btnScan" 
            class="bg-indigo-600 hover:bg-indigo-500 font-semibold px-8 py-3.5 rounded-xl transition duration-200 disabled:opacity-50 text-white flex items-center justify-center gap-2 cursor-pointer shadow-lg shadow-indigo-600/20"
          >
            <span id="btnText">Scan Email</span>
            <svg id="btnSpinner" class="hidden animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
            </svg>
          </button>
        </div>

        <!-- Mode Pemindaian (Menghindari Vercel Timeout) -->
        <div class="flex flex-wrap items-center gap-4 text-xs text-slate-400 border-t border-slate-800/80 pt-4">
          <span class="font-medium text-slate-300">Mode Scan:</span>
          <label class="flex items-center gap-1.5 cursor-pointer hover:text-white">
            <input type="radio" name="scanMode" value="fast" checked class="text-indigo-600 focus:ring-indigo-500">
            <span>⚡ Cepat (35 situs utama - Rekomendasi Vercel ~5 detik)</span>
          </label>
          <label class="flex items-center gap-1.5 cursor-pointer hover:text-white">
            <input type="radio" name="scanMode" value="full" class="text-indigo-600 focus:ring-indigo-500">
            <span>🌐 Lengkap (Semua 120+ situs)</span>
          </label>
        </div>
      </form>
      
      <!-- Loading Indicator -->
      <div id="loader" class="hidden mt-5 text-center text-sm text-indigo-400 bg-indigo-950/30 border border-indigo-900/40 rounded-xl p-3">
        ⏳ Sedang memindai platform target... Mohon tunggu sebentar.
      </div>
    </div>

    <!-- Results Section -->
    <div id="resultBox" class="mt-8 hidden">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h2 class="text-xl font-bold text-white">Hasil Pemeriksaan</h2>
          <p id="counter" class="text-xs text-slate-400 mt-0.5"></p>
        </div>
        <div class="flex items-center gap-2">
          <button id="btnFilterAll" class="filter-btn text-xs px-3 py-1.5 rounded-lg bg-slate-800 text-white font-medium border border-slate-700">Semua</button>
          <button id="btnFilterUsed" class="filter-btn text-xs px-3 py-1.5 rounded-lg bg-slate-900 text-slate-400 font-medium border border-slate-800 hover:text-white">Terdaftar Saja</button>
        </div>
      </div>

      <div class="overflow-x-auto bg-slate-900 rounded-2xl border border-slate-800 shadow-xl">
        <table class="w-full text-left border-collapse text-sm">
          <thead>
            <tr class="bg-slate-950 border-b border-slate-800 text-slate-400 text-xs uppercase tracking-wider">
              <th class="p-3.5">Platform</th>
              <th class="p-3.5">Status</th>
              <th class="p-3.5">Info Pemulihan</th>
            </tr>
          </thead>
          <tbody id="tableBody" class="divide-y divide-slate-800/60 font-mono text-xs sm:text-sm"></tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    const form = document.getElementById('scanForm');
    const emailInput = document.getElementById('emailInput');
    const btnScan = document.getElementById('btnScan');
    const btnText = document.getElementById('btnText');
    const btnSpinner = document.getElementById('btnSpinner');
    const loader = document.getElementById('loader');
    const resultBox = document.getElementById('resultBox');
    const tableBody = document.getElementById('tableBody');
    const counter = document.getElementById('counter');
    const btnFilterAll = document.getElementById('btnFilterAll');
    const btnFilterUsed = document.getElementById('btnFilterUsed');

    let allResults = [];
    let currentFilter = 'all';

    function renderTable() {
      tableBody.innerHTML = '';
      const filtered = currentFilter === 'used' ? allResults.filter(i => i.exists) : allResults;

      if (filtered.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="3" class="p-6 text-center text-slate-500 font-sans">Tidak ada hasil yang sesuai dengan filter ini.</td></tr>';
        return;
      }

      filtered.forEach(item => {
        let badge = '';
        if (item.exists) {
          badge = '<span class="px-2.5 py-1 text-xs rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800 font-medium">Terdaftar</span>';
        } else if (item.rateLimit) {
          badge = '<span class="px-2.5 py-1 text-xs rounded-full bg-amber-950 text-amber-400 border border-amber-800 font-medium">Rate Limit</span>';
        } else if (item.error) {
          badge = '<span class="px-2.5 py-1 text-xs rounded-full bg-rose-950 text-rose-400 border border-rose-800 font-medium">Error</span>';
        } else {
          badge = '<span class="px-2.5 py-1 text-xs rounded-full bg-slate-800 text-slate-400 font-medium">Tidak Terdaftar</span>';
        }

        let extra = item.emailrecovery || item.phoneNumber || '-';
        const row = document.createElement('tr');
        row.className = item.exists ? "bg-emerald-950/20" : "hover:bg-slate-800/30";
        row.innerHTML = `
          <td class="p-3.5 font-medium text-slate-200">${item.domain || item.name}</td>
          <td class="p-3.5">${badge}</td>
          <td class="p-3.5 text-slate-400">${extra}</td>
        `;
        tableBody.appendChild(row);
      });
    }

    btnFilterAll.addEventListener('click', () => {
      currentFilter = 'all';
      btnFilterAll.className = "filter-btn text-xs px-3 py-1.5 rounded-lg bg-slate-800 text-white font-medium border border-slate-700";
      btnFilterUsed.className = "filter-btn text-xs px-3 py-1.5 rounded-lg bg-slate-900 text-slate-400 font-medium border border-slate-800 hover:text-white";
      renderTable();
    });

    btnFilterUsed.addEventListener('click', () => {
      currentFilter = 'used';
      btnFilterUsed.className = "filter-btn text-xs px-3 py-1.5 rounded-lg bg-slate-800 text-white font-medium border border-slate-700";
      btnFilterAll.className = "filter-btn text-xs px-3 py-1.5 rounded-lg bg-slate-900 text-slate-400 font-medium border border-slate-800 hover:text-white";
      renderTable();
    });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = emailInput.value.trim();
      if (!email) return;

      const mode = document.querySelector('input[name="scanMode"]:checked').value;
      const limitParam = mode === 'fast' ? '&limit=35' : '&limit=150';

      btnScan.disabled = true;
      btnText.innerText = "Memindai...";
      btnSpinner.classList.remove('hidden');
      loader.classList.remove('hidden');
      resultBox.classList.add('hidden');

      try {
        const res = await fetch(`/api/scan?email=${encodeURIComponent(email)}${limitParam}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Gagal melakukan scan");

        allResults = data.results || [];
        const usedCount = allResults.filter(i => i.exists).length;
        counter.innerText = `Ditemukan terdaftar di ${usedCount} dari ${allResults.length} platform`;

        currentFilter = 'all';
        renderTable();
        resultBox.classList.remove('hidden');
      } catch (err) {
        alert("Gagal memindai: " + err.message);
      } finally {
        btnScan.disabled = false;
        btnText.innerText = "Scan Email";
        btnSpinner.classList.add('hidden');
        loader.classList.add('hidden');
      }
    });
  </script>
</body>
</html>
"""

@app.get("/api/scan")
def api_scan(
    email: str = Query(..., description="Target email"),
    limit: int = Query(35, description="Batas jumlah situs (untuk menghindari timeout di Vercel)")
):
    if not re.match(EMAIL_REGEX, email):
        raise HTTPException(status_code=400, detail="Format email tidak valid.")

    selected_sites = all_websites[:limit]

    try:
        results = trio.run(run_holehe_async, email, selected_sites, 3.5)
        return {
            "email": email,
            "total": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

