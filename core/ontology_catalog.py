# core/ontology_catalog.py
"""
Catalogo formal de enfermedades reconocidas por el sistema, alineado con
CIE-10, CIE-11 y los capitulos REUNIS (Registro Unico Nominal de Salud).
"""

DISEASE_CATALOG = {
    "cistitis": {
        "category": "Urologia", "cie10": "N30", "cie11": "GC08.0",
        "reunis_capitulo": "Enfermedades del sistema genitourinario",
    },
    "litiasis renal": {
        "category": "Urologia", "cie10": "N20", "cie11": "GB70",
        "reunis_capitulo": "Enfermedades del sistema genitourinario",
    },
    "prostatitis": {
        "category": "Urologia", "cie10": "N41", "cie11": "GC81",
        "reunis_capitulo": "Enfermedades del sistema genitourinario",
    },
    "conjuntivitis": {
        "category": "Oftalmologia", "cie10": "H10", "cie11": "9A60",
        "reunis_capitulo": "Enfermedades del ojo y sus anexos",
    },
    "glaucoma": {
        "category": "Oftalmologia", "cie10": "H40", "cie11": "9C61",
        "reunis_capitulo": "Enfermedades del ojo y sus anexos",
    },
    "cataratas": {
        "category": "Oftalmologia", "cie10": "H25-H26", "cie11": "9B10",
        "reunis_capitulo": "Enfermedades del ojo y sus anexos",
    },
    "sinusitis": {
        "category": "Otorrinolaringologia", "cie10": "J01", "cie11": "CA0A",
        "reunis_capitulo": "Enfermedades del sistema respiratorio",
    },
    "otitis media": {
        "category": "Otorrinolaringologia", "cie10": "H66", "cie11": "AB51",
        "reunis_capitulo": "Enfermedades del oido y de la apofisis mastoides",
    },
    "faringitis": {
        "category": "Otorrinolaringologia", "cie10": "J02", "cie11": "CA02",
        "reunis_capitulo": "Enfermedades del sistema respiratorio",
    },
}

VALID_CATEGORIES = {
    "Urologia", "Oftalmologia", "Otorrinolaringologia", "Cardiologia",
    "Neumologia", "Neurologia", "Dermatologia", "Endocrinologia",
    "Gastroenterologia", "Traumatologia", "Pediatria", "Ginecologia",
    "Psiquiatria", "Infectologia", "Otro",
}


def lookup(name: str):
    """Busca una enfermedad en el catalogo por nombre (case-insensitive)."""
    key = name.strip().lower()
    return DISEASE_CATALOG.get(key)
