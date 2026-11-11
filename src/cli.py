"""Command-line interface for batch processing and generating sample results."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.models import ProductInput
from src.generator import LLMCardGenerator, format_markdown_card


def process_file(generator: LLMCardGenerator, input_path: Path, output_dir: Path, force_offline: bool = False):
    print(f"[*] Обработка: {input_path.name}...")
    try:
        raw_data = json.loads(input_path.read_text(encoding="utf-8"))
        product = ProductInput(**raw_data)
    except Exception as e:
        print(f"[-] Ошибка чтения/валидации файла {input_path}: {e}")
        return

    res = generator.generate(product, force_offline=force_offline)
    if not res.success or not res.draft:
        print(f"[-] Ошибка генерации для {input_path.name}: {res.error}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = input_path.stem
    json_out = output_dir / f"{stem}_draft.json"
    md_out = output_dir / f"{stem}_card.md"

    json_out.write_text(json.dumps(res.draft.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    md_out.write_text(res.markdown or "", encoding="utf-8")

    audit = res.draft.data_quality_audit
    status_str = "ПОЛНЫЕ" if audit.is_complete else "ТРЕБУЮТ УТОЧНЕНИЯ"
    print(f"    -> Готово! Длина описания: {res.draft.seo_description_length} симв. (Title: {len(res.draft.seo_title)}/70). Данные: {status_str} ({audit.completeness_score}/100)")
    print(f"    -> Сохранено: {md_out.name} и {json_out.name}")


def main():
    parser = argparse.ArgumentParser(description="СОЮЗ-ПРИБОР AI Card Generator CLI")
    parser.add_argument("--input", "-i", type=str, help="Путь к входному JSON файлу прибора")
    parser.add_argument("--output", "-o", type=str, default="examples", help="Папка для сохранения результатов")
    parser.add_argument("--run-all-samples", action="store_true", help="Сгенерировать результаты для всех тестовых товаров")
    parser.add_argument("--force-offline", action="store_true", help="Использовать встроенный детерминированный генератор без API")

    args = parser.parse_args()
    generator = LLMCardGenerator()
    out_dir = Path(args.output)

    if args.run_all_samples:
        samples_dir = Path(__file__).resolve().parent.parent / "data" / "samples"
        for sample_file in sorted(samples_dir.glob("*.json")):
            process_file(generator, sample_file, out_dir, force_offline=args.force_offline)
        print("\n[+] Все примеры успешно обработаны и сохранены в папку:", out_dir)
        return

    if args.input:
        in_path = Path(args.input)
        if not in_path.exists():
            print(f"[-] Файл не найден: {in_path}")
            sys.exit(1)
        process_file(generator, in_path, out_dir, force_offline=args.force_offline)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
