"""Sprites desde PokeAPI.

El pipeline resuelve la imagen y guarda una ruta local en
``pokemon.sprite_url``. La UI solo pinta lo que le llega en el snapshot.

PokeAPI no tiene sprites de Shadow, asi que un jefe sombra cae al sprite de su
forma base, que es lo mejor disponible sin inventar nada.

Las formas de PokeAPI se nombran con SUFIJO: ``sandslash-alola``, ``wooper-paldea``,
``giratina-origin``, ``charizard-mega-x``. Nunca con prefijo. El sufijo a interpretar
es el ultimo segmento tras el ultimo guion, asi que un nombre compuesto como
``raticate-totem-alola`` sigue siendo una forma regional de ``raticate``.

La descarga es educada: peticiones secuenciales, una pausa entre cada una, `User-Agent`
descriptivo, salto de lo ya descargado y parada en seco al primer fallo del origen.
"""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from raids.forms import explicit_pokeapi_form_name, match_pokeapi_form
from raids.pokedex import read_species_categories

logger = logging.getLogger(__name__)

SPRITE_BASE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"
SPECIES_URL = "https://pokeapi.co/api/v2/pokemon-species?limit=2000"
# RF-40: detalle de especie, donde viven is_legendary/is_mythical/is_baby.
SPECIES_DETAIL_URL = "https://pokeapi.co/api/v2/pokemon-species/{id}"
FORM_URL = "https://pokeapi.co/api/v2/pokemon-form?limit=2000"
USER_AGENT = "howlongwithoutraids/0.1 (local ETL; +https://github.com/alguimo/howlongwithoutraids)"

# Sufijos de PokeAPI -> nuestro slug de `form`. El sufijo se busca al final del
# nombre, nunca al principio.
FORM_SUFFIXES = {
    "alola": "alola",
    "galar": "galar",
    "hisui": "hisui",
    "paldea": "paldea",
    "origin": "origin",
    "altered": "altered",
    "incarnate": "incarnate",
    "therian": "therian",
    "disguised": "disguised",
    "hero-of-many-battles": "hero-of-many-battles",
    "eternamax": "eternamax",
}

# `shadow` no entra a proposito: no es una forma de nuestra identidad, asi que
# `calyrex-shadow` cae a la especie base por el fallback de resolve_sprite_id.

# Los sufijos mas largos primero: `hero-of-many-battles` gana a cualquier coincidencia
# parcial de sus segmentos intermedios.
FORM_SUFFIXES_BY_LENGTH = sorted(FORM_SUFFIXES, key=len, reverse=True)


class SpriteError(RuntimeError):
    """No se pudo resolver ni descargar un sprite."""


# Un 404 (o un 410) solo dice que ese fichero no esta: no es un fallo del origen, asi
# que se pasa a la siguiente candidata. Cualquier otro status, y cualquier error de
# transporte, significa que el origen esta fallando y la descarga se para.
MISSING_STATUSES = frozenset({404, 410})

# Firmas de imagen que aceptamos (RF-06). Un 200 no basta: un portal de captcha,
# una pagina de error o un HTML vacio tambien responden 200, y escribir eso con
# nombre `.png` deja un sprite roto que la UI no detecta. Se mira la firma del
# CUERPO, no la extension de la URL ni el `content-type`: la URL la pone el
# origen y el `content-type` de los mirrors no es de fiar.
#
# Solo las firmas que el pipeline puede recibir hoy de PokeAPI y de la rotacion
# publicada por LeekDuck, que es donde acaban los ficheros.
IMAGE_SIGNATURES: tuple[bytes, ...] = (
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"\xff\xd8\xff",  # JPEG
    b"GIF87a",
    b"GIF89a",
)


def looks_like_image(body: bytes) -> bool:
    """Si el cuerpo descargado es una imagen segun su firma.

    False cubre tambien el cuerpo vacio: cero bytes no es una imagen (RF-06).
    """
    return any(body.startswith(signature) for signature in IMAGE_SIGNATURES)


def default_client() -> httpx.Client:
    """Cliente HTTP con `User-Agent` descriptivo (constitucion 10)."""
    return httpx.Client(
        headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True
    )


@dataclass(frozen=True)
class Identity:
    dex_number: int
    form: str
    variant: str


@dataclass(frozen=True)
class SpriteResolution:
    """The table's expected PokeAPI resource and its recorded sprite URL."""

    form_name: str
    url: str | None
    form_id: int | None = None


