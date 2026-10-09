"""Nombre de evento desde la prosa de Fandom (RF-42).

La lista de patrones es **cerrada**: añadir uno es un cambio de spec. Solo se
registra ``X`` cuando casa **exactamente uno** de los patrones; con cero o más
de uno el valor es ``None``, porque un nombre inventado o ambiguo es peor que
un hueco.
"""

from __future__ import annotations

import re

# Orden cerrado de patrones de prosa. ``[[X]]`` es un enlace wiki; el resto del
# texto debe casar literalmente.
EVENT_PATTERNS = (
    re.compile(r"Raid Bosses changed after \[\[([^\]]+)\]\]", re.IGNORECASE),
    re.compile(r"the \[\[([^\]]+)\]\] featured", re.IGNORECASE),
    re.compile(r"following the \[\[([^\]]+)\]\]", re.IGNORECASE),
    re.compile(r"after the \[\[([^\]]+)\]\] event", re.IGNORECASE),
)


def extract_event_name(prose: str | None) -> str | None:
    """Return ``X`` only when exactly one closed pattern matches (RF-42)."""
    if not prose:
        return None
    matches = [
        match.group(1).strip()
        for pattern in EVENT_PATTERNS
        for match in pattern.finditer(prose)
        if match.group(1).strip()
    ]
    if len(matches) == 1:
        return matches[0]
    return None
