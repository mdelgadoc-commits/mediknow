from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class MatchedSymptom:
    """Síntoma que coincidió entre el input del médico y la BD."""
    symptom_name: str
    association_weight: int   # Peso formal de la relación (1 ó 3)
    intensity: int            # Intensidad marcada por el médico (1–10)
    contribution: float       # association_weight × intensity

    def __str__(self) -> str:
        return (
            f"  • {self.symptom_name}: "
            f"peso({self.association_weight}) × intensidad({self.intensity}) "
            f"= {self.contribution:.1f}"
        )


@dataclass
class DiseaseScore:
    """Puntaje calculado para una enfermedad en una consulta."""
    disease_name: str
    raw_score: float             # Suma bruta de contributions
    normalized_score: float      # raw_score / max_possible × 100  (0–100)
    matched_symptoms: list[MatchedSymptom] = field(default_factory=list)
    treatments: list[str] = field(default_factory=list)
    clinical_criteria: str = ""
    rank: int = 0

    @property
    def coverage(self) -> float:
        """Porcentaje de síntomas conocidos de la enfermedad que fueron ingresados."""
        total_known = sum(ms.association_weight * 10 for ms in self.matched_symptoms)
        return (self.raw_score / total_known * 100) if total_known > 0 else 0.0

    def __str__(self) -> str:
        lines = [
            f"#{self.rank} {self.disease_name}",
            f"    Score normalizado : {self.normalized_score:.1f} / 100",
            f"    Score bruto       : {self.raw_score:.1f}",
            "    Síntomas coincidentes:",
        ]
        for ms in self.matched_symptoms:
            lines.append(str(ms))
        return "\n".join(lines)

class InferenceEngine:

    MINIMUM_SCORE_THRESHOLD = 5.0  # Ignorar enfermedades con score < 5 (ruido)

    def run(self, symptoms_input: dict[str, int]) -> list[DiseaseScore]:
        """
        Ejecuta la inferencia.

        Args:
            symptoms_input: Diccionario {"nombre_síntoma": intensidad (1–10)}

        Returns:
            Lista de DiseaseScore ordenada por score descendente.
        """
        # Importación aquí para evitar problemas si el módulo se importa fuera de Django
        from core.models import Disease, DiseaseSymptomRelation, DiseaseTreatmentRelation

        # Normalizar el input del médico (lowercase para comparación robusta)
        input_normalized = {k.strip().lower(): v for k, v in symptoms_input.items()}

        results: list[DiseaseScore] = []

        diseases = Disease.objects.prefetch_related(
            "symptom_relations__symptom",
            "treatment_relations__treatment",
        ).all()

        for disease in diseases:
            all_relations = list(disease.symptom_relations.select_related("symptom"))

            # Puntaje máximo posible (si el médico marcara TODOS los síntomas con intensidad 10)
            max_possible = sum(r.association_weight * 10 for r in all_relations)
            if max_possible == 0:
                continue

            matched: list[MatchedSymptom] = []
            raw_score = 0.0

            for relation in all_relations:
                symptom_key = relation.symptom.name.strip().lower()
                if symptom_key in input_normalized:
                    intensity = max(1, min(10, input_normalized[symptom_key]))
                    contribution = relation.association_weight * intensity
                    raw_score += contribution
                    matched.append(
                        MatchedSymptom(
                            symptom_name=relation.symptom.name,
                            association_weight=relation.association_weight,
                            intensity=intensity,
                            contribution=contribution,
                        )
                    )

            if raw_score < self.MINIMUM_SCORE_THRESHOLD:
                continue

            normalized = (raw_score / max_possible) * 100

            # Obtener tratamientos ordenados por prioridad
            treatments = [
                f"[{r.priority}ª línea] {r.treatment.name}"
                for r in disease.treatment_relations.select_related("treatment").order_by("priority")
            ]

            results.append(
                DiseaseScore(
                    disease_name=disease.name,
                    raw_score=raw_score,
                    normalized_score=round(normalized, 2),
                    matched_symptoms=sorted(matched, key=lambda m: m.contribution, reverse=True),
                    treatments=treatments,
                    clinical_criteria=disease.clinical_criteria,
                )
            )

        # Ordenar por score normalizado descendente
        results.sort(key=lambda r: r.normalized_score, reverse=True)

        # Asignar ranking
        for i, result in enumerate(results, start=1):
            result.rank = i

        return results