@dataclass(frozen=True)
class SpriteAssignment:
    """The deterministic inputs and result of the sprite audit."""

    identity: Identity
    expected_form_name: str | None
    expected_url: str | None
    exported_path: str | None
    fallback_allowed: bool = False


def make_sprite_assignment(
    identity: Identity,
    expected_form_name: str | None,
    expected_url: str | None,
    exported_path: str | None,
    *,
    fallback_allowed: bool = False,
) -> SpriteAssignment:
    """Create an audit record without touching the network or filesystem."""
    return SpriteAssignment(
        identity=identity,
        expected_form_name=expected_form_name,
        expected_url=expected_url,
        exported_path=exported_path,
        fallback_allowed=fallback_allowed,
    )


def _identity_json(identity: Identity) -> dict[str, object]:
    return {
        "dex_number": identity.dex_number,
        "form": identity.form,
        "variant": identity.variant,
    }


def _assignment_sort_key(assignment: SpriteAssignment) -> tuple:
    identity = assignment.identity
    return identity.dex_number, identity.form, identity.variant


def _exported_resource_name(path: str | None) -> str | None:
    if not path:
        return None
    return Path(urlparse(path).path).name


def _audit_assignment(assignment: SpriteAssignment) -> tuple[str, str | None]:
    """Classify one assignment; exact URL identity wins over file existence."""
    exported_name = _exported_resource_name(assignment.exported_path)
    expected_name = _exported_resource_name(assignment.expected_url)
    fallback_reason = (
        "shadow_base_fallback"
        if assignment.identity.variant == "SHADOW"
        else "authorized_base_fallback"
    )

    if assignment.expected_url is not None:
        if assignment.fallback_allowed and assignment.identity.variant == "SHADOW":
            return "permitted_fallback", fallback_reason
        if exported_name == expected_name:
            return "ok", None
        if assignment.fallback_allowed and exported_name is not None:
            return "permitted_fallback", fallback_reason
        return "error", "exported_path_does_not_match_expected_resource"

    if assignment.fallback_allowed and exported_name is not None:
        return "permitted_fallback", fallback_reason
    if exported_name is None:
        return "error", "exact_resource_unavailable"
    return "error", "exact_resource_unavailable_without_authorized_fallback"


def audit_sprite_assignments(assignments) -> dict[str, list[dict]]:
    """Return a stable, JSON-ready audit of sprite identity assignments.

    Each input is a :class:`SpriteAssignment` (plain mappings with the same keys
    are accepted for callers loading a fixture).  A duplicate is reported only
    when a route is used by more than one identity.  A shared route is permitted
    only when every identity using it is an explicitly authorized fallback;
    notably, a supported form using the base route remains suspicious even if it
    is the only user of that route.
    """
    normalized: list[SpriteAssignment] = []
    for raw in assignments:
        if isinstance(raw, SpriteAssignment):
            normalized.append(raw)
        else:
            normalized.append(SpriteAssignment(**raw))
    normalized.sort(key=_assignment_sort_key)

    results = []
    by_path: dict[str, list[tuple[SpriteAssignment, str, str | None]]] = {}
    for assignment in normalized:
        classification, reason = _audit_assignment(assignment)
        results.append({
            "identity": _identity_json(assignment.identity),
            "expected_form_name": assignment.expected_form_name,
            "expected_url": assignment.expected_url,
            "exported_path": assignment.exported_path,
            "classification": classification,
            "reason": reason,
        })
        if assignment.exported_path:
            by_path.setdefault(assignment.exported_path, []).append(
                (assignment, classification, reason)
            )

    duplicates = []
    for path in sorted(by_path):
        users = by_path[path]
        if len(users) < 2:
            continue
        identities = [_identity_json(item[0].identity) for item in users]
        permitted = all(item[1] == "permitted_fallback" for item in users)
        duplicates.append({
            "path": path,
            "identities": identities,
            "classification": "permitted" if permitted else "suspicious",
            "reason": "all_users_are_authorized_fallbacks" if permitted else "shared_route_for_distinct_identities",
        })

    return {"assignments": results, "duplicates": duplicates}


# Spec 005 RF-09: Zacian and Zamazenta's base identity is ``hero-of-many-battles``
# while PokeAPI stores their base resource under plain ``zacian``/``zamazenta``
# (``888.png``/``889.png``).
DEFAULT_BASE_SPRITE_FORMS = frozenset({
    (888, "hero-of-many-battles"),
    (889, "hero-of-many-battles"),
})


