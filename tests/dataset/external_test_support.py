"""Synthetic fixtures for external data governance tests."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = REPO_ROOT / "configs/training/external-source-schema-v0.1.json"
MAPPING = REPO_ROOT / "configs/training/external-class-mapping-v0.1.json"


def write_image(path: Path, value: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.full((24, 32, 3), value, dtype=np.uint8)
    image[4:20, 5:27] = (value + 60) % 255
    assert cv2.imwrite(str(path), image)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def coco_document(
    images: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
    categories: list[dict[str, Any]],
) -> dict[str, Any]:
    return {"images": images, "annotations": annotations, "categories": categories}


def create_external_fixture(root: Path) -> dict[str, Path]:
    external = root / "external"
    (external / "reports").mkdir(parents=True)
    (external / "converted/manifests").mkdir(parents=True)
    (external / "quarantine/manifests").mkdir(parents=True)
    (external / "registry/licenses").mkdir(parents=True)
    (external / "registry/citations").mkdir(parents=True)
    (external / "registry/licenses/CC-BY-4.0-legalcode.txt").write_text(
        "CC BY 4.0 fixture", encoding="utf-8"
    )

    source_ids = [
        "roboflow-defect-cardboard-h0kjy-v1",
        "roboflow-damaged-box-detection-v1",
        "zenodo-tampar-10057090",
    ]
    for source_id in source_ids:
        (external / f"registry/citations/{source_id}.bib").write_text(
            f"@misc{{{source_id}}}\n", encoding="utf-8"
        )

    defect_root = external / "raw/roboflow/defect-cardboard-h0kjy/extracted"
    categories = [
        {"id": 1, "name": "dent"},
        {"id": 2, "name": "hole"},
        {"id": 3, "name": "dirt"},
        {"id": 4, "name": "defects-in-cardboards"},
    ]
    defect_specs = {
        "train": ("train.jpg", 10, [(1, 1), (2, 3)]),
        "valid": ("valid.jpg", 20, [(3, 2)]),
        "test": ("test.jpg", 30, [(4, 1)]),
    }
    for split, (name, value, anns) in defect_specs.items():
        image_path = defect_root / split / name
        write_image(image_path, value)
        images = [{"id": value, "file_name": name, "width": 32, "height": 24}]
        annotations = [
            {
                "id": ann_id,
                "image_id": value,
                "category_id": class_id,
                "bbox": [1, 2, 10, 11],
                "iscrowd": 0,
            }
            for ann_id, class_id in anns
        ]
        (defect_root / split / "_annotations.coco.json").write_text(
            json.dumps(coco_document(images, annotations, categories)), encoding="utf-8"
        )

    damaged_root = external / "raw/roboflow/damaged-box-detection/extracted"
    damaged_a = damaged_root / "train/damagedpackages/damaged-a.jpg"
    damaged_b = damaged_root / "train/damagedpackages/damaged-b.jpg"
    write_image(damaged_a, 40)
    damaged_b.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(damaged_a, damaged_b)
    write_image(damaged_root / "train/undamagedpackages/normal-a.jpg", 50)
    write_image(damaged_root / "valid/damagedpackages/damaged-valid.jpg", 60)
    write_image(damaged_root / "valid/undamagedpackages/normal-valid.jpg", 70)
    write_image(damaged_root / "test/damagedpackages/damaged-test.jpg", 80)
    write_image(damaged_root / "test/undamagedpackages/normal-test.jpg", 90)

    tampar_root = external / "raw/zenodo/tampar/extracted/tampar"
    base = tampar_root / "test/base/id_10_20200101_000000.jpg"
    probable = tampar_root / "test/floor/id_10_20200102_000000.jpg"
    unresolved = tampar_root / "test/stairs/id_99_20200102_000000.jpg"
    write_image(base, 100)
    write_image(probable, 110)
    write_image(unresolved, 120)
    write_image(tampar_root / "test/base/id_10_20200101_000000_uvmap_gt.png", 130)
    write_image(tampar_root / "uvmaps/id_10_uvmap.png", 140)
    test_coco = coco_document(
        [
            {
                "id": 1,
                "file_name": "test/base/id_10_20200101_000000.jpg",
                "width": 32,
                "height": 24,
            }
        ],
        [
            {
                "id": 1,
                "image_id": 1,
                "category_id": 0,
                "bbox": [1, 2, 10, 11],
                "segmentation": [[1, 2, 3, 4, 5, 6]],
                "keypoints": [1, 2, 2] * 8,
                "iscrowd": 0,
            }
        ],
        [{"id": 0, "name": "normal box"}, {"id": 1, "name": "damaged box"}],
    )
    (tampar_root / "tampar_test.json").write_text(
        json.dumps(test_coco), encoding="utf-8"
    )
    (tampar_root / "tampar_validation.json").write_text(
        json.dumps(coco_document([], [], test_coco["categories"])), encoding="utf-8"
    )

    stats_root = external / "public-stats/spb"
    raw_html = stats_root / "raw-html/article.html"
    raw_html.parent.mkdir(parents=True, exist_ok=True)
    raw_html.write_text("<html>fixture</html>", encoding="utf-8")
    import hashlib

    raw_hash = hashlib.sha256(raw_html.read_bytes()).hexdigest()
    url = "https://www.spb.gov.cn/example.shtml"
    write_csv(
        stats_root / "parsed-csv/spb-articles-2024-2026.csv",
        [
            "article_title",
            "publication_date",
            "content_source",
            "source_url",
            "retrieved_at",
            "raw_html_file",
            "raw_html_sha256",
            "content_text",
        ],
        [
            {
                "article_title": "Fixture",
                "publication_date": "2026-01-01",
                "content_source": "",
                "source_url": url,
                "retrieved_at": "2026-01-02T00:00:00+00:00",
                "raw_html_file": "article.html",
                "raw_html_sha256": raw_hash,
                "content_text": "fixture",
            }
        ],
    )
    write_csv(
        stats_root / "parsed-csv/spb-indicators-2024-2026.csv",
        [
            "article_title",
            "publication_date",
            "stat_period",
            "indicator",
            "value",
            "unit",
            "year_on_year_percent",
            "year_on_year_direction",
            "source_url",
            "retrieved_at",
            "raw_html_sha256",
        ],
        [
            {
                "article_title": "Fixture",
                "publication_date": "2026-01-01",
                "stat_period": "2025",
                "indicator": "快递业务量",
                "value": "100",
                "unit": "件",
                "year_on_year_percent": "1",
                "year_on_year_direction": "增长",
                "source_url": url,
                "retrieved_at": "2026-01-02T00:00:00+00:00",
                "raw_html_sha256": raw_hash,
            }
        ],
    )

    registry_fields = [
        "dataset_id",
        "dataset_name",
        "provider",
        "source_url",
        "version",
        "task_type",
        "declared_image_count",
        "declared_classes",
        "license",
        "author",
        "approved_action",
        "download_format",
        "download_status",
        "local_path",
        "mapping_status",
        "mapping_notes",
        "integrity_report",
    ]
    registry_rows = [
        {
            "dataset_id": source_ids[0],
            "dataset_name": "defect-cardboard",
            "provider": "Roboflow",
            "source_url": "https://example.invalid/defect",
            "version": "1",
            "task_type": "object-detection",
            "declared_image_count": "3",
            "declared_classes": "dent|hole|dirt",
            "license": "CC BY 4.0",
            "author": "fixture",
            "approved_action": "download",
            "download_format": "COCO",
            "download_status": "downloaded_verified",
            "local_path": "raw/roboflow/defect-cardboard-h0kjy",
            "mapping_status": "candidate_only",
            "mapping_notes": "fixture",
            "integrity_report": "reports/source-integrity.json",
        },
        {
            "dataset_id": source_ids[1],
            "dataset_name": "Damaged Box Detection",
            "provider": "Roboflow",
            "source_url": "https://example.invalid/damaged",
            "version": "1",
            "task_type": "single-label-classification",
            "declared_image_count": "7",
            "declared_classes": "damagedpackages|undamagedpackages",
            "license": "CC BY 4.0",
            "author": "fixture",
            "approved_action": "download",
            "download_format": "folder",
            "download_status": "downloaded_verified",
            "local_path": "raw/roboflow/damaged-box-detection",
            "mapping_status": "candidate_only",
            "mapping_notes": "fixture",
            "integrity_report": "reports/source-integrity.json",
        },
        {
            "dataset_id": source_ids[2],
            "dataset_name": "TAMPAR",
            "provider": "Zenodo",
            "source_url": "https://example.invalid/tampar",
            "version": "1",
            "task_type": "pair",
            "declared_image_count": "5",
            "declared_classes": "tamper",
            "license": "CC BY 4.0",
            "author": "fixture",
            "approved_action": "download",
            "download_format": "folder",
            "download_status": "downloaded_verified",
            "local_path": "raw/zenodo/tampar",
            "mapping_status": "audit_required",
            "mapping_notes": "fixture",
            "integrity_report": "reports/source-integrity.json",
        },
    ]
    registry = external / "registry/source-registry-v0.1.csv"
    write_csv(registry, registry_fields, registry_rows)
    (external / "reports/source-integrity.json").write_text("{}\n", encoding="utf-8")
    return {
        "external": external,
        "registry": registry,
        "licenses": external / "registry/licenses",
        "citations": external / "registry/citations",
        "manifests": external / "converted/manifests",
        "reports": external / "reports",
    }
