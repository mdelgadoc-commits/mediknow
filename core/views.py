from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login as auth_login

from .models import Symptom, ClinicalCase, DiagnosisResult, Allergy, Patient, Disease
from .inference_engine import InferenceEngine, check_inconsistencies, format_inconsistencies_report, export_diagnosis_report


@require_http_methods(["GET", "POST"])
def registro_medico(request):
    context = {"error": None}
    if request.user.is_authenticated:
        return redirect("cuestionario")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        password1 = request.POST.get("password1", "")
        password2 = request.POST.get("password2", "")
        if not username or not password1:
            context["error"] = "El usuario y la contrasena son obligatorios."
        elif password1 != password2:
            context["error"] = "Las contrasenas no coinciden."
        elif len(password1) < 8:
            context["error"] = "La contrasena debe tener al menos 8 caracteres."
        elif User.objects.filter(username=username).exists():
            context["error"] = "El usuario ya existe."
        else:
            user = User.objects.create_user(username=username, password=password1, first_name=first_name, last_name=last_name)
            auth_login(request, user)
            return redirect("cuestionario")
    return render(request, "core/registro_medico.html", context)


@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def registro_paciente(request):
    allergies = Allergy.objects.order_by("category", "name")
    context = {"allergies": allergies, "error": None, "success": None, "patient_id": None}
    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        code = request.POST.get("code", "").strip()
        other_allergies = request.POST.get("other_allergies", "").strip()
        medical_background = request.POST.get("medical_background", "").strip()
        try:
            age = int(request.POST.get("age", 0))
        except ValueError:
            age = 0
        sex = request.POST.get("sex", "")
        if not full_name or not code:
            context["error"] = "El nombre y el codigo son obligatorios."
            return render(request, "core/registro_paciente.html", context)
        if age <= 0 or age > 120:
            context["error"] = "Ingrese una edad valida."
            return render(request, "core/registro_paciente.html", context)
        if Patient.objects.filter(doctor=request.user, code=code).exists():
            context["error"] = "Ya existe un paciente con ese codigo."
            return render(request, "core/registro_paciente.html", context)
        patient = Patient.objects.create(
            doctor=request.user, full_name=full_name, code=code,
            age=age, sex=sex, other_allergies=other_allergies,
            medical_background=medical_background,
        )
        selected_ids = []
        for allergy in allergies:
            if "allergy_" + str(allergy.pk) in request.POST:
                selected_ids.append(allergy.pk)
        if selected_ids:
            patient.allergies.set(selected_ids)
        context["success"] = full_name + " (" + code + ")"
        context["patient_id"] = patient.pk
    return render(request, "core/registro_paciente.html", context)


@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def cuestionario(request):
    symptoms = Symptom.objects.order_by("-relevance_level", "name")
    patient = None
    patient_id = request.GET.get("patient") or request.POST.get("patient_id")
    if patient_id:
        try:
            patient = Patient.objects.prefetch_related("allergies").get(pk=patient_id, doctor=request.user)
        except Patient.DoesNotExist:
            patient = None
    context = {
        "symptoms": symptoms,
        "results": None,
        "symptoms_input": None,
        "patient": patient,
        "allergy_warnings": [],
        "plain_report": None,
        "error": None,
    }
    if request.method == "POST":
        post_patient_id = request.POST.get("patient_id")
        if post_patient_id and not patient:
            try:
                patient = Patient.objects.prefetch_related("allergies").get(pk=post_patient_id, doctor=request.user)
                context["patient"] = patient
            except Patient.DoesNotExist:
                pass
        symptoms_input = {}
        for symptom in symptoms:
            if "symptom_check_" + str(symptom.pk) in request.POST:
                try:
                    intensity = int(request.POST.get("intensity_" + str(symptom.pk), 5))
                    intensity = max(1, min(10, intensity))
                except (ValueError, TypeError):
                    intensity = 5
                symptoms_input[symptom.name] = intensity
        context["symptoms_input"] = symptoms_input
        if not symptoms_input:
            context["error"] = "Debe seleccionar al menos un sintoma."
            return render(request, "core/cuestionario.html", context)
        engine = InferenceEngine()
        results = engine.run(symptoms_input)
        context["results"] = results
        if patient:
            all_allergies = patient.get_all_allergies_display()
            warnings = []
            for ds in results[:3]:
                for treatment in ds.treatments:
                    for allergy_name in all_allergies:
                        if any(word.lower() in treatment.lower() for word in allergy_name.split() if len(word) > 4):
                            warnings.append({"disease": ds.disease_name, "treatment": treatment, "allergy": allergy_name})
            context["allergy_warnings"] = warnings
        doctor_display = request.user.get_full_name() or request.user.username
        patient_code = patient.code if patient else "Sin paciente"
        plain_report = export_diagnosis_report(results=results, symptoms_input=symptoms_input, doctor=doctor_display, patient_code=patient_code, top_n=3)
        context["plain_report"] = plain_report
        try:
            case = ClinicalCase.objects.create(
                doctor_name=doctor_display, patient_code=patient_code,
                symptoms_input=symptoms_input,
                notes="Paciente ID: " + str(patient.pk) if patient else "",
            )
            for ds in results[:3]:
                try:
                    disease_obj = Disease.objects.get(name=ds.disease_name)
                    DiagnosisResult.objects.create(clinical_case=case, disease=disease_obj, score=ds.normalized_score, rank=ds.rank, recommendation="\n".join(ds.treatments))
                except Disease.DoesNotExist:
                    pass
        except Exception:
            pass
    return render(request, "core/cuestionario.html", context)


@login_required(login_url="login")
@require_http_methods(["POST"])
def exportar_reporte(request):
    plain_report = request.POST.get("plain_report", "")
    patient_code = request.POST.get("patient_code", "caso")
    filename = "mediknow_" + patient_code.replace(" ", "_") + ".txt"
    response = HttpResponse(plain_report, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="' + filename + '"'
    return response


@login_required(login_url="login")
@require_http_methods(["GET"])
def reportes(request):
    inconsistencias = check_inconsistencies()
    reporte_texto = format_inconsistencies_report(inconsistencias)
    total_issues = sum(len(v) for v in inconsistencias.values())
    return render(request, "core/reportes.html", {"inconsistencias": inconsistencias, "reporte_texto": reporte_texto, "total_issues": total_issues})