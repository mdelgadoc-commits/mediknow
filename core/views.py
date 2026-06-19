from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages

from .models import Symptom, ClinicalCase, DiagnosisResult
from .inference_engine import (
    InferenceEngine,
    check_inconsistencies,
    format_inconsistencies_report,
    export_diagnosis_report,
)


@require_http_methods(["GET", "POST"])
def cuestionario(request: HttpRequest) -> HttpResponse:
    """
    GET  → Muestra el cuestionario con todos los síntomas de la BD.
    POST → Recibe los síntomas marcados + intensidades, ejecuta el motor
           de inferencia y devuelve los resultados en la misma página.
    """

    # Todos los síntomas disponibles (peso 3 primero, luego 1)
    symptoms = Symptom.objects.order_by("-relevance_level", "name")

    # Valores por defecto para el contexto
    context = {
        "symptoms": symptoms,
        "results": None,
        "symptoms_input": None,
        "doctor_name": "",
        "patient_code": "",
        "error": None,
        "plain_report": None,
    }

    if request.method == "POST":

        # ── 1. Leer datos del médico y del paciente ────────────
        doctor_name  = request.POST.get("doctor_name", "").strip()
        patient_code = request.POST.get("patient_code", "").strip()

        context["doctor_name"]  = doctor_name
        context["patient_code"] = patient_code

        # ── 2. Construir el diccionario {síntoma: intensidad} ──
        # Solo se incluyen los síntomas cuyos checkboxes fueron marcados.
        symptoms_input: dict[str, int] = {}

        for symptom in symptoms:
            checkbox_name = f"symptom_check_{symptom.pk}"
            slider_name   = f"intensity_{symptom.pk}"

            if checkbox_name in request.POST:
                # El checkbox está marcado → leer la intensidad del slider
                try:
                    intensity = int(request.POST.get(slider_name, 5))
                    # Clampar entre 1 y 10 por seguridad
                    intensity = max(1, min(10, intensity))
                except (ValueError, TypeError):
                    intensity = 5

                symptoms_input[symptom.name] = intensity

        context["symptoms_input"] = symptoms_input

        # ── 3. Validación mínima ───────────────────────────────
        if not symptoms_input:
            context["error"] = "Debe seleccionar al menos un síntoma."
            return render(request, "core/cuestionario.html", context)

        # ── 4. Ejecutar el motor de inferencia ────────────────
        engine  = InferenceEngine()
        results = engine.run(symptoms_input)
        context["results"] = results

        # ── 5. Generar reporte de texto estructurado ──────────
        plain_report = export_diagnosis_report(
            results=results,
            symptoms_input=symptoms_input,
            doctor=doctor_name or "No especificado",
            patient_code=patient_code or "No especificado",
            top_n=3,
        )
        context["plain_report"] = plain_report

        # ── 6. Persistir el caso clínico en la BD ─────────────
        if doctor_name and patient_code:
            try:
                case = ClinicalCase.objects.create(
                    doctor_name=doctor_name,
                    patient_code=patient_code,
                    symptoms_input=symptoms_input,
                    notes="Caso generado automáticamente desde el cuestionario.",
                )

                # Guardar los resultados del diagnóstico
                for ds in results[:3]:  # Solo top 3
                    from .models import Disease
                    try:
                        disease_obj = Disease.objects.get(name=ds.disease_name)
                        DiagnosisResult.objects.create(
                            clinical_case=case,
                            disease=disease_obj,
                            score=ds.normalized_score,
                            rank=ds.rank,
                            recommendation="\n".join(ds.treatments),
                        )
                    except Disease.DoesNotExist:
                        pass  # No bloquear si el nombre cambió

            except Exception:
                # No romper la UI si falla la persistencia
                pass

    return render(request, "core/cuestionario.html", context)


@require_http_methods(["GET"])
def reportes(request: HttpRequest) -> HttpResponse:
    """
    Muestra el reporte de inconsistencias de la ontología médica
    y permite exportar el reporte de texto del último caso.
    """
    inconsistencias = check_inconsistencies()
    reporte_texto   = format_inconsistencies_report(inconsistencias)

    total_issues = sum(len(v) for v in inconsistencias.values())

    context = {
        "inconsistencias": inconsistencias,
        "reporte_texto": reporte_texto,
        "total_issues": total_issues,
    }
    return render(request, "core/reportes.html", context)


@require_http_methods(["POST"])
def exportar_reporte(request: HttpRequest) -> HttpResponse:
    """
    Recibe el reporte en texto plano desde el formulario
    y lo devuelve como descarga .txt.

    Conectar en urls.py:
        path('exportar/', views.exportar_reporte, name='exportar_reporte'),
    """
    plain_report  = request.POST.get("plain_report", "")
    patient_code  = request.POST.get("patient_code", "caso")

    filename = f"mediknow_diagnostico_{patient_code.replace(' ', '_')}.txt"

    response = HttpResponse(plain_report, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response