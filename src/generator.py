"""Core generator orchestrating LLM calls, deterministic fallback, and formatting."""
from __future__ import annotations

import os
import json
import time
import re
from typing import Dict, Any, Tuple
import requests

from src.models import (
    ProductInput,
    ProductCardDraft,
    CommercialBlock,
    GenerateResponse,
    AntiHallucinationCheck,
)
from src.audit import audit_product_data, AntiHallucinationGuardrail
from src.prompts import SYSTEM_PROMPT, build_user_prompt


def format_markdown_card(draft: ProductCardDraft) -> str:
    """Format draft into clean GitHub-flavored Markdown for content managers."""
    lines = []
    lines.append(f"# {draft.product_name}")
    lines.append(f"**Производитель:** {draft.manufacturer}\n")
    
    lines.append("## SEO Метаданные")
    lines.append(f"- **SEO Title ({len(draft.seo_title)}/70 символов):** {draft.seo_title}")
    lines.append(f"- **Символов в описании:** {draft.seo_description_length} (норма: 800-1200)")
    lines.append("\n### Поисковые запросы (Keywords):")
    for q in draft.search_queries:
        lines.append(f"  * `{q}`")

    lines.append("\n## Описание товара (для карточки каталога)")
    lines.append(draft.seo_description)

    lines.append("\n## Ключевые технические характеристики")
    lines.append("| Параметр | Значение |")
    lines.append("| :--- | :--- |")
    for k, v in draft.key_specs.items():
        lines.append(f"| {k} | {v} |")

    lines.append("\n## Коммерческий блок (для отдела продаж)")
    lines.append(f"**Целевая аудитория:** {draft.commercial_block.target_audience}\n")
    lines.append("**Типовые сценарии применения:**")
    for uc in draft.commercial_block.use_cases:
        lines.append(f"- {uc}")
    lines.append("\n**Преимущества для заказчика:**")
    for b in draft.commercial_block.key_benefits:
        lines.append(f"- {b}")

    lines.append("\n## Аудит полноты данных")
    audit = draft.data_quality_audit
    status_label = "✅ Данные полные" if audit.is_complete else "⚠️ Требуется дополнение"
    lines.append(f"**Статус:** {status_label} (Оценка полноты: {audit.completeness_score}/100)")
    if audit.missing_fields:
        lines.append("\n**Отсутствующие важные поля:**")
        for mf in audit.missing_fields:
            lines.append(f"- {mf}")
    if audit.recommendations:
        lines.append("\n**Рекомендации контент-менеджеру:**")
        for rec in audit.recommendations:
            lines.append(f"- {rec}")

    lines.append(f"\n*Проверка на отсутствие выдуманных параметров (Anti-Hallucination):* {'Пройдена' if draft.anti_hallucination.passed else 'Обнаружены расхождения'}")
    return "\n".join(lines)


