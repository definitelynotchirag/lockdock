"""Sprite packs on disk: ~/.config/lockdock/pets/<name>/ (user) shadows shell/pets/<name>/ (built-in)."""
from __future__ import annotations

import json
import re
from pathlib import Path

BUILTIN_PETS_DIR = Path(__file__).resolve().parents[2] / "shell" / "pets"
_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")


class DirPetPacks:
    """PetPackSource over a list of (source, directory) roots, searched in order."""

    def __init__(self, roots: list[tuple[str, Path]]) -> None:
        self.roots = roots

    def _manifest(self, pack_dir: Path) -> dict | None:
        try:
            raw = json.loads((pack_dir / "pack.json").read_text())
        except (OSError, json.JSONDecodeError):
            return None
        return raw if isinstance(raw, dict) and isinstance(raw.get("moods"), dict) else None

    def resolve(self, name: str) -> tuple[str, dict] | None:
        """(pack_dir, manifest) of the first root holding a valid `name/pack.json`."""
        if not _NAME.fullmatch(name or ""):
            return None
        for _, root in self.roots:
            if (manifest := self._manifest(root / name)) is not None:
                return str(root / name), manifest
        return None

    def available(self) -> list[dict]:
        """Every valid pack, user ones first; a user pack hides a built-in of the same name."""
        seen: set[str] = set()
        out: list[dict] = []
        for source, root in self.roots:
            for d in sorted(root.iterdir()) if root.is_dir() else []:
                if d.name in seen or not _NAME.fullmatch(d.name):
                    continue
                if (m := self._manifest(d)) is not None:
                    seen.add(d.name)
                    out.append({"name": d.name, "title": m.get("name", d.name), "author": m.get("author", ""),
                                "source": source, "dir": str(d)})
        return out
