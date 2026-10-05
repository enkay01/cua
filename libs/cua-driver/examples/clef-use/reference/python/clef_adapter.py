from __future__ import annotations

import base64
import io
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from PIL import Image
import httpx

from grid import ALL_CELLS


DEFAULT_MODEL = os.environ.get("CLEF_MODEL", "@cf/cloudflare/clef")
CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4/accounts"


@dataclass(frozen=True)
class ClefChoiceResult:
    choice: str
    confidence: float
    probabilities: dict[str, float]
    model: str
    raw_response: dict[str, Any]

    @property
    def sorted_candidates(self) -> list[tuple[str, float]]:
        return sorted(self.probabilities.items(), key=lambda kv: kv[1], reverse=True)

    @property
    def top_candidate(self) -> tuple[str, float]:
        candidates = self.sorted_candidates
        return candidates[0] if candidates else (self.choice, self.confidence)

    @property
    def runner_up_candidate(self) -> tuple[str, float] | None:
        candidates = self.sorted_candidates
        return candidates[1] if len(candidates) > 1 else None


def image_to_base64_jpeg(image: Image.Image, quality: int = 85) -> str:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=quality)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def default_cell_criteria() -> dict[str, str]:
    return {cell: f"Cell {cell}" for cell in ALL_CELLS}


def build_clef_request(
    image_base64: str,
    instructions: str,
    criteria: Mapping[str, str] | None = None,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    model_slug = "clef-flash" if "flash" in model.lower() else "clef"
    return {
        "model": model_slug,
        "state": f"Screenshot with 5x5 grid overlay (columns A-E, rows 1-5). Locate target: {instructions}",
        "images": [f"data:image/jpeg;base64,{image_base64}"],
        "questions": {
            "target_cell": {
                "type": "choice",
                "instructions": instructions,
                "criteria": dict(criteria or default_cell_criteria()),
            }
        },
    }


def parse_clef_response(
    data: dict[str, Any],
    model: str = DEFAULT_MODEL,
    expected_criteria: Sequence[str] | None = None,
) -> ClefChoiceResult:
    result = data.get("result", data)
    answers_dict = result.get("answers") or result.get("choices") or {}
    target_choice = answers_dict.get("target_cell", {})

    choice = str(target_choice.get("choice", "")).strip().upper()

    raw_probs = target_choice.get("probabilities", {})
    probabilities: dict[str, float] = {}
    for k, v in raw_probs.items():
        probabilities[str(k).strip().upper()] = float(v)

    if expected_criteria:
        expected_set = {c.strip().upper() for c in expected_criteria}
        if choice and choice not in expected_set:
            raise ValueError(f"Choice {choice!r} not in expected criteria")

    # If choice wasn't directly supplied, pick argmax
    if not choice and probabilities:
        choice = max(probabilities.items(), key=lambda kv: kv[1])[0]

    # Use winning cell probability as confidence for policy thresholding
    if choice in probabilities:
        confidence = probabilities[choice]
    elif probabilities:
        confidence = max(probabilities.values())
    else:
        confidence = float(target_choice.get("confidence", 0.0))

    returned_model = result.get("model") or model
    return ClefChoiceResult(
        choice=choice,
        confidence=confidence,
        probabilities=probabilities,
        model=returned_model,
        raw_response=data,
    )


class ClefClient:
    def __init__(
        self,
        *,
        account_id: str | None = None,
        api_token: str | None = None,
        model: str = DEFAULT_MODEL,
        mock_fixture_paths: Sequence[str | Path] | None = None,
        mock_handler: Callable[[Image.Image, str], ClefChoiceResult] | None = None,
    ) -> None:
        self.account_id = account_id or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        self.api_token = api_token or os.environ.get("CLOUDFLARE_API_TOKEN")
        self.model = model
        self.mock_handler = mock_handler
        self._fixture_queue: list[Path] = [Path(p) for p in (mock_fixture_paths or [])]
        self._fixture_index: int = 0

    @property
    def is_live_configured(self) -> bool:
        return bool(self.account_id and self.api_token)

    def evaluate_grid(
        self,
        image: Image.Image,
        instructions: str,
        *,
        criteria: Mapping[str, str] | None = None,
    ) -> ClefChoiceResult:
        """Evaluate a 5x5 grid crop against a goal description."""
        # 1. Custom mock handler
        if self.mock_handler is not None:
            return self.mock_handler(image, instructions)

        # 2. Mock fixture queue
        if self._fixture_queue:
            fixture_path = self._fixture_queue[self._fixture_index % len(self._fixture_queue)]
            self._fixture_index += 1
            with open(fixture_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return parse_clef_response(data, model=self.model, expected_criteria=ALL_CELLS)

        # 3. Live Cloudflare Workers AI call
        if not self.is_live_configured:
            raise RuntimeError(
                "Cloudflare credentials missing. Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN "
                "or initialize ClefClient with mock fixtures."
            )

        model_path = self.model
        if not model_path.startswith("@cf/"):
            model_path = f"@cf/cloudflare/{model_path}"

        url = f"{CLOUDFLARE_API_BASE}/{self.account_id}/ai/run/{model_path}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        b64_image = image_to_base64_jpeg(image)
        payload = build_clef_request(b64_image, instructions, criteria=criteria, model=self.model)

        timeout = float(os.environ.get("CLEF_TIMEOUT", 120.0))
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        return parse_clef_response(data, model=self.model, expected_criteria=ALL_CELLS)