class DeterministicOfflineEngine:
    """High-quality offline template generator used when no external API key is provided."""

    @classmethod
    def generate(cls, product: ProductInput) -> ProductCardDraft:
        mfg = (product.manufacturer or "").strip() or "данных нет"
        
        # Build SEO title (strictly <= 70 chars)
        title_candidate = f"{product.name}: купить, цена | СОЮЗ-ПРИБОР"
        if len(title_candidate) > 70:
            title_candidate = f"{product.name} | СОЮЗ-ПРИБОР"
        if len(title_candidate) > 70:
            title_candidate = title_candidate[:67].rsplit(" ", 1)[0] + "..."
        seo_title = title_candidate

        # Format key specs (strictly from input)
        key_specs = dict(product.specs)
        if not key_specs:
            key_specs["основные характеристики"] = "данных нет (требуется уточнение по паспорту изделия)"

        # Generate grounded SEO description (target 800 - 1200 characters)
        specs_summary = "; ".join([f"{k}: {v}" for k, v in list(key_specs.items())[:6]])
        base_desc = (product.description or "").strip()
        
        paragraphs = []
        p1 = f"{product.name} от производителя {mfg} представляет собой специализированное контрольно-измерительное решение для применения в промышленности, энергетике и автоматизированных производственных комплексах. Оборудование предназначено для стабильного контроля технологических параметров и интеграции в единые контуры мониторинга предприятий."
        paragraphs.append(p1)

        p2 = f"В перечень подтвержденных рабочих параметров прибора входят следующие показатели: {specs_summary}. Соблюдение регламентированных метрологических стандартов и применение надежной элементной базы обеспечивают долговременную стабильность калибровки, высокую помехоустойчивость и безопасность при непрерывной эксплуатации на объекте."
        paragraphs.append(p2)

        if base_desc:
            p3 = f"Функциональное назначение и специфика эксплуатации: {base_desc} Прибор оптимизирован для снижения трудоемкости монтажных и сервисных работ, а также оперативной локализации отклонений в технологических процессах."
            paragraphs.append(p3)
        else:
            p3 = f"Прибор спроектирован с учетом жестких требований к промышленным средствам автоматизации и измерения. Оборудование полностью совместимо со стандартными узлами крепления и коммуникационными линиями отечественных и зарубежных АСУ ТП."
            paragraphs.append(p3)

        p4 = f"Компания «СОЮЗ-ПРИБОР» осуществляет официальные поставки {product.name} с предоставлением заводской гарантии, технической документации и метрологической поддержки. Для заказа оборудования и согласования условий поставки свяжитесь со специалистами отдела продаж."
        paragraphs.append(p4)

        combined_desc = "\n\n".join(paragraphs)
        
        # Adjust length strictly into 800 - 1200 range
        if len(combined_desc) > 1200:
            combined_desc = combined_desc[:1190].rsplit(".", 1)[0] + "."
        elif len(combined_desc) < 800:
            filler = f" За дополнительными консультациями по подбору приборов аналогичного назначения и расчету стоимости обратитесь к инженерам СОЮЗ-ПРИБОР."
            combined_desc += filler

        # Build search queries (3-5 queries)
        queries = [
            f"купить {product.name.lower()}",
            f"{product.name.lower()} цена",
            f"{product.name.lower()} характеристики",
        ]
        if mfg and mfg != "данных нет":
            queries.append(f"{mfg.lower()} {product.name.lower()}")
        if len(queries) < 4:
            queries.append(f"{product.name.lower()} паспорт")

        # Commercial block
        comm_audience = f"Инженеры КИПиА, технологи промышленных производств, отделы материально-технического снабжения и системные интеграторы АСУ ТП."
        if "testo" in product.name.lower() or "манометр" in product.name.lower():
            comm_audience = "Службы наладки газового хозяйства, котельных, систем отопления, вентиляции и кондиционирования (ОВиК), энергоаудиторы."
        elif "модуль" in product.name.lower() or "овен" in product.name.lower() or "rs-485" in str(product.specs).lower():
            comm_audience = "Проектировщики шкафов автоматики, разработчики распределенных систем диспетчеризации, инженеры АСУ ТП промышленных предприятий."

        comm_use_cases = [
            "Непрерывный производственный контроль и мониторинг регламентных технологических параметров.",
            "Плановое сервисное обслуживание, наладка и диагностика технологического оборудования.",
            "Интеграция в существующие и вновь проектируемые контуры автоматизации предприятий.",
        ]

        comm_benefits = [
            "Полное соответствие заявленным паспортным характеристикам завода-изготовителя.",
            "Простота монтажа, стандартное подключение и готовность к работе в промышленных условиях.",
            "Официальная гарантия и техническая консультационная поддержка от компании «СОЮЗ-ПРИБОР».",
        ]

        audit = audit_product_data(product)
        hallucination_check = AntiHallucinationGuardrail.verify(
            draft_specs=key_specs,
            input_specs=product.specs,
            raw_text=f"{product.name} {product.manufacturer} {product.description}"
        )

        return ProductCardDraft(
            product_name=product.name,
            manufacturer=mfg,
            seo_title=seo_title,
            seo_description=combined_desc,
            seo_description_length=len(combined_desc),
            key_specs=key_specs,
            search_queries=queries[:5],
            commercial_block=CommercialBlock(
                target_audience=comm_audience,
                use_cases=comm_use_cases,
                key_benefits=comm_benefits,
            ),
            data_quality_audit=audit,
            anti_hallucination=hallucination_check,
        )


