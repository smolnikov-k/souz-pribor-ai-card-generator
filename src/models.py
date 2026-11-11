"""Data models and schemas for Soyuz-Pribor AI Card Generator."""
from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class ProductInput(BaseModel):
    """Raw product input schema from JSON or Web form."""
    name: str = Field(..., min_length=2, description="Название прибора или модели")
    manufacturer: Optional[str] = Field(default="", description="Производитель / бренд")
    source_url: Optional[str] = Field(default="", description="Ссылка на товар в каталоге")
    specs: Dict[str, str] = Field(default_factory=dict, description="Технические характеристики (ключ-значение)")
    description: Optional[str] = Field(default="", description="Текстовое описание или выдержка из паспорта")

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Название товара не может быть пустым.")
        return v

    @field_validator("specs", mode="before")
    @classmethod
    def clean_specs(cls, v: object) -> Dict[str, str]:
        if not isinstance(v, dict):
            return {}
        cleaned = {}
        for k, val in v.items():
            if k and str(k).strip():
                cleaned[str(k).strip()] = str(val).strip() if val is not None else "данных нет"
        return cleaned


class DataQualityAudit(BaseModel):
    """Audit of input completeness with missing and recommended fields."""
    is_complete: bool = Field(..., description="Флаг достаточной полноты исходных данных")
    completeness_score: int = Field(..., ge=0, le=100, description="Оценка полноты данных в процентах (0-100)")
    missing_fields: List[str] = Field(default_factory=list, description="Критические или рекомендуемые поля, которые отсутствуют во входных данных")
    recommendations: List[str] = Field(default_factory=list, description="Рекомендации контент-менеджеру по дополнению карточки")


class CommercialBlock(BaseModel):
    """Commercial overview for sales managers and B2B buyers."""
    target_audience: str = Field(..., description="Кому подходит прибор: отрасли, роли специалистов")
    use_cases: List[str] = Field(..., description="Типовые производственные и сервисные задачи, которые решает прибор")
    key_benefits: List[str] = Field(..., description="Ключевые эксплуатационные преимущества")


class AntiHallucinationCheck(BaseModel):
    """Verification results to ensure zero-hallucination compliance."""
    passed: bool = Field(True, description="Прошла ли генерация проверку на соответствие входным данным")
    verified_specs_count: int = Field(0, description="Количество параметров, сверенных с источником")
    unverified_values: List[str] = Field(default_factory=list, description="Значения, которых не было во входных данных (должно быть пустым)")


class ProductCardDraft(BaseModel):
    """Standardized output card draft for B2B e-commerce."""
    product_name: str = Field(..., description="Наименование товара")
    manufacturer: str = Field(..., description="Производитель («данных нет», если не указан)")
    
    seo_title: str = Field(
        ...,
        description="SEO-заголовок (title), строго до 70 символов"
    )
    seo_description: str = Field(
        ...,
        description="SEO-описание для карточки товара, целевой объем 800-1200 символов"
    )
    seo_description_length: int = Field(
        ...,
        description="Фактическое количество символов в SEO-описании"
    )
    
    key_specs: Dict[str, str] = Field(
        ...,
        description="Структурированный список ключевых характеристик (только из входных данных)"
    )
    search_queries: List[str] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="3-5 целевых поисковых запросов для оптимизации страницы"
    )
    commercial_block: CommercialBlock = Field(
        ...,
        description="Коммерческий блок для менеджеров и заказчиков"
    )
    data_quality_audit: DataQualityAudit = Field(
        ...,
        description="Отчет о полноте данных и недостающих полях"
    )
    anti_hallucination: AntiHallucinationCheck = Field(
        default_factory=AntiHallucinationCheck,
        description="Результаты проверки на отсутствие выдуманных характеристик"
    )

    @field_validator("seo_title")
    @classmethod
    def validate_title_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) > 70:
            # Safely truncate if a model slightly exceeded 70 chars
            truncated = v[:67].rsplit(" ", 1)[0] + "..."
            return truncated if len(truncated) <= 70 else v[:70]
        return v


class GenerateResponse(BaseModel):
    """API response envelope."""
    success: bool
    draft: Optional[ProductCardDraft] = None
    markdown: Optional[str] = None
    error: Optional[str] = None
    provider_used: str = "offline_engine"
    execution_time_ms: float = 0.0
