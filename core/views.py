from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login as auth_login
from django.db.models import Count

from .models import Symptom, ClinicalCase, DiagnosisResult, Allergy, Patient, Disease, MedicalCategory, Treatment, DiseaseSymptomRelation, DiseaseTreatmentRelation

from .inference_engine import InferenceEngine, check_inconsistencies, format_inconsistencies_report, export_diagnosis_report, format_query_report
from . import ontology_catalog
from .ontology import validate_new_disease


@login_required(login_url="login")
@require_http_methods(["GET"])
def menu(request):
    """Pantalla principal tras el login: Enfermedades / Ingresar sintomas."""
    return render(request, "core/menu.html")


@require_http_methods(["GET", "POST"])
def registro_medico(request):
    context = {"error": None}
    if request.user.is_authenticated:
        return redirect("menu")
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
            return redirect("menu")
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
def actualizar_antecedentes(request):
    """Actualiza los antecedentes/complicaciones del paciente (campo opcional)."""
    patient_id = request.POST.get("patient_id")
    medical_background = request.POST.get("medical_background", "").strip()
    try:
        patient = Patient.objects.get(pk=patient_id, doctor=request.user)
        patient.medical_background = medical_background
        patient.save()
        messages.success(request, "Antecedentes del paciente actualizados.")
    except Patient.DoesNotExist:
        messages.error(request, "No se encontro el paciente indicado.")
    return redirect(f"/sintomas/?patient={patient_id}")


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
@require_http_methods(["GET", "POST"])
def enfermedades(request):
    """
    Registro de enfermedades preestablecidas (nombre, descripcion,
    categoria medica). Permite agregar nuevas enfermedades, validando
    que existan en el catalogo alineado con CIE-10, CIE-11 y REUNIS.
    """
    context = {
        "diseases": Disease.objects.select_related("category").order_by("name"),
        "errors": {},
        "success": None,
        "form_values": {"name": "", "description": "", "category": ""},
        "show_form": False,
    }

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        category = request.POST.get("category", "").strip()
        context["form_values"] = {"name": name, "description": description, "category": category}
        context["show_form"] = True

        if not name or not description or not category:
            context["errors"]["general"] = "Todos los campos son obligatorios."
        else:
            is_valid, errors, entry = validate_new_disease(name, description, category)
            if not is_valid:
                context["errors"] = errors
            elif Disease.objects.filter(name__iexact=entry["name"]).exists():
                context["errors"]["name"] = "Esta enfermedad ya esta registrada."
            else:
                medical_category, _ = MedicalCategory.objects.get_or_create(
                    name=entry["category"],
                    defaults={"description": "Categoria alineada con CIE-10/CIE-11/REUNIS."},
                )
                Disease.objects.create(
                    name=entry["name"],
                    description=description,
                    category=medical_category,
                    cie10_code=entry["cie10"],
                    cie11_code=entry["cie11"],
                    reunis_capitulo=entry["reunis_capitulo"],
                )
                context["success"] = f'Enfermedad "{entry["name"]}" registrada correctamente.'
                context["form_values"] = {"name": "", "description": "", "category": ""}
                context["show_form"] = False
                context["diseases"] = Disease.objects.select_related("category").order_by("name")

    return render(request, "core/enfermedades.html", context)

@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def sintomas(request):
    """Registro de sintomas (nombre, descripcion, nivel de relevancia diagnostica)."""
    context = {
        "symptoms": Symptom.objects.order_by("-relevance_level", "name"),
        "errors": {},
        "success": None,
        "form_values": {"name": "", "description": "", "relevance_level": "1"},
        "show_form": False,
        "relevance_choices": Symptom.RelevanceLevel.choices,
    }

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        relevance_level = request.POST.get("relevance_level", "").strip()
        context["form_values"] = {"name": name, "description": description, "relevance_level": relevance_level}
        context["show_form"] = True

        valid_levels = {str(choice[0]) for choice in Symptom.RelevanceLevel.choices}
        if not name or relevance_level not in valid_levels:
            context["errors"]["general"] = "El nombre y el nivel de relevancia son obligatorios."
        elif Symptom.objects.filter(name__iexact=name).exists():
            context["errors"]["name"] = "Ya existe un sintoma con ese nombre."
        else:
            Symptom.objects.create(name=name, description=description, relevance_level=int(relevance_level))
            context["success"] = f'Sintoma "{name}" registrado correctamente.'
            context["form_values"] = {"name": "", "description": "", "relevance_level": "1"}
            context["show_form"] = False
            context["symptoms"] = Symptom.objects.order_by("-relevance_level", "name")

    return render(request, "core/sintomas.html", context)

