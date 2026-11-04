"""Exporta los nombres oficiales de especies en español y francés desde PokéAPI.

Descarga el CSV oficial de nombres de especies y genera un JSON compacto en
`src/data/species-names.json` para consumo directo del frontend en build time.
"""

import csv
import json
import ssl
from pathlib import Path
import urllib.request
import certifi

URL = "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/pokemon_species_names.csv"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "src" / "data" / "species-names.json"
SEED_PATH = Path(__file__).resolve().parent.parent / "db" / "seeds" / "species_names.json"


def fetch_species_names() -> dict[str, dict[str, str]]:
    ctx = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(URL, headers={"User-Agent": "HowLongWithoutRaids/1.0"})
    with urllib.request.urlopen(req, context=ctx) as response:
        lines = response.read().decode("utf-8").splitlines()

    reader = csv.DictReader(lines)
    data: dict[str, dict[str, str]] = {"es": {}, "fr": {}}
    for row in reader:
        spec_id = row["pokemon_species_id"]
        lang_id = row["local_language_id"]
        name = row["name"]
        if lang_id == "7":  # Spanish
            data["es"][spec_id] = name
        elif lang_id == "5":  # French
            data["fr"][spec_id] = name
    return data


def main() -> int:
    try:
        data = fetch_species_names()
        # Guardar en seeds para respaldo offline
        SEED_PATH.parent.mkdir(parents=True, exist_ok=True)
        SEED_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"Aviso: no se pudo descargar de la red ({exc}), usando seed local si existe.")
        if SEED_PATH.exists():
            data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        else:
            raise

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Exportadas {len(data.get('es', {}))} especies (ES) y {len(data.get('fr', {}))} especies (FR) en {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