def check_inconsistencies() -> dict[str, list[str]]:
    """
    Detecta inconsistencias en la ontología médica almacenada en la BD.

    Retorna un diccionario con las categorías de inconsistencias encontradas.
    """
    from core.models import Symptom, Treatment, Disease

    report: dict[str, list[str]] = {
        "sintomas_sin_enfermedad": [],
        "tratamientos_sin_enfermedad": [],
        "enfermedades_sin_sintomas": [],
        "enfermedades_sin_tratamiento": [],
        "enfermedades_sin_criterios_clinicos": [],
    }

    # Síntomas que no están asociados a ninguna enfermedad
    for symptom in Symptom.objects.all():
        if not symptom.disease_relations.exists():
            report["sintomas_sin_enfermedad"].append(
                f"SÍNTOMA HUÉRFANO: '{symptom.name}' (ID: {symptom.pk})"
            )

    # Tratamientos no asignados a ninguna enfermedad
    for treatment in Treatment.objects.all():
        if not treatment.disease_relations.exists():
            report["tratamientos_sin_enfermedad"].append(
                f"TRATAMIENTO HUÉRFANO: '{treatment.name}' (ID: {treatment.pk})"
            )

    # Enfermedades sin síntomas definidos
    for disease in Disease.objects.all():
        if not disease.symptom_relations.exists():
            report["enfermedades_sin_sintomas"].append(
                f"ENFERMEDAD SIN SÍNTOMAS: '{disease.name}' (ID: {disease.pk})"
            )

        # Enfermedades sin tratamiento
        if not disease.treatment_relations.exists():
            report["enfermedades_sin_tratamiento"].append(
                f"ENFERMEDAD SIN TRATAMIENTO: '{disease.name}' (ID: {disease.pk})"
            )

        # Enfermedades sin criterios clínicos documentados
        if not disease.clinical_criteria.strip():
            report["enfermedades_sin_criterios_clinicos"].append(
                f"SIN CRITERIOS CLÍNICOS: '{disease.name}' (ID: {disease.pk})"
            )

    return report


def format_inconsistencies_report(inconsistencies: dict[str, list[str]]) -> str:
    """Formatea el reporte de inconsistencias como texto estructurado."""
    lines = [
        "═" * 64,
        "  REPORTE DE INCONSISTENCIAS — MediKnow",
        "═" * 64,
    ]
    total = 0
    labels = {
        "sintomas_sin_enfermedad": "Síntomas sin enfermedad asociada",
        "tratamientos_sin_enfermedad": "Tratamientos sin enfermedad asociada",
        "enfermedades_sin_sintomas": "Enfermedades sin síntomas definidos",
        "enfermedades_sin_tratamiento": "Enfermedades sin tratamiento asignado",
        "enfermedades_sin_criterios_clinicos": "Enfermedades sin criterios clínicos",
    }
    for key, label in labels.items():
        items = inconsistencies.get(key, [])
        lines.append(f"\n▶ {label} ({len(items)})")
        if items:
            for item in items:
                lines.append(f"    ⚠ {item}")
        else:
            lines.append("    ✓ Sin inconsistencias en esta categoría.")
        total += len(items)

    lines.append("\n" + "─" * 64)
    lines.append(f"  Total de inconsistencias detectadas: {total}")
    lines.append("═" * 64)
    return "\n".join(lines)
def export_diagnosis_report(
    results: list[DiseaseScore],
    symptoms_input: dict[str, int],
    doctor: str = "No especificado",
    patient_code: str = "No especificado",
    top_n: int = 3,
) -> str:
    """
    Exporta los resultados del diagnóstico como texto estructurado limpio.

    Args:
        results: Lista de DiseaseScore devuelta por InferenceEngine.run()
        symptoms_input: Diccionario original de síntomas + intensidades.
        doctor: Nombre del médico.
        patient_code: Código anónimo del paciente.
        top_n: Número de diagnósticos principales a mostrar.

    Returns:
        String con el reporte formateado.
    """
    from datetime import datetime

    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    sep = "═" * 64

    lines = [
        sep,
        "  REPORTE DE DIAGNÓSTICO DIFERENCIAL",
        "  MediKnow — Sistema de Gestión del Conocimiento Médico",
        sep,
        f"  Fecha y hora   : {now}",
        f"  Médico         : {doctor}",
        f"  Cód. paciente  : {patient_code}",
        "",
        "─" * 64,
        "  SÍNTOMAS INGRESADOS",
        "─" * 64,
    ]

    for symptom, intensity in sorted(symptoms_input.items(), key=lambda x: -x[1]):
        bar = "█" * intensity + "░" * (10 - intensity)
        lines.append(f"  • {symptom:<40} [{bar}] {intensity}/10")

    lines.append("")
    lines.append("─" * 64)
    lines.append(f"  TOP {top_n} DIAGNÓSTICOS DIFERENCIALES (por score ponderado)")
    lines.append("─" * 64)

    if not results:
        lines.append("  ⚠ No se encontraron diagnósticos con suficiente puntuación.")
        lines.append("    Revise los síntomas ingresados o amplíe la ontología.")
    else:
        for ds in results[:top_n]:
            lines.append(f"\n  ┌─ #{ds.rank}  {ds.disease_name}")
            lines.append(f"  │  Score: {ds.normalized_score:.1f}/100")
            lines.append("  │")
            lines.append("  │  Síntomas coincidentes:")
            for ms in ds.matched_symptoms:
                lines.append(
                    f"  │    • {ms.symptom_name} "
                    f"(peso {ms.association_weight} × intensidad {ms.intensity} = {ms.contribution:.0f})"
                )
            lines.append("  │")
            lines.append("  │  Tratamientos sugeridos:")
            for t in ds.treatments:
                lines.append(f"  │    {t}")
            if ds.clinical_criteria:
                lines.append("  │")
                lines.append("  │  Criterios clínicos / Derivación:")
                for crit_line in ds.clinical_criteria.strip().splitlines():
                    lines.append(f"  │    {crit_line.strip()}")
            lines.append("  └" + "─" * 62)

    lines.append("")
    lines.append(sep)
    lines.append("  FIN DEL REPORTE — MediKnow")
    lines.append(sep)

    return "\n".join(lines)