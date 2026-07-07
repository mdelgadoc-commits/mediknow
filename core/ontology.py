# core/ontology.py
"""
Reglas de validacion formal (especificacion formal) para el registro de
enfermedades.
"""

from . import ontology_catalog


def validate_new_disease(name: str, description: str, category: str):
    errors = {}
    clean_name = name.strip()
    clean_category = category.strip()

    if not clean_name:
        errors["name"] = "El nombre de la enfermedad es obligatorio."
    if not description.strip():
        errors["description"] = "La descripcion es obligatoria."

    catalog_entry = ontology_catalog.lookup(clean_name)

    if catalog_entry:
        if clean_category.lower() != catalog_entry["category"].lower():
            errors["category"] = (
                f"Segun el catalogo formal, '{clean_name}' pertenece a la "
                f"categoria '{catalog_entry['category']}', no a '{clean_category}'."
            )
        entry = {
            "name": clean_name,
            "category": catalog_entry["category"],
            "cie10": catalog_entry["cie10"],
            "cie11": catalog_entry["cie11"],
            "reunis_capitulo": catalog_entry["reunis_capitulo"],
        }
    else:
        if clean_category not in ontology_catalog.VALID_CATEGORIES:
            errors["category"] = (
                "Categoria no reconocida. Elija una categoria valida o use 'Otro'."
            )
        entry = {
            "name": clean_name,
            "category": clean_category,
            "cie10": "",
            "cie11": "",
            "reunis_capitulo": "",
        }

    if errors:
        return False, errors, None

    return True, {}, entry