@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def tratamientos(request):
    """Registro de tratamientos (nombre, tipo, condiciones de aplicacion)."""
    context = {
        "treatments": Treatment.objects.order_by("name"),
        "errors": {},
        "success": None,
        "form_values": {"name": "", "treatment_type": "FARM", "application_conditions": ""},
        "show_form": False,
        "type_choices": Treatment.TreatmentType.choices,
    }

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        treatment_type = request.POST.get("treatment_type", "").strip()
        application_conditions = request.POST.get("application_conditions", "").strip()
        context["form_values"] = {"name": name, "treatment_type": treatment_type, "application_conditions": application_conditions}
        context["show_form"] = True

        valid_types = {choice[0] for choice in Treatment.TreatmentType.choices}
        if not name or not application_conditions or treatment_type not in valid_types:
            context["errors"]["general"] = "El nombre, el tipo y las condiciones de aplicacion son obligatorios."
        elif Treatment.objects.filter(name__iexact=name).exists():
            context["errors"]["name"] = "Ya existe un tratamiento con ese nombre."
        else:
            Treatment.objects.create(name=name, treatment_type=treatment_type, application_conditions=application_conditions)
            context["success"] = f'Tratamiento "{name}" registrado correctamente.'
            context["form_values"] = {"name": "", "treatment_type": "FARM", "application_conditions": ""}
            context["show_form"] = False
            context["treatments"] = Treatment.objects.order_by("name")

    return render(request, "core/tratamientos.html", context)

@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def relaciones(request):
    """
    Permite relacionar una enfermedad con sintomas (peso de asociacion)
    y con tratamientos (condiciones formales), requisitos 4 y 5.
    """
    diseases = Disease.objects.order_by("name")
    disease_id = request.GET.get("disease") or request.POST.get("disease_id")
    disease = None
    if disease_id:
        disease = Disease.objects.filter(pk=disease_id).first()

    context = {
        "diseases": diseases,
        "disease": disease,
        "symptom_relations": [],
        "treatment_relations": [],
        "available_symptoms": [],
        "available_treatments": [],
        "weight_choices": DiseaseSymptomRelation.AssociationWeight.choices,
        "errors": {},
        "success": None,
    }

    if disease:
        related_symptom_ids = disease.symptom_relations.values_list("symptom_id", flat=True)
        related_treatment_ids = disease.treatment_relations.values_list("treatment_id", flat=True)
        context["symptom_relations"] = disease.symptom_relations.select_related("symptom").order_by("-association_weight")
        context["treatment_relations"] = disease.treatment_relations.select_related("treatment").order_by("priority")
        context["available_symptoms"] = Symptom.objects.exclude(pk__in=related_symptom_ids).order_by("name")
        context["available_treatments"] = Treatment.objects.exclude(pk__in=related_treatment_ids).order_by("name")

    if request.method == "POST" and disease:
        relation_type = request.POST.get("relation_type")

        if relation_type == "symptom":
            symptom_id = request.POST.get("symptom_id")
            weight = request.POST.get("association_weight")
            notes = request.POST.get("notes", "").strip()
            valid_weights = {str(c[0]) for c in DiseaseSymptomRelation.AssociationWeight.choices}
            symptom = Symptom.objects.filter(pk=symptom_id).first()
            if not symptom or weight not in valid_weights:
                context["errors"]["symptom"] = "Seleccione un sintoma y un peso validos."
            else:
                DiseaseSymptomRelation.objects.create(
                    disease=disease, symptom=symptom, association_weight=int(weight), notes=notes
                )
                context["success"] = f'Sintoma "{symptom.name}" relacionado con "{disease.name}".'

        elif relation_type == "treatment":
            treatment_id = request.POST.get("treatment_id")
            formal_conditions = request.POST.get("formal_conditions", "").strip()
            try:
                priority = int(request.POST.get("priority", 1))
            except ValueError:
                priority = 1
            treatment = Treatment.objects.filter(pk=treatment_id).first()
            if not treatment or not formal_conditions:
                context["errors"]["treatment"] = "Seleccione un tratamiento y escriba las condiciones formales."
            else:
                DiseaseTreatmentRelation.objects.create(
                    disease=disease, treatment=treatment, formal_conditions=formal_conditions, priority=priority
                )
                context["success"] = f'Tratamiento "{treatment.name}" relacionado con "{disease.name}".'

        if not context["errors"]:
            related_symptom_ids = disease.symptom_relations.values_list("symptom_id", flat=True)
            related_treatment_ids = disease.treatment_relations.values_list("treatment_id", flat=True)
            context["symptom_relations"] = disease.symptom_relations.select_related("symptom").order_by("-association_weight")
            context["treatment_relations"] = disease.treatment_relations.select_related("treatment").order_by("priority")
            context["available_symptoms"] = Symptom.objects.exclude(pk__in=related_symptom_ids).order_by("name")
            context["available_treatments"] = Treatment.objects.exclude(pk__in=related_treatment_ids).order_by("name")

    return render(request, "core/relaciones.html", context)


