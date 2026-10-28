import os
import re
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import trio
from holehe.core import import_submodules, get_functions, launch_module

app = FastAPI(title="Holehe OSINT Web")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

# Load modul Holehe saat startup container
modules = import_submodules("holehe.modules")
websites = get_functions(modules)

async def run_holehe_async(email: str, timeout: int = 10):
    out = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with trio.open_nursery() as nursery:
            for website in websites:
                nursery.start_soon(launch_module, website, email, client, out)
    return sorted(out, key=lambda i: i.get("name", ""))

@app.get("/", response_class=HTMLResponse)
def index():
    return """<!DOCTYPE html>
<html lang="id" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Holehe OSINT - Railway Scanner</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: { 500: '#6366f1', 600: '#4f46e5', 700: '#4338ca' }
          }
        }
      }
    }
  </script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen py-10 px-4 antialiased selection:bg-indigo-500 selection:text-white">
  <div class="max-w-4xl mx-auto">
    <!-- Header -->
    <div class="text-center mb-8">
      <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 text-indigo-400 text-xs font-medium border border-indigo-500/20 mb-3">
        <span>🚀 Deployed on Railway</span>
      </div>
      <h1 class="text-3xl font-extrabold text-white sm:text-5xl tracking-tight">Holehe OSINT Scanner</h1>
      <p class="mt-2 text-slate-400 text-sm sm:text-base">Periksa apakah email terdaftar di lebih dari 120 platform online.</p>
    </div>

    <!-- Search Box -->
    <div class="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-2xl backdrop-blur">
      <form id="scanForm" class="flex flex-col sm:flex-row gap-3">
        <div class="relative flex-1">
          <input 
            type="email" 
            id="emailInput" 
            required 
            placeholder="Ketik email target (contoh: user@gmail.com)" 
            class="w-full px-4 py-3.5 bg-slate-950 border border-slate-700/80 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 text-white placeholder-slate-500 text-sm sm:text-base transition"
          />
        </div>
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
      </form>
      
      <!-- Loading Progress Indicator -->
      <div id="loader" class="hidden mt-5 text-center text-sm text-indigo-400 bg-indigo-950/30 border border-indigo-900/40 rounded-xl p-3">
        ⚡ Sedang memindai 120+ situs web secara bersamaan... Harap tunggu ~15-30 detik.
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
            <tr class="bg-slate-950/80 border-b border-slate-800 text-slate-400 text-xs uppercase tracking-wider">
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
        tableBody.innerHTML = '<tr><td colspan="3" class="p-6 text-center text-slate-500 font-sans">Tidak ada hasil ditemukan dengan filter ini.</td></tr>';
        return;
      }

      filtered.forEach(item => {
        let badge = '';
        if (item.exists) {
          badge = '<span class="px-2.5 py-1 text-xs rounded-full bg-emerald-950/80 text-emerald-400 border border-emerald-800/60 font-medium">Terdaftar</span>';
        } else if (item.rateLimit) {
          badge = '<span class="px-2.5 py-1 text-xs rounded-full bg-amber-950/80 text-amber-400 border border-amber-800/60 font-medium">Rate Limit</span>';
        } else if (item.error) {
          badge = '<span class="px-2.5 py-1 text-xs rounded-full bg-rose-950/80 text-rose-400 border border-rose-800/60 font-medium">Error</span>';
        } else {
          badge = '<span class="px-2.5 py-1 text-xs rounded-full bg-slate-800/80 text-slate-400 font-medium">Tidak Terdaftar</span>';
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

      btnScan.disabled = true;
      btnText.innerText = "Memindai...";
      btnSpinner.classList.remove('hidden');
      loader.classList.remove('hidden');
      resultBox.classList.add('hidden');

      try {
        const res = await fetch(`/api/scan?email=${encodeURIComponent(email)}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Gagal melakukan scan");

        allResults = data.results || [];
        const usedCount = allResults.filter(i => i.exists).length;
        counter.innerText = `Ditemukan terdaftar pada ${usedCount} dari ${allResults.length} platform untuk email: ${email}`;

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
def api_scan(email: str = Query(..., description="Target email")):
    if not re.match(EMAIL_REGEX, email):
        raise HTTPException(status_code=400, detail="Format email tidak valid.")

    try:
        results = trio.run(run_holehe_async, email, 10)
        return {
            "email": email,
            "total": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

