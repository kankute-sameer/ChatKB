"""Download only the Docling artifacts used by ChatKB's PDF pipeline."""

from __future__ import annotations

import os
from pathlib import Path

from huggingface_hub import snapshot_download

LAYOUT_REPO = "docling-project/docling-layout-heron"
LAYOUT_REVISION = "main"
TABLE_REPO = "docling-project/docling-models"
TABLE_REVISION = "v2.3.0"


def main() -> None:
    artifacts_path = Path(
        os.environ.get("DOCLING_ARTIFACTS_PATH", "/opt/models/docling")
    )
    artifacts_path.mkdir(parents=True, exist_ok=True)

    snapshot_download(
        repo_id=LAYOUT_REPO,
        revision=LAYOUT_REVISION,
        local_dir=artifacts_path / LAYOUT_REPO.replace("/", "--"),
        allow_patterns=[
            "config.json",
            "model.safetensors",
            "preprocessor_config.json",
        ],
    )
    snapshot_download(
        repo_id=TABLE_REPO,
        revision=TABLE_REVISION,
        local_dir=artifacts_path / TABLE_REPO.replace("/", "--"),
        allow_patterns=["model_artifacts/tableformer/accurate/*"],
    )

    required_files = [
        artifacts_path
        / "docling-project--docling-layout-heron"
        / "model.safetensors",
        artifacts_path
        / "docling-project--docling-models"
        / "model_artifacts"
        / "tableformer"
        / "accurate"
        / "tableformer_accurate.safetensors",
    ]
    missing = [str(path) for path in required_files if not path.is_file()]
    if missing:
        raise RuntimeError(f"Docling model prefetch incomplete: {missing}")

    size_bytes = sum(
        path.stat().st_size for path in artifacts_path.rglob("*") if path.is_file()
    )
    print(
        f"Docling layout + TableFormer artifacts ready at {artifacts_path} "
        f"({size_bytes / 1024 / 1024:.0f} MiB)"
    )


if __name__ == "__main__":
    main()