@login_required(login_url="login")
@require_http_methods(["GET"])
def reportes(request):
    inconsistencias = check_inconsistencies()
    reporte_texto = format_inconsistencies_report(inconsistencias)
    total_issues = sum(len(v) for v in inconsistencias.values())
    return render(request, "core/reportes.html", {"inconsistencias": inconsistencias, "reporte_texto": reporte_texto, "total_issues": total_issues})


@login_required(login_url="login")
@require_http_methods(["GET"])
def consultas_avanzadas(request):
    """
    Consultas avanzadas por combinacion de sintomas, enfermedades y
    tratamientos sobre el grafo de conocimiento (requisito 9).

    Permite filtrar enfermedades por:
      - categoria medica
      - conjunto de sintomas (coincidencia con TODOS o con ALGUNO)
      - conjunto de tratamientos (coincidencia con TODOS o con ALGUNO)
      - peso de asociacion sintoma-enfermedad minimo
    Los filtros se combinan entre si (AND), y dentro de cada filtro de
    sintomas/tratamientos el usuario elige el modo de combinacion.
    """
    categories = MedicalCategory.objects.order_by("name")
    all_symptoms = Symptom.objects.order_by("-relevance_level", "name")
    all_treatments = Treatment.objects.order_by("name")

    symptom_ids = [int(s) for s in request.GET.getlist("symptom") if s.isdigit()]
    treatment_ids = [int(t) for t in request.GET.getlist("treatment") if t.isdigit()]
    category_id = request.GET.get("category") or ""
    symptom_mode = request.GET.get("symptom_mode", "any")
    treatment_mode = request.GET.get("treatment_mode", "any")
    min_weight_raw = request.GET.get("min_weight") or ""
    min_weight = int(min_weight_raw) if min_weight_raw in {"1", "3"} else None
    has_search = bool(request.GET)

    context = {
        "categories": categories,
        "symptoms": all_symptoms,
        "treatments": all_treatments,
        "selected_symptom_ids": symptom_ids,
        "selected_treatment_ids": treatment_ids,
        "selected_category_id": category_id,
        "symptom_mode": symptom_mode,
        "treatment_mode": treatment_mode,
        "min_weight": min_weight_raw,
        "has_search": has_search,
        "results": [],
        "plain_report": None,
    }

    if not has_search:
        return render(request, "core/consultas_avanzadas.html", context)

    qs = Disease.objects.select_related("category").all()

    if category_id:
        qs = qs.filter(category_id=category_id)

    if symptom_ids:
        rel_qs = DiseaseSymptomRelation.objects.filter(symptom_id__in=symptom_ids)
        if min_weight:
            rel_qs = rel_qs.filter(association_weight__gte=min_weight)
        if symptom_mode == "all":
            matching_ids = list(
                rel_qs.values("disease_id")
                .annotate(n=Count("symptom_id", distinct=True))
                .filter(n=len(symptom_ids))
                .values_list("disease_id", flat=True)
            )
        else:
            matching_ids = list(rel_qs.values_list("disease_id", flat=True).distinct())
        qs = qs.filter(pk__in=matching_ids)
    elif min_weight:
        qs = qs.filter(symptom_relations__association_weight__gte=min_weight).distinct()

    if treatment_ids:
        rel_t_qs = DiseaseTreatmentRelation.objects.filter(treatment_id__in=treatment_ids)
        if treatment_mode == "all":
            matching_t_ids = list(
                rel_t_qs.values("disease_id")
                .annotate(n=Count("treatment_id", distinct=True))
                .filter(n=len(treatment_ids))
                .values_list("disease_id", flat=True)
            )
        else:
            matching_t_ids = list(rel_t_qs.values_list("disease_id", flat=True).distinct())
        qs = qs.filter(pk__in=matching_t_ids)

    qs = qs.distinct().order_by("name")

    results = []
    for disease in qs:
        results.append(
            {
                "disease": disease,
                "symptom_relations": disease.symptom_relations.select_related("symptom").order_by("-association_weight"),
                "treatment_relations": disease.treatment_relations.select_related("treatment").order_by("priority"),
                "matched_symptom_ids": symptom_ids,
                "matched_treatment_ids": treatment_ids,
            }
        )
    context["results"] = results

    filters_summary = {
        "category": categories.filter(pk=category_id).first().name if category_id else None,
        "symptom_mode": symptom_mode,
        "treatment_mode": treatment_mode,
        "min_weight": min_weight,
        "symptoms": list(Symptom.objects.filter(pk__in=symptom_ids)),
        "treatments": list(Treatment.objects.filter(pk__in=treatment_ids)),
    }
    context["plain_report"] = format_query_report(results, filters_summary)

    return render(request, "core/consultas_avanzadas.html", context)
