from __future__ import annotations

import base64
import io
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from PIL import Image
import httpx

from grid import ALL_CELLS, are_adjacent


def load_env_files() -> None:
    """Find and load .env.local or .env from current directory up to repository root."""
    current = Path.cwd().resolve()
    for parent in [current, *current.parents]:
        for candidate_name in [".env.local", ".env"]:
            env_path = parent / candidate_name
            if env_path.is_file():
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#") or "=" not in line:
                                continue
                            key, _, val = line.partition("=")
                            key = key.strip()
                            val = val.strip().strip("'\"")
                            if key and key not in os.environ:
                                os.environ[key] = val
                except Exception:
                    pass
        if (parent / ".git").exists():
            break


load_env_files()

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

    def top_non_adjacent_candidate(self, reference_cell: str | None = None) -> tuple[str, float] | None:
        """Find the highest-scoring cell that is not adjacent to reference_cell (defaults to top cell)."""
        ref = reference_cell or self.choice
        for cell, prob in self.sorted_candidates:
            if cell != ref and not are_adjacent(ref, cell):
                return (cell, prob)
        return None


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
    if not isinstance(data, dict):
        raise ValueError(f"Invalid response payload: expected dict, got {type(data).__name__}")

    result = data.get("result", data)
    if not isinstance(result, dict):
        raise ValueError(f"Invalid 'result' field in payload: expected dict, got {type(result).__name__}")

    answers_dict = result.get("answers") or result.get("choices") or {}
    if not isinstance(answers_dict, dict):
        raise ValueError(f"Invalid answers container: expected dict, got {type(answers_dict).__name__}")

    target_choice = answers_dict.get("target_cell", {})
    if not isinstance(target_choice, dict):
        raise ValueError(f"Invalid target_cell entry: expected dict, got {type(target_choice).__name__}")

    raw_choice = target_choice.get("choice")
    choice = str(raw_choice).strip().upper() if raw_choice is not None else ""

    raw_probs = target_choice.get("probabilities", {})
    if not isinstance(raw_probs, dict):
        raise ValueError(f"Invalid probabilities field: expected dict, got {type(raw_probs).__name__}")

    expected_set = {c.strip().upper() for c in (expected_criteria or ALL_CELLS)}
    probabilities: dict[str, float] = {}

    for k, v in raw_probs.items():
        cell_key = str(k).strip().upper()
        if expected_criteria and cell_key not in expected_set:
            raise ValueError(f"Unknown cell score returned: {cell_key!r} is not in expected criteria")

        try:
            val = float(v)
        except (TypeError, ValueError) as err:
            raise ValueError(f"Non-numeric probability for cell {cell_key}: {v!r}") from err

        if not math.isfinite(val):
            raise ValueError(f"Non-finite probability for cell {cell_key}: {val}")

        if val < 0.0 or val > 1.0 + 1e-4:
            raise ValueError(f"Probability out of range [0, 1] for cell {cell_key}: {val}")

        probabilities[cell_key] = val

    if not choice and probabilities:
        choice = max(probabilities.items(), key=lambda kv: kv[1])[0]

    if not choice:
        raise ValueError("Malformed response: neither choice nor probabilities provided in target_cell")

    if expected_criteria and choice not in expected_set:
        raise ValueError(f"Choice {choice!r} not in expected criteria")

    if choice in probabilities:
        confidence = probabilities[choice]
    elif probabilities:
        confidence = max(probabilities.values())
    else:
        raw_conf = target_choice.get("confidence", 0.0)
        try:
            confidence = float(raw_conf)
        except (TypeError, ValueError):
            confidence = 0.0

    returned_model = result.get("model") or model
    return ClefChoiceResult(
        choice=choice,
        confidence=confidence,
        probabilities=probabilities,
        model=str(returned_model),
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
        timeout: float | None = None,
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

        effective_timeout = timeout if timeout is not None else float(os.environ.get("CLEF_TIMEOUT", 120.0))
        if effective_timeout <= 0:
            raise TimeoutError("Inference timed out before request dispatch")

        with httpx.Client(timeout=effective_timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        return parse_clef_response(data, model=self.model, expected_criteria=ALL_CELLS)
