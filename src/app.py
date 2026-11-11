"""FastAPI Web application for Soyuz-Pribor AI Card Generator."""
from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Dict, Any, List

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from src.models import ProductInput, GenerateResponse
from src.generator import LLMCardGenerator

app = FastAPI(
    title="СОЮЗ-ПРИБОР AI-помощник",
    description="Сервис генерации черновиков карточек товаров КИПиА для B2B-интернет-магазина",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

generator = LLMCardGenerator()
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"


def load_samples() -> Dict[str, Dict[str, Any]]:
    samples = {}
    if SAMPLES_DIR.exists():
        for f in sorted(SAMPLES_DIR.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                samples[f.stem] = data
            except Exception:
                pass
    return samples


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "souz-pribor-ai-card-generator",
        "llm_model": generator.model,
        "has_api_key": bool(generator.api_key),
    }


@app.get("/api/samples")
async def get_samples():
    return load_samples()


@app.post("/api/generate", response_model=GenerateResponse)
async def generate_card(payload: Dict[str, Any], force_offline: bool = False):
    try:
        product = ProductInput(**payload)
    except ValidationError as ve:
        raise HTTPException(
            status_code=422,
            detail=f"Ошибка валидации входных данных: {ve.errors()}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Некорректный JSON прибора: {str(e)}"
        )

    res = generator.generate(product, force_offline=force_offline)
    return res


@app.get("/", response_class=HTMLResponse)
async def index():
    html_content = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>СОЮЗ-ПРИБОР | AI-генератор карточек товаров КИПиА</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    pre { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
  </style>
</head>
<body class="bg-slate-50 text-slate-900 min-h-screen">
  
  <!-- Header -->
  <header class="bg-slate-900 border-b border-slate-800 text-white py-4 px-6 sticky top-0 z-20 shadow-md">
    <div class="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded bg-blue-600 flex items-center justify-center font-bold text-xl text-white shadow">СП</div>
        <div>
          <h1 class="text-lg font-bold tracking-tight">СОЮЗ-ПРИБОР • AI-генератор карточек товаров</h1>
          <p class="text-xs text-slate-400">Автоматическая подготовка B2B-описаний КИПиА с защитой от галлюцинаций</p>
        </div>
      </div>
      <div class="flex items-center gap-3 text-xs">
        <span class="px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700 text-slate-300">
          <i class="fa-solid fa-shield-halved text-emerald-400 mr-1"></i> Zero-Hallucination Guardrail
        </span>
        <span class="px-2.5 py-1 rounded-full bg-slate-800 border border-slate-700 text-slate-300">
          <i class="fa-solid fa-robot text-blue-400 mr-1"></i> LLM API + Offline Mode
        </span>
      </div>
    </div>
  </header>

  <!-- Main Container -->
  <main class="max-w-7xl mx-auto p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
    
    <!-- Left Column: Input Form -->
    <div class="lg:col-span-5 space-y-4">
      <div class="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        <div class="flex items-center justify-between mb-3">
          <h2 class="font-bold text-slate-800 flex items-center gap-2">
            <i class="fa-solid fa-file-code text-blue-600"></i> Входные данные о приборе
          </h2>
          <span class="text-xs text-slate-500">JSON / Форма</span>
        </div>

        <!-- Quick Sample Pickers -->
        <div class="mb-4">
          <label class="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">Быстрая загрузка из каталога:</label>
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <button onclick="loadSample('sample_1_testo_510')" class="px-2.5 py-1.5 text-xs text-left bg-blue-50 hover:bg-blue-100 text-blue-800 border border-blue-200 rounded-lg transition font-medium">
              <i class="fa-solid fa-gauge mr-1"></i> Testo 510
            </button>
            <button onclick="loadSample('sample_2_owen_mk110')" class="px-2.5 py-1.5 text-xs text-left bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200 rounded-lg transition font-medium">
              <i class="fa-solid fa-microchip mr-1"></i> ОВЕН МК110
            </button>
            <button onclick="loadSample('sample_3_incomplete_manometr')" class="px-2.5 py-1.5 text-xs text-left bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 rounded-lg transition font-medium">
              <i class="fa-solid fa-triangle-exclamation mr-1"></i> Неполные данные
            </button>
          </div>
        </div>

        <!-- JSON Editor Area -->
        <div class="space-y-2">
          <div class="flex justify-between items-center text-xs text-slate-500">
            <span>JSON структура (name, manufacturer, specs, description):</span>
            <button onclick="formatJson()" class="text-blue-600 hover:underline">Форматировать</button>
          </div>
          <textarea id="jsonInput" rows="16" class="w-full font-mono text-xs p-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-blue-500 focus:outline-none bg-slate-900 text-slate-100" placeholder="Вставьте JSON товара..."></textarea>
        </div>

        <!-- Action Buttons -->
        <div class="mt-4 flex flex-col sm:flex-row gap-2">
          <button id="btnGenerate" onclick="submitGenerate(false)" class="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 px-4 rounded-lg shadow-sm transition flex items-center justify-center gap-2">
            <i class="fa-solid fa-wand-magic-sparkles"></i> Сформировать карточку
          </button>
          <button onclick="submitGenerate(true)" title="Генерация без обращения к внешним LLM API" class="bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs px-3 py-2.5 rounded-lg border border-slate-300 transition flex items-center justify-center gap-1">
            <i class="fa-solid fa-bolt"></i> Офлайн режим
          </button>
        </div>
      </div>
    </div>

    <!-- Right Column: Results & Previews -->
    <div class="lg:col-span-7 space-y-4">
      
      <!-- Output Tabs Container -->
      <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        
        <!-- Tabs Header -->
        <div class="border-b border-slate-200 bg-slate-50 px-4 pt-3 flex flex-wrap items-center justify-between gap-2">
          <div class="flex space-x-1" id="tabButtons">
            <button onclick="switchTab('tabCard')" id="tabBtn-tabCard" class="px-3.5 py-2 font-medium text-xs rounded-t-lg bg-white border-t-2 border-blue-600 text-blue-600 shadow-sm">
              <i class="fa-solid fa-id-card mr-1"></i> Готовая карточка
            </button>
            <button onclick="switchTab('tabMarkdown')" id="tabBtn-tabMarkdown" class="px-3.5 py-2 font-medium text-xs rounded-t-lg text-slate-600 hover:text-slate-900">
              <i class="fa-brands fa-markdown mr-1"></i> Markdown
            </button>
            <button onclick="switchTab('tabJson')" id="tabBtn-tabJson" class="px-3.5 py-2 font-medium text-xs rounded-t-lg text-slate-600 hover:text-slate-900">
              <i class="fa-solid fa-code mr-1"></i> JSON результат
            </button>
          </div>
          <div class="flex items-center gap-2 pb-2">
            <button onclick="copyCurrentTab()" class="text-xs bg-white hover:bg-slate-100 border border-slate-300 px-2.5 py-1 rounded shadow-sm text-slate-700 transition">
              <i class="fa-regular fa-copy mr-1"></i> Копировать
            </button>
          </div>
        </div>

        <!-- Placeholder State -->
        <div id="emptyState" class="p-12 text-center text-slate-400">
          <i class="fa-solid fa-clipboard-list text-4xl mb-3 text-slate-300"></i>
          <p class="text-sm font-medium">Выберите товар слева или вставьте свой JSON и нажмите «Сформировать карточку»</p>
        </div>

        <!-- Loading State -->
        <div id="loadingState" class="hidden p-12 text-center text-slate-600">
          <i class="fa-solid fa-circle-notch fa-spin text-3xl text-blue-600 mb-3"></i>
          <p class="text-sm font-medium">Обработка технических данных и генерация черновика...</p>
        </div>

        <!-- Results Content -->
        <div id="resultContainer" class="hidden p-5 space-y-5">
          
          <!-- Metadata Bar -->
          <div class="flex flex-wrap items-center justify-between text-xs pb-3 border-b border-slate-100 text-slate-500 gap-2">
            <span id="providerBadge" class="px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200"></span>
            <span id="timingBadge"></span>
          </div>

          <!-- Tab 1: Rendered Card -->
          <div id="tabCard" class="space-y-5">
            
            <!-- Audit Banner -->
            <div id="auditBanner" class="p-3.5 rounded-lg text-xs border"></div>

            <!-- SEO Block -->
            <div class="bg-slate-50 rounded-lg p-4 border border-slate-200 space-y-2">
              <div class="flex justify-between items-baseline">
                <span class="text-xs font-bold uppercase tracking-wider text-slate-600">SEO-заголовок (Title):</span>
                <span id="seoTitleLen" class="text-xs px-2 py-0.5 rounded bg-slate-200 font-mono"></span>
              </div>
              <div id="cardSeoTitle" class="text-base font-bold text-slate-900"></div>

              <div class="pt-2">
                <span class="text-xs font-bold uppercase tracking-wider text-slate-600">Поисковые фразы (Keywords):</span>
                <div id="cardQueries" class="flex flex-wrap gap-1.5 mt-1.5"></div>
              </div>
            </div>

            <!-- Product Description -->
            <div>
              <div class="flex justify-between items-baseline mb-1">
                <h3 class="text-sm font-bold text-slate-800 uppercase tracking-wide">SEO-описание для карточки товара:</h3>
                <span id="descLenBadge" class="text-xs font-mono px-2 py-0.5 rounded"></span>
              </div>
              <div id="cardDescription" class="text-sm text-slate-700 leading-relaxed bg-white p-4 rounded-lg border border-slate-200 whitespace-pre-line"></div>
            </div>

            <!-- Specs Table -->
            <div>
              <h3 class="text-sm font-bold text-slate-800 uppercase tracking-wide mb-2">Технические характеристики (строго из источника):</h3>
              <div class="overflow-x-auto rounded-lg border border-slate-200">
                <table class="w-full text-xs text-left">
                  <thead class="bg-slate-100 text-slate-700 uppercase font-semibold">
                    <tr>
                      <th class="py-2.5 px-3 w-1/2">Параметр</th>
                      <th class="py-2.5 px-3 w-1/2">Значение</th>
                    </tr>
                  </thead>
                  <tbody id="cardSpecsTable" class="divide-y divide-slate-200"></tbody>
                </table>
              </div>
            </div>

            <!-- Commercial Block -->
            <div class="bg-amber-50/70 border border-amber-200 rounded-lg p-4 space-y-3">
              <h3 class="text-xs font-bold uppercase tracking-wider text-amber-900 flex items-center gap-1.5">
                <i class="fa-solid fa-briefcase"></i> Коммерческий блок для менеджеров по продажам
              </h3>
              <div class="text-xs text-amber-950">
                <strong>Целевая аудитория:</strong> <span id="cardAudience"></span>
              </div>
              <div class="text-xs text-amber-950">
                <strong>Типовые задачи:</strong>
                <ul id="cardUseCases" class="list-disc pl-4 space-y-1 mt-1"></ul>
              </div>
              <div class="text-xs text-amber-950">
                <strong>Ключевые преимущества:</strong>
                <ul id="cardBenefits" class="list-disc pl-4 space-y-1 mt-1"></ul>
              </div>
            </div>

          </div>

          <!-- Tab 2: Markdown -->
          <div id="tabMarkdown" class="hidden">
            <textarea id="markdownOutput" readonly rows="20" class="w-full font-mono text-xs p-3 rounded-lg border border-slate-300 bg-slate-900 text-slate-100 focus:outline-none"></textarea>
          </div>

          <!-- Tab 3: JSON Result -->
          <div id="tabJson" class="hidden">
            <textarea id="jsonOutput" readonly rows="20" class="w-full font-mono text-xs p-3 rounded-lg border border-slate-300 bg-slate-900 text-slate-100 focus:outline-none"></textarea>
          </div>

        </div>

      </div>

    </div>

  </main>

  <script>
    let samplesCache = {};
    let lastResult = null;
    let activeTab = 'tabCard';

    // Fetch samples on load
    window.addEventListener('DOMContentLoaded', async () => {
      try {
        const resp = await fetch('/api/samples');
        samplesCache = await resp.json();
        // Load first sample by default
        loadSample('sample_1_testo_510');
      } catch (err) {
        console.error('Failed to load samples:', err);
      }
    });

    function loadSample(key) {
      if (samplesCache[key]) {
        document.getElementById('jsonInput').value = JSON.stringify(samplesCache[key], null, 2);
      }
    }

    function formatJson() {
      try {
        const val = JSON.parse(document.getElementById('jsonInput').value);
        document.getElementById('jsonInput').value = JSON.stringify(val, null, 2);
      } catch (e) {
        alert('Некорректный JSON: ' + e.message);
      }
    }

    function switchTab(tabId) {
      activeTab = tabId;
      ['tabCard', 'tabMarkdown', 'tabJson'].forEach(t => {
        const el = document.getElementById(t);
        const btn = document.getElementById('tabBtn-' + t);
        if (t === tabId) {
          el.classList.remove('hidden');
          btn.className = 'px-3.5 py-2 font-medium text-xs rounded-t-lg bg-white border-t-2 border-blue-600 text-blue-600 shadow-sm';
        } else {
          el.classList.add('hidden');
          btn.className = 'px-3.5 py-2 font-medium text-xs rounded-t-lg text-slate-600 hover:text-slate-900';
        }
      });
    }

    async function submitGenerate(forceOffline) {
      const raw = document.getElementById('jsonInput').value.trim();
      let payload;
      try {
        payload = JSON.parse(raw);
      } catch (e) {
        alert('Пожалуйста, введите валидный JSON: ' + e.message);
        return;
      }

      document.getElementById('emptyState').classList.add('hidden');
      document.getElementById('resultContainer').classList.add('hidden');
      document.getElementById('loadingState').classList.remove('hidden');

      try {
        const resp = await fetch('/api/generate?force_offline=' + (forceOffline ? 'true' : 'false'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!resp.ok) {
          const err = await resp.json();
          throw new Error(err.detail || 'Ошибка генерации');
        }

        const data = await resp.json();
        lastResult = data;
        renderResult(data);
      } catch (err) {
        alert('Ошибка при генерации карточки: ' + err.message);
      } finally {
        document.getElementById('loadingState').classList.add('hidden');
      }
    }

    function renderResult(data) {
      document.getElementById('resultContainer').classList.remove('hidden');
      const draft = data.draft;

      // Meta
      document.getElementById('providerBadge').innerText = data.provider_used;
      document.getElementById('timingBadge').innerText = 'Время обработки: ' + data.execution_time_ms + ' мс';

      // Audit Banner
      const ab = document.getElementById('auditBanner');
      const audit = draft.data_quality_audit;
      if (audit.is_complete) {
        ab.className = 'p-3.5 rounded-lg text-xs border bg-emerald-50 border-emerald-200 text-emerald-900';
        ab.innerHTML = '<div class="font-bold flex items-center gap-1.5"><i class="fa-solid fa-check-circle text-emerald-600"></i> Исходные данные полные (' + audit.completeness_score + '/100)</div><div class="mt-1 text-emerald-800">Все ключевые метрологические поля присутствуют. Карточка готова к публикации.</div>';
      } else {
        ab.className = 'p-3.5 rounded-lg text-xs border bg-amber-50 border-amber-200 text-amber-900';
        let html = '<div class="font-bold flex items-center gap-1.5"><i class="fa-solid fa-triangle-exclamation text-amber-600"></i> Обнаружены пропуски в данных (' + audit.completeness_score + '/100)</div>';
        if (audit.missing_fields.length) {
          html += '<div class="mt-1 font-semibold">Отсутствуют: ' + audit.missing_fields.join(', ') + '</div>';
        }
        if (audit.recommendations.length) {
          html += '<div class="mt-1 text-xs text-amber-800">Рекомендация: ' + audit.recommendations[0] + '</div>';
        }
        ab.innerHTML = html;
      }

      // Title
      document.getElementById('cardSeoTitle').innerText = draft.seo_title;
      const tlen = draft.seo_title.length;
      const tBadge = document.getElementById('seoTitleLen');
      tBadge.innerText = tlen + ' / 70 символов';
      tBadge.className = tlen <= 70 ? 'text-xs px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 font-mono' : 'text-xs px-2 py-0.5 rounded bg-red-100 text-red-800 font-mono';

      // Queries
      const qContainer = document.getElementById('cardQueries');
      qContainer.innerHTML = '';
      draft.search_queries.forEach(q => {
        const span = document.createElement('span');
        span.className = 'px-2 py-0.5 rounded bg-blue-100 text-blue-800 text-xs font-medium';
        span.innerText = q;
        qContainer.appendChild(span);
      });

      // Description
      document.getElementById('cardDescription').innerText = draft.seo_description;
      const dlen = draft.seo_description_length;
      const dBadge = document.getElementById('descLenBadge');
      dBadge.innerText = dlen + ' символов (норма: 800-1200)';
      dBadge.className = (dlen >= 800 && dlen <= 1200) ? 'text-xs font-mono px-2 py-0.5 rounded bg-emerald-100 text-emerald-800' : 'text-xs font-mono px-2 py-0.5 rounded bg-amber-100 text-amber-800';

      // Specs Table
      const tb = document.getElementById('cardSpecsTable');
      tb.innerHTML = '';
      for (const [k, v] of Object.entries(draft.key_specs)) {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-50';
        tr.innerHTML = '<td class="py-2 px-3 font-medium text-slate-800">' + k + '</td><td class="py-2 px-3 text-slate-600">' + v + '</td>';
        tb.appendChild(tr);
      }

      // Commercial
      document.getElementById('cardAudience').innerText = draft.commercial_block.target_audience;
      const ucList = document.getElementById('cardUseCases');
      ucList.innerHTML = '';
      draft.commercial_block.use_cases.forEach(uc => {
        const li = document.createElement('li');
        li.innerText = uc;
        ucList.appendChild(li);
      });
      const benList = document.getElementById('cardBenefits');
      benList.innerHTML = '';
      draft.commercial_block.key_benefits.forEach(b => {
        const li = document.createElement('li');
        li.innerText = b;
        benList.appendChild(li);
      });

      // Markdown & JSON Tabs
      document.getElementById('markdownOutput').value = data.markdown || '';
      document.getElementById('jsonOutput').value = JSON.stringify(data.draft, null, 2);
    }

    function copyCurrentTab() {
      if (!lastResult) return;
      let textToCopy = '';
      if (activeTab === 'tabCard') {
        textToCopy = lastResult.markdown;
      } else if (activeTab === 'tabMarkdown') {
        textToCopy = document.getElementById('markdownOutput').value;
      } else if (activeTab === 'tabJson') {
        textToCopy = document.getElementById('jsonOutput').value;
      }
      navigator.clipboard.writeText(textToCopy).then(() => {
        alert('Скопировано в буфер обмена!');
      });
    }
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)
