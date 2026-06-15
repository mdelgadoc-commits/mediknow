from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


# ─────────────────────────────────────────────
#  1. CATEGORÍA MÉDICA
# ─────────────────────────────────────────────
class MedicalCategory(models.Model):
    """Categoría médica (ej. Urología, Oftalmología, ORL…)"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Categoría")
    description = models.TextField(blank=True, verbose_name="Descripción")

    class Meta:
        verbose_name = "Categoría médica"
        verbose_name_plural = "Categorías médicas"
        ordering = ["name"]

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────
#  2. ENFERMEDAD
# ─────────────────────────────────────────────
class Disease(models.Model):
    """Enfermedad registrada en la ontología médica."""
    name = models.CharField(max_length=200, unique=True, verbose_name="Nombre")
    description = models.TextField(verbose_name="Descripción")
    category = models.ForeignKey(
        MedicalCategory,
        on_delete=models.PROTECT,
        related_name="diseases",
        verbose_name="Categoría médica",
    )
    # Guía clínica / criterios especiales (ej. Criterios de Centor para Faringoamigdalitis)
    clinical_criteria = models.TextField(
        blank=True,
        verbose_name="Criterios clínicos / notas",
        help_text="Criterios diagnósticos formales, derivaciones o exámenes sugeridos.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Enfermedad"
        verbose_name_plural = "Enfermedades"
        ordering = ["name"]

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────
#  3. SÍNTOMA
# ─────────────────────────────────────────────
class Symptom(models.Model):
    """
    Síntoma con su peso diagnóstico base.
    PATHOGNOMONIC / MAJOR → peso 3
    COMMON / MINOR        → peso 1
    """

    class RelevanceLevel(models.IntegerChoices):
        MINOR = 1, "Común / Menor (peso 1)"
        MAJOR = 3, "Patognomónico / Mayor (peso 3)"

    name = models.CharField(max_length=200, unique=True, verbose_name="Nombre")
    description = models.TextField(blank=True, verbose_name="Descripción")
    relevance_level = models.IntegerField(
        choices=RelevanceLevel.choices,
        default=RelevanceLevel.MINOR,
        verbose_name="Nivel de relevancia",
        help_text="Define el peso base del síntoma para el motor de inferencia.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Síntoma"
        verbose_name_plural = "Síntomas"
        ordering = ["-relevance_level", "name"]

    def __str__(self):
        return f"{self.name} (peso base: {self.relevance_level})"


# ─────────────────────────────────────────────
#  4. TRATAMIENTO
# ─────────────────────────────────────────────
class Treatment(models.Model):
    """Tratamiento con tipo y condiciones de aplicación."""

    class TreatmentType(models.TextChoices):
        PHARMACOLOGICAL = "FARM", "Farmacológico"
        SURGICAL = "QUIR", "Quirúrgico"
        PHYSICAL = "FISI", "Fisioterapéutico"
        DIETARY = "DIET", "Dietético / Nutricional"
        REFERRAL = "DERI", "Derivación a especialista"
        OTHER = "OTRO", "Otro"

    name = models.CharField(max_length=200, verbose_name="Nombre")
    treatment_type = models.CharField(
        max_length=4,
        choices=TreatmentType.choices,
        default=TreatmentType.PHARMACOLOGICAL,
        verbose_name="Tipo de tratamiento",
    )
    application_conditions = models.TextField(
        verbose_name="Condiciones de aplicación",
        help_text="Cuándo y cómo aplicar este tratamiento.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tratamiento"
        verbose_name_plural = "Tratamientos"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} [{self.get_treatment_type_display()}]"


# ─────────────────────────────────────────────
#  5. RELACIÓN ENFERMEDAD ↔ SÍNTOMA
# ─────────────────────────────────────────────
class DiseaseSymptomRelation(models.Model):
    """
    Tabla intermedia Many-to-Many entre Disease y Symptom.
    Guarda el peso formal de la asociación en el contexto de ESA enfermedad,
    lo que permite que un mismo síntoma tenga distinto peso según la enfermedad.
    """

    class AssociationWeight(models.IntegerChoices):
        MINOR = 1, "Menor (1)"
        MAJOR = 3, "Mayor / Patognomónico (3)"

    disease = models.ForeignKey(
        Disease,
        on_delete=models.CASCADE,
        related_name="symptom_relations",
        verbose_name="Enfermedad",
    )
    symptom = models.ForeignKey(
        Symptom,
        on_delete=models.CASCADE,
        related_name="disease_relations",
        verbose_name="Síntoma",
    )
    association_weight = models.IntegerField(
        choices=AssociationWeight.choices,
        default=AssociationWeight.MINOR,
        verbose_name="Peso de asociación",
        help_text="Peso formal de esta relación para el motor de inferencia.",
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Notas",
        help_text="Observaciones clínicas adicionales sobre esta relación.",
    )

    class Meta:
        verbose_name = "Relación Enfermedad–Síntoma"
        verbose_name_plural = "Relaciones Enfermedad–Síntoma"
        unique_together = ("disease", "symptom")
        ordering = ["-association_weight"]

    def __str__(self):
        return (
            f"{self.disease.name} ← {self.symptom.name} "
            f"(peso: {self.association_weight})"
        )


# ─────────────────────────────────────────────
#  6. RELACIÓN ENFERMEDAD ↔ TRATAMIENTO
# ─────────────────────────────────────────────
class DiseaseTreatmentRelation(models.Model):
    """
    Tabla intermedia entre Disease y Treatment.
    Permite registrar condiciones formales de aplicación del tratamiento
    en el contexto de una enfermedad específica.
    """

    disease = models.ForeignKey(
        Disease,
        on_delete=models.CASCADE,
        related_name="treatment_relations",
        verbose_name="Enfermedad",
    )
    treatment = models.ForeignKey(
        Treatment,
        on_delete=models.CASCADE,
        related_name="disease_relations",
        verbose_name="Tratamiento",
    )
    formal_conditions = models.TextField(
        verbose_name="Condiciones formales de aplicación",
        help_text="Condiciones específicas para aplicar este tratamiento a esta enfermedad.",
    )
    priority = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Prioridad",
        help_text="1 = primera línea, 2 = segunda línea, etc.",
    )

    class Meta:
        verbose_name = "Relación Enfermedad–Tratamiento"
        verbose_name_plural = "Relaciones Enfermedad–Tratamiento"
        unique_together = ("disease", "treatment")
        ordering = ["priority"]

    def __str__(self):
        return (
            f"{self.disease.name} → {self.treatment.name} "
            f"(prioridad: {self.priority})"
        )


# ─────────────────────────────────────────────
#  7. CASO CLÍNICO
# ─────────────────────────────────────────────
class ClinicalCase(models.Model):
    """Registro de un caso clínico evaluado por un médico."""

    doctor_name = models.CharField(max_length=200, verbose_name="Médico responsable")
    patient_code = models.CharField(
        max_length=50,
        verbose_name="Código de paciente",
        help_text="Identificador anónimo del paciente.",
    )
    notes = models.TextField(blank=True, verbose_name="Notas clínicas adicionales")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de consulta")

    # JSON snapshot de los síntomas ingresados: {"Disuria": 8, "Polaquiuria": 5}
    symptoms_input = models.JSONField(
        verbose_name="Síntomas ingresados (JSON)",
        help_text="Diccionario síntoma→intensidad enviado por el formulario.",
    )

    class Meta:
        verbose_name = "Caso clínico"
        verbose_name_plural = "Casos clínicos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Caso #{self.pk} – {self.doctor_name} ({self.created_at:%d/%m/%Y})"


# ─────────────────────────────────────────────
#  8. RESULTADO DE DIAGNÓSTICO
# ─────────────────────────────────────────────
class DiagnosisResult(models.Model):
    """Resultado generado por el motor de inferencia para un caso clínico."""

    clinical_case = models.ForeignKey(
        ClinicalCase,
        on_delete=models.CASCADE,
        related_name="results",
        verbose_name="Caso clínico",
    )
    disease = models.ForeignKey(
        Disease,
        on_delete=models.PROTECT,
        related_name="diagnosis_results",
        verbose_name="Enfermedad sugerida",
    )
    score = models.FloatField(verbose_name="Puntaje calculado")
    rank = models.PositiveSmallIntegerField(verbose_name="Posición en el ranking")
    recommendation = models.TextField(
        blank=True,
        verbose_name="Recomendación / exámenes sugeridos",
    )

    class Meta:
        verbose_name = "Resultado de diagnóstico"
        verbose_name_plural = "Resultados de diagnóstico"
        ordering = ["rank"]

    def __str__(self):
        return f"#{self.rank} {self.disease.name} (score: {self.score:.1f})"