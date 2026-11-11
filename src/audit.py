"""Data audit and anti-hallucination verification module for KIP equipment."""
from __future__ import annotations

import re
from typing import Dict, List, Set, Tuple
from src.models import ProductInput, DataQualityAudit, ProductCardDraft, AntiHallucinationCheck

# Recommended technical fields for KIP (Control and Measuring Instruments & Automation)
CRITICAL_KIP_FIELDS = [
    ("производитель", ["производитель", "бренд", "изготовитель", "марка"]),
    ("диапазон измерений / шкала", ["диапазон", "предел", "шкала", "вход"]),
    ("класс точности / погрешность", ["класс точности", "погрешность", "точность", "отклонение"]),
    ("выходные сигналы / интерфейсы", ["интерфейс", "выход", "протокол", "реле", "токовый выход"]),
    ("параметры электропитания", ["питание", "напряжение", "батаре", "потребляемая"]),
    ("условия эксплуатации", ["температура", "климатическое", "условия"]),
    ("степень защиты корпуса", ["ip", "пылевлаго", "защит", "корпус"]),
]


def audit_product_data(product: ProductInput) -> DataQualityAudit:
    """Analyze input completeness against standard B2B KIP requirements."""
    missing: List[str] = []
    recommendations: List[str] = []
    
    # Check manufacturer
    mfg = (product.manufacturer or "").strip()
    if not mfg or mfg.lower() in ["данных нет", "не указан", "unknown", ""]:
        missing.append("Производитель / торговая марка")
        recommendations.append("Укажите завод-изготовитель или бренд прибора (важно для B2B-клиентов и гарантийных обязательств).")

    # Lowercase combined specs keys for matching
    spec_keys = [k.lower() for k in product.specs.keys()]
    combined_text = f"{product.name} {product.description}".lower()

    # Check KIP-specific technical parameters
    found_count = 0
    total_checks = len(CRITICAL_KIP_FIELDS)
    
    for display_name, aliases in CRITICAL_KIP_FIELDS:
        matched = False
        # Check in specs keys
        for alias in aliases:
            if any(alias in sk for sk in spec_keys):
                matched = True
                break
        # Also check in name/description as fallback
        if not matched:
            for alias in aliases:
                if alias in combined_text:
                    matched = True
                    break
        
        if matched:
            found_count += 1
        else:
            missing.append(f"Параметр: {display_name}")
            recommendations.append(f"Рекомендуется добавить точное паспортное значение для: «{display_name}».")

    # Evaluate description fullness
    desc = (product.description or "").strip()
    if len(desc) < 80:
        missing.append("Текстовое описание назначения прибора")
        recommendations.append("Добавьте фрагмент паспорта или развернутое назначение прибора для лучшей SEO-индексации.")

    # Calculate 0-100 score
    score = int((found_count / total_checks) * 80)
    if mfg:
        score += 10
    if len(desc) >= 150:
        score += 10
    score = max(10, min(100, score))

    is_complete = len(missing) <= 1

    return DataQualityAudit(
        is_complete=is_complete,
        completeness_score=score,
        missing_fields=missing,
        recommendations=recommendations,
    )


class AntiHallucinationGuardrail:
    """Deterministic validator verifying that model output does not invent specs."""

    @staticmethod
    def verify(draft_specs: Dict[str, str], input_specs: Dict[str, str], raw_text: str) -> AntiHallucinationCheck:
        """Cross-checks every spec value against raw input data."""
        unverified: List[str] = []
        verified_count = 0

        # Normalization helper
        def normalize(s: str) -> str:
            # Replace comma with dot and normalize spacing
            return re.sub(r"\s+", " ", s.lower().replace(",", ".")).strip()

        corpus = normalize(raw_text)
        for k, v in input_specs.items():
            corpus += " " + normalize(f"{k} {v}")

        for k, val in draft_specs.items():
            val_clean = val.strip()
            if not val_clean or val_clean.lower() in ["данных нет", "не указано", "нет данных", "н/д"]:
                verified_count += 1
                continue

            # Check if numbers from the value exist in the input corpus
            numbers = re.findall(r"\d+(?:[.,]\d+)?", val_clean)
            
            # If value contains specific numbers (e.g. 100, 0.03, 220), they MUST be in the source
            num_mismatch = False
            for num in numbers:
                num_norm = num.replace(",", ".")
                # Check for exact substring match or stripped match
                if num_norm not in corpus and num not in corpus:
                    num_mismatch = True
                    break

            if num_mismatch:
                unverified.append(f"{k}: {val} (числовые значения отсутствуют в исходных данных)")
            else:
                verified_count += 1

        passed = len(unverified) == 0
        return AntiHallucinationCheck(
            passed=passed,
            verified_specs_count=verified_count,
            unverified_values=unverified,
        )
