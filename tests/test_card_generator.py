"""Unit and integration tests for Soyuz-Pribor AI Card Generator."""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.models import ProductInput, ProductCardDraft
from src.audit import audit_product_data, AntiHallucinationGuardrail
from src.generator import DeterministicOfflineEngine, LLMCardGenerator
from src.app import app


@pytest.fixture
def sample_testo():
    p = Path(__file__).resolve().parent.parent / "data" / "samples" / "sample_1_testo_510.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    return ProductInput(**data)


@pytest.fixture
def sample_owen():
    p = Path(__file__).resolve().parent.parent / "data" / "samples" / "sample_2_owen_mk110.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    return ProductInput(**data)


@pytest.fixture
def sample_incomplete():
    p = Path(__file__).resolve().parent.parent / "data" / "samples" / "sample_3_incomplete_manometr.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    return ProductInput(**data)


def test_input_validation():
    # Empty name should fail
    with pytest.raises(ValueError):
        ProductInput(name="")

    # Missing specs should be handled gracefully as empty dict
    prod = ProductInput(name="Тестовый прибор")
    assert prod.specs == {}
    assert prod.manufacturer == ""


def test_seo_title_length_constraint(sample_testo, sample_owen):
    draft_testo = DeterministicOfflineEngine.generate(sample_testo)
    assert len(draft_testo.seo_title) <= 70, f"Title too long: {len(draft_testo.seo_title)}"

    draft_owen = DeterministicOfflineEngine.generate(sample_owen)
    assert len(draft_owen.seo_title) <= 70, f"Title too long: {len(draft_owen.seo_title)}"


def test_seo_description_length_constraint(sample_testo, sample_owen):
    draft_testo = DeterministicOfflineEngine.generate(sample_testo)
    assert 800 <= draft_testo.seo_description_length <= 1200, (
        f"Description length out of 800-1200 range: {draft_testo.seo_description_length}"
    )

    draft_owen = DeterministicOfflineEngine.generate(sample_owen)
    assert 800 <= draft_owen.seo_description_length <= 1200, (
        f"Description length out of 800-1200 range: {draft_owen.seo_description_length}"
    )


def test_search_queries_count(sample_testo):
    draft = DeterministicOfflineEngine.generate(sample_testo)
    assert 3 <= len(draft.search_queries) <= 5


def test_data_quality_audit_detects_missing_fields(sample_incomplete):
    audit = audit_product_data(sample_incomplete)
    assert not audit.is_complete
    assert audit.completeness_score < 80
    assert any("Производитель" in mf for mf in audit.missing_fields)
    assert len(audit.recommendations) > 0


def test_anti_hallucination_guardrail():
    # Valid specs matching source
    source_specs = {"диапазон": "0-100 гПа", "погрешность": "±0.03 гПа"}
    draft_specs = {"диапазон": "0-100 гПа", "погрешность": "±0.03 гПа"}
    res = AntiHallucinationGuardrail.verify(draft_specs, source_specs, "манометр testo 510 0-100 гПа")
    assert res.passed
    assert len(res.unverified_values) == 0

    # Hallucinated number that does not exist in source specs or text
    fake_specs = {"давление разрыва": "9999 бар"}
    res_fake = AntiHallucinationGuardrail.verify(fake_specs, source_specs, "манометр testo 510 0-100 гПа")
    assert not res_fake.passed
    assert len(res_fake.unverified_values) > 0


def test_api_health_and_samples():
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"

    resp_samples = client.get("/api/samples")
    assert resp_samples.status_code == 200
    samples = resp_samples.json()
    assert "sample_1_testo_510" in samples
    assert "sample_2_owen_mk110" in samples


def test_api_generate_endpoint(sample_testo):
    client = TestClient(app)
    payload = sample_testo.model_dump()
    resp = client.post("/api/generate?force_offline=true", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["draft"]["product_name"] == sample_testo.name
    assert len(data["draft"]["seo_title"]) <= 70
    assert 800 <= data["draft"]["seo_description_length"] <= 1200
    assert data["markdown"] is not None
