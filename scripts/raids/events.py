"""Nombre de evento desde la prosa de Fandom (RF-42).

La lista de patrones es **cerrada**: añadir uno es un cambio de spec. Solo se
registra ``X`` cuando casa **exactamente uno** de los patrones; con cero o más
de uno el valor es ``None``, porque un nombre inventado o ambiguo es peor que
un hueco.
"""

from __future__ import annotations

import re

# Orden cerrado de patrones de prosa (RF-42). ``[[X]]`` es un enlace wiki; el
# resto del texto debe casar literalmente. Cada frase de cambio tiene su patrón
# con enlace y su patrón en texto plano: la fuente escribe el nombre enlazado
# unas veces y desnudo otras. En los patrones de texto plano ``X`` termina en el
# punto de la frase y el lookahead ``(?!\[\[)`` evita que se traguen el enlace
# (que ya captura su patrón con enlace), de modo que una mención casa solo una
# vez. Los patrones con enlace no exigen el artículo ``the`` delante.
EVENT_PATTERNS = (
    re.compile(r"Raid Bosses changed after \[\[([^\]]+)\]\]", re.IGNORECASE),
    re.compile(r"\[\[([^\]]+)\]\] featured", re.IGNORECASE),
    re.compile(r"following the \[\[([^\]]+)\]\]", re.IGNORECASE),
    re.compile(r"after the \[\[([^\]]+)\]\] event", re.IGNORECASE),
    re.compile(r"Raid Bosses changed after (?!\[\[)([^.\n]+)\.", re.IGNORECASE),
    re.compile(r"Raid Bosses returned to previous layout after \[\[([^\]]+)\]\]", re.IGNORECASE),
    re.compile(r"Raid Bosses returned to previous layout after (?!\[\[)([^.\n]+)\.", re.IGNORECASE),
)


def _clean_match(raw: str, *, is_link: bool) -> str:
    if not is_link:
        return raw.strip()
    parts = [segment.strip() for segment in raw.split("|") if segment.strip()]
    return parts[-1] if parts else ""


def extract_event_name(prose: str | None) -> str | None:
    """Return ``X`` only when exactly one closed pattern matches (RF-42)."""
    if not prose:
        return None
    matches = []
    for pattern in EVENT_PATTERNS:
        is_link = r"\]\]" in pattern.pattern
        for match in pattern.finditer(prose):
            cleaned = _clean_match(match.group(1), is_link=is_link)
            if cleaned:
                matches.append(cleaned)
    if len(matches) == 1:
        return matches[0]
    return None