class LLMCardGenerator:
    """Orchestrator selecting online LLM API or deterministic offline engine."""

    def __init__(self):
        self.api_key = (
            os.getenv("OPENAI_API_KEY")
            or os.getenv("GROQ_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
            or os.getenv("LLM_API_KEY")
            or ""
        )
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    def generate(self, product: ProductInput, force_offline: bool = False) -> GenerateResponse:
        t0 = time.time()
        audit = audit_product_data(product)

        # Fallback to offline engine if no API key or forced
        if force_offline or not self.api_key or self.api_key.startswith("mock_"):
            draft = DeterministicOfflineEngine.generate(product)
            elapsed_ms = round((time.time() - t0) * 1000, 2)
            md = format_markdown_card(draft)
            return GenerateResponse(
                success=True,
                draft=draft,
                markdown=md,
                provider_used="DeterministicOfflineEngine (Встроенный генератор без зависимости от ключей)",
                execution_time_ms=elapsed_ms,
            )

        # Online LLM generation
        try:
            payload_input = {
                "name": product.name,
                "manufacturer": product.manufacturer or "данных нет",
                "specs": product.specs,
                "description": product.description,
            }
            user_prompt = build_user_prompt(json.dumps(payload_input, ensure_ascii=False, indent=2))
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            body = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,  # Low temperature for strict adherence to facts
                "response_format": {"type": "json_object"},
            }

            resp = requests.post(f"{self.base_url}/chat/completions", headers=headers, json=body, timeout=30)
            if resp.status_code != 200:
                raise RuntimeError(f"LLM API returned status {resp.status_code}: {resp.text[:200]}")

            data = resp.json()
            raw_content = data["choices"][0]["message"]["content"]
            parsed = json.loads(raw_content)

            # Ensure anti-hallucination verification
            extracted_specs = parsed.get("key_specs", {})
            hallucination_check = AntiHallucinationGuardrail.verify(
                draft_specs=extracted_specs,
                input_specs=product.specs,
                raw_text=f"{product.name} {product.manufacturer} {product.description}"
            )

            desc = parsed.get("seo_description", "")
            title = parsed.get("seo_title", "")
            if len(title) > 70:
                title = title[:67].rsplit(" ", 1)[0] + "..."

            comm_raw = parsed.get("commercial_block", {})
            comm_block = CommercialBlock(
                target_audience=comm_raw.get("target_audience", "Специалисты КИПиА и технологи производств."),
                use_cases=comm_raw.get("use_cases", ["Промышленный контроль параметров."]),
                key_benefits=comm_raw.get("key_benefits", ["Высокая надежность и точность."]),
            )

            draft = ProductCardDraft(
                product_name=parsed.get("product_name", product.name),
                manufacturer=parsed.get("manufacturer", product.manufacturer or "данных нет"),
                seo_title=title,
                seo_description=desc,
                seo_description_length=len(desc),
                key_specs=extracted_specs,
                search_queries=parsed.get("search_queries", [f"купить {product.name}"]),
                commercial_block=comm_block,
                data_quality_audit=audit,
                anti_hallucination=hallucination_check,
            )

            elapsed_ms = round((time.time() - t0) * 1000, 2)
            md = format_markdown_card(draft)
            return GenerateResponse(
                success=True,
                draft=draft,
                markdown=md,
                provider_used=f"LLM API ({self.model})",
                execution_time_ms=elapsed_ms,
            )

        except Exception as e:
            # Graceful fallback on API failure
            draft = DeterministicOfflineEngine.generate(product)
            elapsed_ms = round((time.time() - t0) * 1000, 2)
            md = format_markdown_card(draft)
            return GenerateResponse(
                success=True,
                draft=draft,
                markdown=md,
                error=f"Обращение к LLM API завершилось с ошибкой ({str(e)}), автоматически применен встроенный детерминированный движок.",
                provider_used="DeterministicOfflineEngine (Авто-fallback при сбое API)",
                execution_time_ms=elapsed_ms,
            )