def sprite_key(identity: Identity) -> str:
    """Nombre estable y derivado de la identidad. Cambia la cache del navegador."""
    key = str(identity.dex_number)
    if (
        identity.form
        and identity.form != "normal"
        and (identity.dex_number, identity.form) not in DEFAULT_BASE_SPRITE_FORMS
    ):
        key += f"-{identity.form}"
    if identity.variant and identity.variant != "NORMAL":
        key += f"-{identity.variant.lower()}"
    return key


def base_sprite_key(identity: Identity) -> str:
    """Nombre del fichero del sprite del dex base de esta identidad (RF-03).

    El repliegue de RF-03 no crea un fichero nuevo con el nombre de la forma:
    reutiliza (o descarga) el del dex base, y es esa ruta la que queda en
    ``sprite_url``. Asi el mismo dex no se descarga ni se duplica nunca.
    """
    return sprite_key(Identity(identity.dex_number, "normal", "NORMAL"))


def _index_from_listing(payload: dict) -> dict[str, int]:
    """Convierte un listado de PokeAPI en {nombre: id}."""
    index: dict[str, int] = {}
    for result in payload.get("results", []):
        index[result["name"]] = int(result["url"].rstrip("/").split("/")[-1])
    return index


def load_catalog(cache_path: Path, *, client: httpx.Client | None = None) -> dict:
    """Download and cache species plus the real sprite URL of every form.

    The numeric form id is an API resource id, not a sprite id.  Form details are
    therefore fetched explicitly and their ``sprites.front_default`` is retained.

    Since version 3 the cache also stores ``species_categories`` (RF-40), read
    from ``/pokemon-species/{id}`` for the dex used by the downloaded forms only,
    so the 1000+ species listing is not requested in full.  A cache with any
    other version is an obsolete, regenerable artifact and is rebuilt.
    """
    cache_path = Path(cache_path)
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        forms = cached.get("forms") if isinstance(cached, dict) else None
        categories = cached.get("species_categories") if isinstance(cached, dict) else None
        if cached.get("version") == 3 and isinstance(forms, dict) and all(
            isinstance(value, dict) for value in forms.values()
        ) and isinstance(categories, dict):
            return cached

    owns_client = client is None
    client = client or default_client()
    try:
        species = _index_from_listing(client.get(SPECIES_URL).json())
        form_listing = client.get(FORM_URL).json()
        forms = {}
        used_dex: set[int] = set()
        for result in form_listing.get("results", []):
            form_name = result["name"]
            form_id = int(result["url"].rstrip("/").split("/")[-1])
            detail = client.get(result["url"]).json()
            sprite_url = (detail.get("sprites") or {}).get("front_default")
            # pokemon-form often has no sprite fields. Its linked pokemon resource
            # has the actual form sprite (e.g. form 10136 -> pokemon 10036).
            if not sprite_url and detail.get("pokemon", {}).get("url"):
                pokemon_detail = client.get(detail["pokemon"]["url"]).json()
                sprite_url = (pokemon_detail.get("sprites") or {}).get("front_default")
            forms[form_name] = {"id": form_id, "sprite_url": sprite_url}
            dex_number, _, _ = _match_form(form_name, species)
            if dex_number is not None:
                used_dex.add(dex_number)

        species_categories = {}
        for dex_number in sorted(used_dex):
            detail = client.get(SPECIES_DETAIL_URL.format(id=dex_number)).json()
            species_categories[dex_number] = read_species_categories(detail)
    finally:
        if owns_client:
            client.close()

    catalog = {
        "version": 3,
        "species": species,
        "species_categories": species_categories,
        "forms": forms,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    return catalog


def build_index(catalog: dict) -> dict[tuple[int, str, str], int]:
    """Build ``(dex, form, variant) -> form record`` from a catalog.

    Legacy integer records remain accepted so old fixtures and local caches can be
    migrated without changing identity resolution.
    """
    species_by_name: dict[str, int] = catalog["species"]

    index: dict[tuple[int, str, str], int] = {}
    for form_name, form_id in catalog["forms"].items():
        dex, form, variant = _match_form(form_name, species_by_name)
        if dex is None:
            continue
        # Un mismo nombre puede repetirse; el primero gana.
        index.setdefault((dex, form, variant), form_id)
        if dex in {888, 889} and form == "normal" and variant == "NORMAL":
            index.setdefault((dex, "hero-of-many-battles", "NORMAL"), form_id)
    return index


def _lookup_species(name: str, species_by_name: dict[str, int]) -> int | None:
    """Busca una especie por nombre, probando tambien nombres mas cortos.

    Asi ``raticate-totem-alola`` (ya sin el sufijo) y ``deoxys-attack`` caen a
    ``raticate`` y ``deoxys`` cuando el nombre completo no es una especie.
    """
    parts = name.split("-")
    while parts:
        dex = species_by_name.get("-".join(parts))
        if dex is not None:
            return dex
        parts.pop()
    return None


def _match_form(form_name: str, species_by_name: dict[str, int]) -> tuple:
    """Traduce un nombre de forma de PokeAPI a (dex, form, variant)."""
    # Mega es una variante, no una forma: el sprite va en `variant`.
    # PokeAPI escribe `charizard-mega`, `charizard-mega-x`, `beedrill-mega`.
    parts = form_name.split("-")
    if "mega" in parts:
        before = parts[: parts.index("mega")]
        dex = _lookup_species("-".join(before), species_by_name) if before else None
        if dex is not None:
            # PokeAPI distingue mega X e Y con un sufijo que nuestro modelo no
            # guarda; colapsamos ambos en la misma identidad.
            return dex, "normal", "MEGA"

    # RF-46: taxonomia ampliada, anclada a la especie. `dusk-mane` no es
    # `necrozma-dusk-mane` y `crowned` vale para Zacian y Zamazenta.
    expanded = match_pokeapi_form(form_name, species_by_name)
    if expanded is not None:
        dex, form = expanded
        return dex, form, "NORMAL"

    for suffix in FORM_SUFFIXES_BY_LENGTH:
        marker = f"-{suffix}"
        if form_name.endswith(marker):
            dex = _lookup_species(form_name[: -len(marker)], species_by_name)
            if dex is not None:
                return dex, FORM_SUFFIXES[suffix], "NORMAL"

    # Forma base: el nombre de la especie a secas, o una variante que no modelamos
    # (cosplay, gmax, attack/defense...) y que cae a la especie base.
    dex = _lookup_species(form_name, species_by_name)
    if dex is not None:
        return dex, "normal", "NORMAL"
    return None, "normal", "NORMAL"


def exact_sprite_id(index: dict, identity: Identity) -> int | None:
    """Id de sprite de la identidad exacta, o None si el catalogo no la tiene."""
    value = index.get((identity.dex_number, identity.form, identity.variant))
    if isinstance(value, dict):
        return value.get("id")
    return value


def resolve_sprite_identity(
    identity: Identity, catalog: dict
) -> SpriteResolution | None:
    """Resolve an identity through the explicit PokeAPI form-name table.

    The catalog is the local, already downloaded source of truth.  The finite
    candidates come from ``forms.py``; no suffix inference is performed here.
    Missing exact resources intentionally return ``None`` (T7 decides the
    fallback/null download policy).
    """
    species_by_name = catalog.get("species", {})
    species = next(
        (name for name, dex in species_by_name.items() if int(dex) == identity.dex_number),
        None,
    )
    if species is None:
        return None

    forms = catalog.get("forms", {})
    for form_name in explicit_pokeapi_form_name(
        species, identity.form, identity.variant
    ):
        record = forms.get(form_name)
        if record is None:
            continue
        if isinstance(record, dict):
            return SpriteResolution(
                form_name=form_name,
                url=record.get("sprite_url"),
                form_id=record.get("id"),
            )
        return SpriteResolution(
            form_name=form_name,
            url=f"{SPRITE_BASE}/{record}.png",
            form_id=int(record),
        )
    return None


def exact_sprite_url(index: dict, identity: Identity) -> str | None:
    """Return the source URL recorded by PokeAPI for the exact form."""
    value = index.get((identity.dex_number, identity.form, identity.variant))
    if isinstance(value, dict):
        return value.get("sprite_url")
    if value is None:
        return None
    return f"{SPRITE_BASE}/{value}.png"


def base_sprite_id(index: dict, identity: Identity) -> int:
    """Id de sprite del dex base. Es la ultima opcion y nunca falla."""
    value = index.get((identity.dex_number, "normal", "NORMAL"), identity.dex_number)
    if isinstance(value, dict):
        return int(value["id"])
    return value


def resolve_sprite_id(index: dict, identity: Identity) -> int:
    """Devuelve el id de sprite para la identidad, con caida al dex base."""
    exact = exact_sprite_id(index, identity)
    if exact is not None:
        return exact
    return base_sprite_id(index, identity)


def candidate_targets(
    identity: Identity,
    index: dict,
    *,
    rotation_url: str | None = None,
    catalog: dict | None = None,
) -> list[tuple[str, str]]:
    """Candidatas como pares ``(url, nombre del fichero local)``, sin repeticiones.

    Se deduplica por URL, nunca por nombre: la rotacion y el sprite del dex base
    pueden acabar en el mismo fichero local (p. ej. un jefe sin forma propia), y
    esa segunda URL hace falta como red de seguridad si la primera da 404.

    1. La imagen que publica la fuente de la rotacion vigente (RF-02): es la que
       refleja el sprite real del jefe. Se guarda con el nombre de la identidad.
    2. El sprite de la forma o variante concreta (RF-01), tambien con el nombre de
       la identidad.
    3. El sprite del dex base (RF-03): mejor un sprite base que un hueco. Se
       guarda con el nombre del dex base, que es justo la ruta que quedara en
       ``sprite_url``.
    """
    targets: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    def add(url: str | None, name: str) -> None:
        if url is None or url in seen_urls:
            return
        seen_urls.add(url)
        targets.append((url, name))

    if rotation_url:
        add(rotation_url, sprite_key(identity))

    exact_url = exact_sprite_url(index, identity)
    if exact_url is not None:
        add(exact_url, sprite_key(identity))

    # El fallback base está cerrado: solo Shadow y formas que no pertenecen a la
    # taxonomía soportada pueden reutilizarlo. Una forma conocida sin recurso
    # exacto debe quedarse sin sprite (RF-46/RF-51).
    allow_base_fallback = catalog is None or _base_fallback_allowed(identity, catalog)
    if allow_base_fallback:
        add(f"{SPRITE_BASE}/{base_sprite_id(index, identity)}.png", base_sprite_key(identity))
    return targets


def _base_fallback_allowed(identity: Identity, catalog: dict) -> bool:
    """Whether the spec permits using the base resource for this identity."""
    if identity.variant == "SHADOW":
        return True
    species_by_name = catalog.get("species", {})
    species = next(
        (name for name, dex in species_by_name.items() if int(dex) == identity.dex_number),
        None,
    )
    if species is None:
        # An unknown species has no supported exact mapping; retain the old,
        # explicitly permitted outside-taxonomy fallback.
        return True
    return not explicit_pokeapi_form_name(species, identity.form, identity.variant)


def candidate_urls(
    identity: Identity,
    index: dict,
    *,
    rotation_url: str | None = None,
    catalog: dict | None = None,
) -> list[str]:
    """URLs candidatas en orden de prioridad, sin repeticiones."""
    return [
        url
        for url, _ in candidate_targets(
            identity, index, rotation_url=rotation_url, catalog=catalog
        )
    ]


def local_sprite_url(name: str) -> str:
    """Ruta que el navegador pide por un fichero de ``public/sprites/``."""
    return f"/sprites/{name}.png"


def resolve_local_sprite_name(
    identity: Identity, sprite_dir: Path, *, catalog: dict | None = None
) -> str | None:
    """Nombre del fichero local que representa esta identidad, o ``None``.

    Es la misma resolucion que hace la descarga pero solo mirando el disco: el
    nombre de la identidad si su fichero esta, y si no el del dex base (RF-03).
    Sirve para rellenar ``sprite_url`` sin volver a preguntar al origen.
    """
    sprite_dir = Path(sprite_dir)
    names = [sprite_key(identity)]
    if catalog is None or _base_fallback_allowed(identity, catalog):
        names.append(base_sprite_key(identity))
    for name in names:
        if (sprite_dir / f"{name}.png").exists():
            return name
    return None


def sprite_url(identity: Identity, index: dict) -> str:
    exact_url = exact_sprite_url(index, identity)
    if exact_url:
        return exact_url
    return f"{SPRITE_BASE}/{base_sprite_id(index, identity)}.png"


def download_sprites(
    identities: list[Identity],
    index: dict,
    out_dir: Path,
    *,
    client: httpx.Client | None = None,
    delay: float = 0.2,
    rotation_images: dict[Identity, str] | None = None,
    on_download=None,
    force: bool = False,
    catalog: dict | None = None,
) -> dict[str, int]:
    """Descarga en orden y de una en una. Salta lo ya descargado y para si falla.

    Recorre las candidatas de cada jefe en orden (RF-02, RF-01, RF-03) y solo
    escribe el fichero cuando el origen responde de verdad (RF-06). Cada
    candidata trae el nombre del fichero local que resolveria: el de la identidad
    para la rotacion y la forma, y el del dex base para el repliegue (RF-03). Si
    el fichero que resolveria esa candidata ya esta en disco no se vuelve a pedir
    (RF-07), ni siquiera dos veces en la misma pasada; `force` lo ignora. Si el
    origen falla, la descarga se aborta sin reintentar (RF-08).

    `on_download(identity, name)` se llama por cada identidad que acaba con
    fichero, tanto recien descargado como ya presente en disco.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rotation_images = rotation_images or {}
    stats = {"downloaded": 0, "skipped": 0, "failed": 0}
    # Rastrea por URL que nombre local la pidio por primera vez en esta pasada y
    # el cuerpo aceptado, para no volver a pedir la misma URL ni dejar sin
    # fichero a una identidad que comparte URL con otra (el sprite del default
    # form de una especie es la misma URL que el del dex base).
    attempted: dict[str, str] = {}
    downloaded: dict[str, bytes] = {}

    owns_client = client is None
    client = client or default_client()
    try:
        for identity in identities:
            resolved: str | None = None
            requested = False

            candidates = candidate_targets(
                identity,
                index,
                rotation_url=rotation_images.get(identity),
                catalog=catalog,
            )
            # No candidate is itself an audited, unavailable exact resource
            # when the strict catalog policy is active.
            if not candidates and catalog is not None:
                requested = True
            for url, name in candidates:
                target = out_dir / f"{name}.png"
                if target.exists() and not force:
                    # RF-07: este fichero ya esta resuelto para esta identidad.
                    resolved = name
                    break
                if url in attempted:
                    if attempted[url] == name:
                        # El mismo par (url, nombre) ya se resolvio en esta
                        # pasada para esta identidad; no se repite.
                        resolved = name
                        break
                    body = downloaded.get(url)
                    if body is not None:
                        # Otra identidad ya trajo esta URL bajo OTRO nombre de
                        # fichero. Se reutilizan los bytes para no dejar a esta
                        # identidad sin su fichero (bug de las dos pasadas).
                        if not target.exists():
                            target.write_bytes(body)
                            stats["downloaded"] += 1
                        requested = True
                        resolved = name
                        break
                    # La URL ya se pregunto y no existe (404/410): este nombre
                    # tampoco la va a encontrar.
                    requested = True
                    continue
                attempted[url] = name

                requested = True
                try:
                    response = client.get(url)
                except Exception as exc:
                    raise SpriteError(f"descarga abortada en {url}: {exc}") from exc
                finally:
                    # Pausa entre peticiones, tambien entre candidatas del mismo jefe.
                    time.sleep(delay)

                if response.status_code == 200:
                    # RF-06: el 200 se comprueba contra la firma del cuerpo ANTES
                    # de escribir nada en disco. Un cuerpo que no sea imagen aborta
                    # (RF-08) y no se pasa a la siguiente candidata: eso solo lo
                    # hacen los 404/410, que son una ausencia y no un fallo.
                    if not looks_like_image(response.content):
                        raise SpriteError(
                            f"descarga abortada en {url}: la respuesta 200 no es una imagen"
                        )
                    target.write_bytes(response.content)
                    downloaded[url] = response.content
                    stats["downloaded"] += 1
                    resolved = name
                    break
                if response.status_code in MISSING_STATUSES:
                    continue
                raise SpriteError(
                    f"descarga abortada en {url}: HTTP {response.status_code}"
                )

            if resolved is not None:
                if requested:
                    if on_download:
                        on_download(identity, resolved)
                else:
                    stats["skipped"] += 1
                    if on_download:
                        on_download(identity, resolved)
            elif requested:
                stats["failed"] += 1
                reason = "exact sprite resource unavailable; no authorized base fallback"
                stats.setdefault("failure_reasons", []).append(
                    {"identity": identity, "reason": reason}
                )
                logger.warning("sprite omitted: %s (%s)", identity, reason)
    finally:
        if owns_client:
            client.close()

    return stats
