from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class MedicalCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Categoria")
    description = models.TextField(blank=True, verbose_name="Descripcion")

    class Meta:
        verbose_name = "Categoria medica"
        verbose_name_plural = "Categorias medicas"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Disease(models.Model):
    name = models.CharField(max_length=200, unique=True, verbose_name="Nombre")
    description = models.TextField(verbose_name="Descripcion")
    category = models.ForeignKey(
        MedicalCategory,
        on_delete=models.PROTECT,
        related_name="diseases",
        verbose_name="Categoria medica",
    )
    clinical_criteria = models.TextField(blank=True, verbose_name="Criterios clinicos / notas")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Enfermedad"
        verbose_name_plural = "Enfermedades"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Symptom(models.Model):
    class RelevanceLevel(models.IntegerChoices):
        MINOR = 1, "Comun / Menor (peso 1)"
        MAJOR = 3, "Patognomonico / Mayor (peso 3)"

    name = models.CharField(max_length=200, unique=True, verbose_name="Nombre")
    description = models.TextField(blank=True, verbose_name="Descripcion")
    relevance_level = models.IntegerField(
        choices=RelevanceLevel.choices,
        default=RelevanceLevel.MINOR,
        verbose_name="Nivel de relevancia",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sintoma"
        verbose_name_plural = "Sintomas"
        ordering = ["-relevance_level", "name"]

    def __str__(self):
        return f"{self.name} (peso base: {self.relevance_level})"


class Treatment(models.Model):
    class TreatmentType(models.TextChoices):
        PHARMACOLOGICAL = "FARM", "Farmacologico"
        SURGICAL = "QUIR", "Quirurgico"
        PHYSICAL = "FISI", "Fisioterapeutico"
        DIETARY = "DIET", "Dietetico / Nutricional"
        REFERRAL = "DERI", "Derivacion a especialista"
        OTHER = "OTRO", "Otro"

    name = models.CharField(max_length=200, verbose_name="Nombre")
    treatment_type = models.CharField(
        max_length=4,
        choices=TreatmentType.choices,
        default=TreatmentType.PHARMACOLOGICAL,
        verbose_name="Tipo de tratamiento",
    )
    application_conditions = models.TextField(verbose_name="Condiciones de aplicacion")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tratamiento"
        verbose_name_plural = "Tratamientos"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} [{self.get_treatment_type_display()}]"


class DiseaseSymptomRelation(models.Model):
    class AssociationWeight(models.IntegerChoices):
        MINOR = 1, "Menor (1)"
        MAJOR = 3, "Mayor / Patognomonico (3)"

    disease = models.ForeignKey(
        Disease, on_delete=models.CASCADE, related_name="symptom_relations", verbose_name="Enfermedad"
    )
    symptom = models.ForeignKey(
        Symptom, on_delete=models.CASCADE, related_name="disease_relations", verbose_name="Sintoma"
    )
    association_weight = models.IntegerField(
        choices=AssociationWeight.choices, default=AssociationWeight.MINOR, verbose_name="Peso de asociacion"
    )
    notes = models.TextField(blank=True, verbose_name="Notas")

    class Meta:
        verbose_name = "Relacion Enfermedad-Sintoma"
        verbose_name_plural = "Relaciones Enfermedad-Sintoma"
        unique_together = ("disease", "symptom")
        ordering = ["-association_weight"]

    def __str__(self):
        return f"{self.disease.name} - {self.symptom.name} (peso: {self.association_weight})"


class DiseaseTreatmentRelation(models.Model):
    disease = models.ForeignKey(
        Disease, on_delete=models.CASCADE, related_name="treatment_relations", verbose_name="Enfermedad"
    )
    treatment = models.ForeignKey(
        Treatment, on_delete=models.CASCADE, related_name="disease_relations", verbose_name="Tratamiento"
    )
    formal_conditions = models.TextField(verbose_name="Condiciones formales de aplicacion")
    priority = models.PositiveSmallIntegerField(default=1, verbose_name="Prioridad")

    class Meta:
        verbose_name = "Relacion Enfermedad-Tratamiento"
        verbose_name_plural = "Relaciones Enfermedad-Tratamiento"
        unique_together = ("disease", "treatment")
        ordering = ["priority"]

    def __str__(self):
        return f"{self.disease.name} -> {self.treatment.name} (prioridad: {self.priority})"


class Allergy(models.Model):
    name = models.CharField(max_length=150, unique=True, verbose_name="Nombre")
    description = models.TextField(blank=True, verbose_name="Descripcion")
    category = models.CharField(max_length=80, blank=True, verbose_name="Categoria")

    class Meta:
        verbose_name = "Alergia"
        verbose_name_plural = "Alergias"
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class Patient(models.Model):
    class Sex(models.TextChoices):
        MALE = "M", "Masculino"
        FEMALE = "F", "Femenino"
        OTHER = "O", "Otro"

    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="patients", verbose_name="Medico responsable"
    )
    code = models.CharField(max_length=50, verbose_name="Codigo de paciente")
    full_name = models.CharField(max_length=200, verbose_name="Nombre completo")
    age = models.PositiveSmallIntegerField(verbose_name="Edad")
    sex = models.CharField(max_length=1, choices=Sex.choices, verbose_name="Sexo")
    allergies = models.ManyToManyField(Allergy, blank=True, related_name="patients", verbose_name="Alergias")
    other_allergies = models.TextField(blank=True, verbose_name="Otras alergias")
    medical_background = models.TextField(blank=True, verbose_name="Antecedentes medicos")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de registro")

    class Meta:
        verbose_name = "Paciente"
        verbose_name_plural = "Pacientes"
        ordering = ["-created_at"]
        unique_together = ("doctor", "code")

    def __str__(self):
        return f"{self.full_name} ({self.code})"


class ClinicalCase(models.Model):
    doctor_name = models.CharField(max_length=200, verbose_name="Medico responsable")
    patient_code = models.CharField(max_length=50, verbose_name="Codigo de paciente")
    notes = models.TextField(blank=True, verbose_name="Notas clinicas adicionales")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de consulta")
    symptoms_input = models.JSONField(verbose_name="Sintomas ingresados (JSON)")

    class Meta:
        verbose_name = "Caso clinico"
        verbose_name_plural = "Casos clinicos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Caso #{self.pk} - {self.doctor_name} ({self.created_at:%d/%m/%Y})"


class DiagnosisResult(models.Model):
    clinical_case = models.ForeignKey(
        ClinicalCase, on_delete=models.CASCADE, related_name="results", verbose_name="Caso clinico"
    )
    disease = models.ForeignKey(
        Disease, on_delete=models.PROTECT, related_name="diagnosis_results", verbose_name="Enfermedad sugerida"
    )
    score = models.FloatField(verbose_name="Puntaje calculado")
    rank = models.PositiveSmallIntegerField(verbose_name="Posicion en el ranking")
    recommendation = models.TextField(blank=True, verbose_name="Recomendacion / examenes sugeridos")

    class Meta:
        verbose_name = "Resultado de diagnostico"
        verbose_name_plural = "Resultados de diagnostico"
        ordering = ["rank"]

    def __str__(self):
        return f"#{self.rank} {self.disease.name} (score: {self.score:.1f})"
