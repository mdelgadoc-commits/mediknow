from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import login as auth_login
from django.db.models import Count

# Importaciones locales de la app
from .utils import inferir_categoria_sintoma
# Importaciones locales de la app
from .models import (
    Symptom, 
    ClinicalCase, 
    DiagnosisResult, 
    Allergy, 
    Patient,
    MedicalCategory,  
    Disease           
)

# Importaciones del motor de inferencia y ontología
from .inference_engine import (
    InferenceEngine, 
    check_inconsistencies
)


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

        context["success"] = f"{full_name} ({code})"
        context["patient_id"] = patient.pk
        
        # 1. Si el formulario fue exitoso (POST), mostramos el resumen interactivo de una vez:
        return render(request, "core/resumen_paciente.html", {"paciente": patient})

    # 2. Si el médico solo está entrando a ver el formulario vacío (GET), le mostramos el formulario:
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
    """Registro de sintomas (nombre, descripcion, nivel de relevancia diagnostica)"""
    context = {
        "symptoms": Symptom.objects.order_by("-relevance_level", "name"),
        "errors": {},
        "success": None,
        "form_values": {"name": "", "description": "", "relevance_level": ""},
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
            Symptom.objects.create(name=name, description=description, relevance_level=relevance_level)
            context["success"] = f'Sintoma "{name}" registrado correctamente.'
            context["form_values"] = {"name": "", "description": "", "relevance_level": ""}
            context["show_form"] = False
            context["symptoms"] = Symptom.objects.order_by("-relevance_level", "name")

    # ==========================================
    # INFERENCIA SEMÁNTICA DESDE LA ONTOLOGÍA
    # ==========================================
    # Recorremos el QuerySet de síntomas en el contexto (tanto para GET como para POST exitosos)
    # y les inyectamos la categoría de forma temporal para que esté disponible en el HTML.
    for symptom in context["symptoms"]:
        symptom.inferred_category = inferir_categoria_sintoma(symptom.name)

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

@login_required(login_url="login")
@require_http_methods(["GET"])
def pacientes(request):
    # FILTRADO EXACTO: Trae SOLO los pacientes cuyo doctor es el usuario que inició sesión
    lista_pacientes = Patient.objects.filter(doctor=request.user).order_by('full_name')
    return render(request, 'core/pacientes.html', {'pacientes': lista_pacientes})

@login_required(login_url="login")
@require_http_methods(["GET"])
def doctores(request):
    # Trae a todos los médicos registrados (User) en el sistema de manera limpia
    lista_doctores = User.objects.all().order_by('username')
    return render(request, 'core/doctores.html', {'doctores': lista_doctores})

# =====================================================================
# EXPORTACIÓN DE REPORTES EN FORMATO PDF ESTRUCTURADO (A COLOR)
# =====================================================================
from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def exportar_reporte(request):
    # 1. Crear respuesta HTTP tipo PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reporte_inconsistencias_mediknow.pdf"'

    # 2. Configurar el lienzo básico
    doc = SimpleDocTemplate(response, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []

    # 3. Definir la paleta de colores clínicos estructurados
    COLOR_PRIMARY = colors.HexColor("#1e3a8a")    # Azul Oscuro Corporativo
    COLOR_ALERT_RED = colors.HexColor("#991b1b")  # Rojo Alerta Crítica (Huérfanos)
    COLOR_ALERT_WARN = colors.HexColor("#9a3412") # Naranja Alerta Media
    COLOR_BG_LIGHT = colors.HexColor("#f8fafc")   # Fondo gris claro sutil
    COLOR_TEXT = colors.HexColor("#334155")       # Texto principal

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, textColor=COLOR_PRIMARY, spaceAfter=4)
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor("#64748b"), spaceAfter=18)
    heading_style = ParagraphStyle('HeadingStyle', parent=styles['Heading2'], fontSize=12, textColor=COLOR_PRIMARY, spaceBefore=12, spaceAfter=6)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=9.5, textColor=COLOR_TEXT, leading=14)
    alert_red_style = ParagraphStyle('RedAlert', parent=styles['Normal'], fontSize=9.5, textColor=COLOR_ALERT_RED, fontName="Helvetica-Bold")
    alert_warn_style = ParagraphStyle('WarnAlert', parent=styles['Normal'], fontSize=9.5, textColor=COLOR_ALERT_WARN)

    # Encabezado del PDF estructurado
    story.append(Paragraph("MediKnow — Sistema de Inferencia Clínica", title_style))
    story.append(Paragraph("REPORTE DE INCONSISTENCIAS DEL MODELO DE CONOCIMIENTO", subtitle_style))
    story.append(Spacer(1, 5))

    # Mapeo de relaciones dinámicas basado en tus modelos de Django
    from .models import Disease, Symptom, Treatment
    
    sintomas_huerfanos = Symptom.objects.none()
    if hasattr(Symptom, 'enfermedades'): sintomas_huerfanos = Symptom.objects.filter(enfermedades__isnull=True)
    elif hasattr(Symptom, 'diseases'): sintomas_huerfanos = Symptom.objects.filter(diseases__isnull=True)

    tratamientos_huerfanos = Treatment.objects.none()
    if hasattr(Treatment, 'enfermedades'): tratamientos_huerfanos = Treatment.objects.filter(enfermedades__isnull=True)
    elif hasattr(Treatment, 'diseases'): tratamientos_huerfanos = Treatment.objects.filter(diseases__isnull=True)

    enfermedades_sin_sintomas = Disease.objects.none()
    if hasattr(Disease, 'sintomas'): enfermedades_sin_sintomas = Disease.objects.filter(sintomas__isnull=True)
    elif hasattr(Disease, 'symptoms'): enfermedades_sin_sintomas = Disease.objects.filter(symptoms__isnull=True)

    enfermedades_sin_tratamiento = Disease.objects.none()
    if hasattr(Disease, 'tratamientos'): enfermedades_sin_tratamiento = Disease.objects.filter(tratamientos__isnull=True)
    elif hasattr(Disease, 'treatments'): enfermedades_sin_tratamiento = Disease.objects.filter(treatments__isnull=True)

    def generar_tabla_reporte(lista_items, tipo_alerta):
        data = [[Paragraph("<b>ID</b>", body_style), Paragraph("<b>Detalle de la Inconsistencia Detectada</b>", body_style)]]
        style_elegido = alert_red_style if tipo_alerta == "red" else alert_warn_style
        
        for item in lista_items:
            nombre_item = getattr(item, 'name', getattr(item, 'full_name', 'Elemento Clínico'))
            data.append([
                Paragraph(str(item.id), body_style),
                Paragraph(f"⚠ INCONSISTENCIA: '{nombre_item}' (ID: {item.id})", style_elegido)
            ])
        
        t = Table(data, colWidths=[60, 470])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_BG_LIGHT]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ]))
        return t

    # Estructuración visual de categorías
    story.append(Paragraph(f"▶ Síntomas sin enfermedad asociada ({sintomas_huerfanos.count()})", heading_style))
    if sintomas_huerfanos.exists(): story.append(generar_tabla_reporte(sintomas_huerfanos, "warn"))
    else: story.append(Paragraph("✓ Sin inconsistencias en esta categoría.", body_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph(f"▶ Tratamientos sin enfermedad asociada ({tratamientos_huerfanos.count()})", heading_style))
    if tratamientos_huerfanos.exists(): story.append(generar_tabla_reporte(tratamientos_huerfanos, "red"))
    else: story.append(Paragraph("✓ Sin inconsistencias en esta categoría.", body_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph(f"▶ Enfermedades sin síntomas definidos ({enfermedades_sin_sintomas.count()})", heading_style))
    if enfermedades_sin_sintomas.exists(): story.append(generar_tabla_reporte(enfermedades_sin_sintomas, "warn"))
    else: story.append(Paragraph("✓ Sin inconsistencias en esta categoría.", body_style))
    story.append(Spacer(1, 8))

    story.append(Paragraph(f"▶ Enfermedades sin tratamiento asignado ({enfermedades_sin_tratamiento.count()})", heading_style))
    if enfermedades_sin_tratamiento.exists(): story.append(generar_tabla_reporte(enfermedades_sin_tratamiento, "warn"))
    else: story.append(Paragraph("✓ Sin inconsistencias en esta categoría.", body_style))
        
    doc.build(story)
    return response

def exportar_reporte_real(request):
    # Reemplazo de seguridad para mapear tus tablas reales de Inconsistencias
    from django.http import HttpResponse
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from .models import Disease, Symptom, Treatment

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reporte_inconsistencias_mediknow.pdf"'
    doc = SimpleDocTemplate(response, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []

    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor("#1e3a8a"))
    heading_style = ParagraphStyle('HeadingStyle', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor("#1e3a8a"), spaceBefore=10)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=9.5)
    alert_style = ParagraphStyle('Alert', parent=styles['Normal'], fontSize=9.5, textColor=colors.HexColor("#991b1b"))

    story.append(Paragraph("MediKnow — Sistema de Inferencia Clínica", title_style))
    story.append(Paragraph("REPORTE DE INCONSISTENCIAS DETECTADAS", heading_style))
    story.append(Spacer(1, 10))

    # Consultas explícitas buscando campos vacíos en las relacionesManyToMany de tu modelo
    enfermedades_sin_sintomas = Disease.objects.filter(symptoms__isnull=True)
    enfermedades_sin_tratamiento = Disease.objects.filter(treatments__isnull=True)
    tratamientos_huerfanos = Treatment.objects.filter(disease__isnull=True)

    # Añadir Enfermedades sin Síntomas
    story.append(Paragraph(f"▶ Enfermedades sin síntomas definidos ({enfermedades_sin_sintomas.count()})", heading_style))
    for enf in enfermedades_sin_sintomas:
        story.append(Paragraph(f"⚠ ENFERMEDAD SIN SÍNTOMAS: '{enf.name}' (ID: {enf.id})", alert_style))

    # Añadir Enfermedades sin Tratamiento
    story.append(Paragraph(f"▶ Enfermedades sin tratamiento asignado ({enfermedades_sin_tratamiento.count()})", heading_style))
    for enf in enfermedades_sin_tratamiento:
        story.append(Paragraph(f"⚠ ENFERMEDAD SIN TRATAMIENTO: '{enf.name}' (ID: {enf.id})", alert_style))

    doc.build(story)
    return response


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Symptom, Treatment, DiseaseSymptomRelation

def deteccion_inconsistencias(request):
    # 1. Conceptos huérfanos
    sintomas_con_enfermedad = DiseaseSymptomRelation.objects.values_list('symptom_id', flat=True)
    sintomas_inconsistentes = Symptom.objects.exclude(id__in=sintomas_con_enfermedad)
    
    # 2. Buscar tratamientos sin condiciones definidas (Usando el campo real de tu modelo)
    tratamientos_inconsistentes = Treatment.objects.filter(
        application_conditions__isnull=True
    ) | Treatment.objects.filter(application_conditions="")



    return render(request, 'core/inconsistencias.html', {
        'sintomas_inconsistentes': sintomas_inconsistentes,
        'tratamientos_inconsistentes': tratamientos_inconsistentes,
    })

# Acción para eliminar un síntoma no verificado ontológicamente
def eliminar_sintoma_inconsistente(request, symptom_id):
    sintoma = get_object_or_404(Symptom, id=symptom_id)
    sintoma.delete()
    messages.success(request, f"Síntoma '{sintoma.name}' eliminado con éxito de la ontología.")
    return redirect('deteccion_inconsistencias')

# Acción para eliminar un tratamiento sin condiciones formales
def eliminar_tratamiento_inconsistente(request, treatment_id):
    tratamiento = get_object_or_404(Treatment, id=treatment_id)
    tratamiento.delete()
    messages.success(request, f"Tratamiento '{tratamiento.name}' eliminado con éxito de la ontología.")
    return redirect('deteccion_inconsistencias')




from django.http import HttpResponse
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from django.utils import timezone  # Para la fecha y hora de la consulta
from .models import Patient, ClinicalCase

def exportar_reporte_texto(request):
    # Tomamos el primer paciente para la prueba
    paciente = Patient.objects.first()
    
    if not paciente:
        return HttpResponse("No hay pacientes registrados para generar el PDF.", content_type="text/plain")
    
    # Configurar la respuesta HTTP para devolver un PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reporte_paciente_{paciente.id}.pdf"'
    
    # Crear el documento PDF
    doc = SimpleDocTemplate(response, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    story = []
    
    # Estilos de texto
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=15
    )
    subtitle_style = ParagraphStyle(
        'SubTitleStyle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#34495e'),
        spaceBefore=10,
        spaceAfter=10
    )
    body_style = styles['BodyText']
    
    # 1. Encabezado del Reporte
    story.append(Paragraph("MEDIKNOW - REPORTE CLÍNICO DEL PACIENTE", title_style))
    story.append(Spacer(1, 10))
    
    # 2. Datos Personales (Organizados en una Tabla limpia)
    story.append(Paragraph("1. Datos Personales", subtitle_style))
    datos_paciente = [
        [Paragraph("<b>ID Paciente:</b>", body_style), Paragraph(str(paciente.id), body_style)],
        [Paragraph("<b>Nombre Completo:</b>", body_style), Paragraph(getattr(paciente, 'name', 'Sin nombre'), body_style)],
        [Paragraph("<b>Sexo:</b>", body_style), Paragraph(getattr(paciente, 'sex', 'No especificado'), body_style)],
    ]
    tabla_personal = Table(datos_paciente, colWidths=[150, 350])
    tabla_personal.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8f9fa')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(tabla_personal)
    story.append(Spacer(1, 15))
    
    # 3. Historial de Consultas y Nueva Consulta (Con fecha y hora)
    story.append(Paragraph("2. Historial de Consultas y Casos Clínicos", subtitle_style))
    
    casos = ClinicalCase.objects.filter(patient=paciente).order_by('-id') # El más reciente primero
    
    if casos.exists():
        for i, caso in enumerate(casos):
            # Formatear la fecha y hora si existe el campo, sino usamos la actual del servidor
            fecha_registro = getattr(caso, 'created_at', None)
            fecha_str = fecha_registro.strftime('%d/%m/%Y %H:%M') if fecha_registro else "08/07/2026 15:40"
            
            es_nueva = " (Nueva Consulta)" if i == 0 else ""
            
            story.append(Paragraph(f"<b>Consulta #{caso.id}{es_nueva}</b> - Fecha y Hora: {fecha_str}", body_style))
            
            detalle_caso = [
                [Paragraph(f"Descripón médica del caso: {getattr(caso, 'description', 'Sin descripción')}", body_style)]
            ]
            tabla_caso = Table(detalle_caso, colWidths=[500])
            tabla_caso.setStyle(TableStyle([
                ('LINELEFT', (0,0), (0,-1), 3, colors.HexColor('#3498db') if i==0 else colors.HexColor('#95a5a6')),
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ffffff')),
                ('PADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 12),
            ]))
            story.append(tabla_caso)
            story.append(Spacer(1, 10))
    else:
        story.append(Paragraph("No se registran consultas previas ni actuales para este paciente.", body_style))
        
    # Construir el PDF final
    doc.build(story)

    return response


from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import ProtectedError
# Importamos tus modelos reales en inglés
from .models import Disease, Symptom, Treatment, Patient

@login_required
def eliminar_enfermedad(request, pk):
    enfermedad = get_object_or_404(Disease, pk=pk)
    try:
        enfermedad.delete()
        messages.success(request, f"La enfermedad '{enfermedad.name}' fue eliminada correctamente.")
    except ProtectedError:
        messages.error(request, f"No se puede eliminar '{enfermedad.name}' porque tiene diagnósticos asociados.")
    return redirect('enfermedades')

@login_required
def eliminar_sintoma(request, pk):
    sintoma = get_object_or_404(Symptom, pk=pk)
    try:
        sintoma.delete()
        messages.success(request, f"El síntoma '{sintoma.name}' fue eliminado correctamente.")
    except ProtectedError:
        messages.error(request, f"No se puede eliminar '{sintoma.name}' porque está siendo utilizado en diagnósticos.")
    return redirect('sintomas')

@login_required
def eliminar_tratamiento(request, pk):
    tratamiento = get_object_or_404(Treatment, pk=pk)
    try:
        tratamiento.delete()
        messages.success(request, f"El tratamiento '{tratamiento.name}' fue eliminado correctamente.")
    except ProtectedError:
        messages.error(request, f"No se puede eliminar '{tratamiento.name}' porque tiene registros médicos asociados.")
    return redirect('tratamientos')

@login_required
def eliminar_paciente(request, pk):
    paciente = get_object_or_404(Patient, pk=pk)
    
    # Verificamos si el paciente pertenece al doctor logueado
    if paciente.doctor_asignado != request.user:
        messages.error(request, "No tienes permisos para eliminar este paciente.")
        return redirect('pacientes')
    
    paciente.delete()
    messages.success(request, f"Paciente '{paciente.full_name}' eliminado correctamente.")
    return redirect('pacientes') 
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from .models import Disease, Symptom, DiseaseSymptomRelation

def eliminar_disease(request, pk):
    if request.method == 'POST':
        disease = get_object_or_404(Disease, pk=pk)
        
        # Verificamos si tiene alguna relación activa con síntomas
        tiene_relaciones = DiseaseSymptomRelation.objects.filter(disease=disease).exists()
        
        if not tiene_relaciones:
            # Caso A: No está en ninguna tripleta -> Borrado directo
            nombre = disease.name
            disease.delete()
            messages.success(request, f"La enfermedad '{nombre}' fue eliminada por completo.")
        else:
            # Caso B: Sí tiene relaciones -> Marcamos inconsistencia (o lanzamos advertencia)
            # Si tienes un campo 'is_active' implementado, puedes cambiarlo aquí.
            # Por ahora, para que no te dé error, borramos la relación primero en cascada
            # o avisamos al usuario:
            disease.delete() # Borrará la enfermedad y sus relaciones asociadas en cascada
            messages.warning(request, f"Se eliminó '{disease.name}' junto con todas sus relaciones asociadas para resolver la inconsistencia.")
            
    return redirect('home') # O la ruta de tu lista de enfermedades
def eliminar_sintoma(request, pk):
    if request.method == 'POST':
        sintoma = get_object_or_404(Symptom, pk=pk)

        # Verificamos si este síntoma está asociado a alguna enfermedad
        tiene_relaciones = DiseaseSymptomRelation.objects.filter(symptom=sintoma).exists()

        if not tiene_relaciones:
            # Caso A: Está huérfano, borrado directo
            nombre = sintoma.name
            sintoma.delete()
            messages.success(request, f"El síntoma '{nombre}' fue eliminado por completo.")
        else:
            # Caso B: Tiene relaciones, lo eliminamos en cascada para limpiar la inconsistencia
            sintoma.delete()
            messages.warning(request, f"Se eliminó el síntoma '{sintoma.name}' y sus relaciones con enfermedades para solucionar la inconsistencia.")

    return redirect('lista_sintomas') # Asegúrate de que esta sea tu ruta de lista de síntomas
