"""
Comando de gestion de Django para poblar la ontologia medica de MediKnow.

Uso:
    python3 manage.py seed

Fuentes: MedlinePlus (Biblioteca Nacional de Medicina de EE.UU.), Mayo Clinic,
Manual MSD, CDC, y guias clinicas de consenso (criterios de Centor para
faringoamigdalitis, guias de HPB, litiasis renal, glaucoma agudo, etc).

Este script es IDEMPOTENTE: se puede ejecutar varias veces sin duplicar datos,
gracias a get_or_create().
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    MedicalCategory,
    Disease,
    Symptom,
    Treatment,
    DiseaseSymptomRelation,
    DiseaseTreatmentRelation,
)


# ─────────────────────────────────────────────────────────────
# 1. CATEGORIAS MEDICAS
# ─────────────────────────────────────────────────────────────
CATEGORIES = [
    ("Urologia", "Enfermedades del aparato urinario y del sistema reproductor masculino."),
    ("Oftalmologia", "Enfermedades y trastornos del ojo y la vision."),
    ("Otorrinolaringologia (ORL)", "Enfermedades del oido, la nariz y la garganta."),
]


# ─────────────────────────────────────────────────────────────
# 2. SINTOMAS
# Formato: nombre -> (descripcion, relevancia_base 1|3)
# La relevancia base es un valor por defecto; el peso real en el
# calculo diagnostico lo define DiseaseSymptomRelation.association_weight
# de forma independiente por cada enfermedad.
# ─────────────────────────────────────────────────────────────
SYMPTOMS = {
    # --- Urologia ---
    "Disuria (dolor o ardor al orinar)": ("Dolor o sensacion de ardor al orinar.", 3),
    "Polaquiuria (orinar con mucha frecuencia)": ("Necesidad de orinar con mayor frecuencia de lo habitual.", 3),
    "Tenesmo vesical (urgencia urinaria)": ("Sensacion urgente e imperiosa de orinar.", 1),
    "Dolor suprapubico": ("Dolor en la parte baja del abdomen, sobre la vejiga.", 1),
    "Orina turbia o maloliente": ("Cambios en el aspecto u olor de la orina.", 1),
    "Hematuria (sangre en la orina)": ("Presencia de sangre visible o microscopica en la orina.", 3),
    "Fiebre": ("Elevacion de la temperatura corporal por encima de lo normal.", 1),
    "Dolor lumbar intenso irradiado a ingle (colico nefritico)": (
        "Dolor subito e intenso en la espalda o el costado que se irradia hacia el abdomen o los genitales.", 3,
    ),
    "Nauseas y vomitos": ("Sensacion de malestar estomacal con o sin expulsion del contenido gastrico.", 1),
    "Sudoracion": ("Sudoracion excesiva asociada al dolor o malestar.", 1),
    "Chorro urinario debil": ("Disminucion en la fuerza del flujo de orina.", 3),
    "Dificultad para iniciar la miccion": ("Esfuerzo o retraso al comenzar a orinar.", 3),
    "Nicturia (orinar de noche)": ("Necesidad de levantarse a orinar durante la noche.", 1),
    "Sensacion de vaciamiento incompleto": ("Sensacion de que la vejiga no se vacio por completo tras orinar.", 1),
    "Goteo terminal": ("Goteo de orina al finalizar la miccion.", 1),
    "Retencion urinaria aguda": ("Incapacidad subita para orinar. Es una emergencia medica.", 3),

    # --- Oftalmologia ---
    "Enrojecimiento ocular": ("Ojo de color rojo o rosado por dilatacion de vasos sanguineos.", 3),
    "Secrecion ocular purulenta o mucosa": ("Secrecion amarillenta, verdosa o blanquecina del ojo.", 3),
    "Picazon ocular": ("Sensacion de comezon en el ojo.", 1),
    "Lagrimeo excesivo": ("Produccion de lagrimas mayor a lo habitual.", 1),
    "Sensacion de cuerpo extrano en el ojo": ("Sensacion de arena o algo alojado en el ojo.", 1),
    "Costras en las pestanas al despertar": ("Formacion de costras que pegan los parpados al despertar.", 1),
    "Fotofobia (sensibilidad a la luz)": ("Molestia o dolor ocular al exponerse a la luz.", 1),
    "Dolor ocular intenso": ("Dolor severo en el ojo o alrededor de este.", 3),
    "Vision borrosa subita": ("Perdida repentina de nitidez visual.", 3),
    "Halos de colores alrededor de las luces": ("Percepcion de anillos o halos coloreados alrededor de fuentes de luz.", 3),
    "Dolor de cabeza": ("Cefalea o dolor en la region craneal.", 1),
    "Bulto rojo y doloroso en el parpado": ("Protuberancia inflamada y sensible en el borde del parpado.", 3),
    "Sensibilidad al tacto en el parpado": ("Dolor al tocar o presionar el parpado afectado.", 1),
    "Hinchazon del parpado": ("Inflamacion visible del parpado.", 1),

    # --- ORL ---
    "Exudado amigdalar (placas blanquecinas)": ("Placas o pus visible sobre las amigdalas.", 3),
    "Adenopatia cervical dolorosa": ("Ganglios inflamados y dolorosos en el cuello.", 3),
    "Fiebre alta": ("Temperatura corporal elevada, tipicamente mayor a 38 grados.", 3),
    "Ausencia de tos": ("No presenta tos; su ausencia orienta a causa bacteriana en el contexto de dolor de garganta.", 1),
    "Odinofagia (dolor al tragar)": ("Dolor al deglutir alimentos o saliva.", 1),
    "Cefalea": ("Dolor de cabeza asociado al cuadro infeccioso.", 1),
    "Otalgia (dolor de oido)": ("Dolor localizado en el oido.", 3),
    "Otorrea (secrecion del oido)": ("Salida de liquido o pus del oido, puede indicar perforacion timpanica.", 3),
    "Irritabilidad o llanto en ninos": ("Cambios de comportamiento como irritabilidad o llanto inconsolable.", 1),
    "Hipoacusia (perdida auditiva)": ("Disminucion de la capacidad auditiva.", 1),
    "Rechazo de la alimentacion": ("El paciente (frecuentemente un nino) rechaza comer o beber.", 1),
    "Congestion nasal": ("Obstruccion o taponamiento de las fosas nasales.", 1),
    "Dolor facial": ("Dolor localizado en la cara, tipicamente sobre los senos paranasales.", 3),
    "Secrecion nasal purulenta": ("Secrecion nasal espesa, amarillenta o verdosa.", 3),
    "Tos": ("Tos asociada al cuadro respiratorio.", 1),
    "Perdida del olfato": ("Disminucion o perdida de la capacidad de percibir olores.", 1),
}


# ─────────────────────────────────────────────────────────────
# 3. TRATAMIENTOS
# Formato: nombre -> (tipo, condiciones_de_aplicacion)
# tipo debe coincidir con Treatment.TreatmentType: FARM, QUIR, FISI, DIET, DERI, OTRO
# ─────────────────────────────────────────────────────────────
TREATMENTS = {
    # --- Urologia ---
    "Nitrofurantoina o fosfomicina": ("FARM", "Antibiotico de primera linea para cistitis no complicada."),
    "Trimetoprim-sulfametoxazol": ("FARM", "Alternativa antibiotica segun resistencia local y alergias."),
    "Fenazopiridina (alivio sintomatico)": ("FARM", "Analgesico urinario para aliviar disuria mientras actua el antibiotico."),
    "Analgesicos AINE para colico renal": ("FARM", "Primera linea para el dolor del colico nefritico."),
    "Alfabloqueante (tamsulosina) para expulsion de calculo": ("FARM", "Facilita la expulsion espontanea de calculos ureterales pequenos."),
    "Litotricia por ondas de choque": ("QUIR", "Para calculos que no se expulsan espontaneamente."),
    "Derivacion urologica urgente": ("DERI", "Ante obstruccion persistente, fiebre o deterioro de la funcion renal."),
    "Alfabloqueante para HPB (tamsulosina)": ("FARM", "Relaja el musculo prostatico para mejorar el flujo urinario."),
    "Inhibidor de 5-alfa reductasa (finasteride)": ("FARM", "Reduce el tamano de la prostata a largo plazo."),
    "Cirugia o procedimiento minimamente invasivo prostatico": ("QUIR", "Indicado en retencion urinaria recurrente o sintomas severos refractarios."),

    # --- Oftalmologia ---
    "Compresas frias o tibias": ("FISI", "Medida general para aliviar molestia ocular segun el tipo de conjuntivitis."),
    "Antibiotico topico oftalmico": ("FARM", "Gotas o ungueento antibiotico para conjuntivitis bacteriana."),
    "Antihistaminico topico oftalmico": ("FARM", "Gotas antihistaminicas para conjuntivitis alergica."),
    "Derivacion oftalmologica urgente": ("DERI", "Emergencia medica: requiere evaluacion inmediata para prevenir perdida de vision."),
    "Gotas hipotensoras oculares": ("FARM", "Reducen la presion intraocular de forma aguda."),
    "Iridotomia periferica con laser": ("QUIR", "Procedimiento definitivo para el glaucoma de angulo cerrado."),
    "Ungueento antibiotico para parpado": ("FARM", "Se aplica sobre el borde palpebral si el orzuelo no mejora."),

    # --- ORL ---
    "Penicilina V oral": ("FARM", "Tratamiento de primera linea para faringoamigdalitis estreptococica confirmada o de alta sospecha."),
    "Amoxicilina": ("FARM", "Alternativa a penicilina; tambien primera linea en otitis media y sinusitis bacteriana."),
    "Analgesicos y antitermicos": ("FARM", "Paracetamol o ibuprofeno para el dolor y la fiebre."),
    "Observacion clinica 48-72 horas": ("OTRO", "Manejo expectante antes de iniciar antibiotico en cuadros leves."),
    "Lavados nasales con solucion salina": ("OTRO", "Medida sintomatica para congestion nasal y sinusitis."),
}


# ─────────────────────────────────────────────────────────────
# 4. ENFERMEDADES
# Formato:
#   nombre: {
#       "categoria": "...",
#       "descripcion": "...",
#       "criterios_clinicos": "...",
#       "sintomas": [(nombre_sintoma, peso 1|3, notas), ...],
#       "tratamientos": [(nombre_tratamiento, condiciones, prioridad), ...],
#   }
# ─────────────────────────────────────────────────────────────
DISEASES = {
    "Cistitis aguda (infeccion urinaria baja)": {
        "categoria": "Urologia",
        "descripcion": (
            "Infeccion de la vejiga o vias urinarias inferiores, causada con mayor "
            "frecuencia por Escherichia coli. Mas comun en mujeres."
        ),
        "criterios_clinicos": (
            "Diagnostico clinico + analisis de orina (nitritos, leucocitos). "
            "Sospechar pielonefritis si hay fiebre alta, dolor lumbar o afectacion "
            "del estado general: en ese caso derivar de forma urgente."
        ),
        "sintomas": [
            ("Disuria (dolor o ardor al orinar)", 3, "Sintoma cardinal de cistitis."),
            ("Polaquiuria (orinar con mucha frecuencia)", 3, "Muy frecuente en cistitis aguda."),
            ("Tenesmo vesical (urgencia urinaria)", 1, "Frecuente, menos especifico."),
            ("Dolor suprapubico", 1, "Puede acompanar al cuadro."),
            ("Orina turbia o maloliente", 1, "Signo de apoyo diagnostico."),
            ("Hematuria (sangre en la orina)", 1, "Puede presentarse en cistitis hemorragica."),
            ("Fiebre", 1, "Su presencia marcada sugiere progresion a pielonefritis."),
        ],
        "tratamientos": [
            ("Nitrofurantoina o fosfomicina", "Cistitis no complicada en mujeres sin comorbilidades.", 1),
            ("Trimetoprim-sulfametoxazol", "Alternativa segun resistencia local.", 2),
            ("Fenazopiridina (alivio sintomatico)", "Uso complementario por maximo 2 dias.", 3),
        ],
    },
    "Litiasis renal (calculos renales)": {
        "categoria": "Urologia",
        "descripcion": (
            "Formacion de calculos solidos en el rinon o las vias urinarias a partir "
            "de sustancias cristalizadas en la orina, mas frecuentes en personas "
            "con baja ingesta de liquidos."
        ),
        "criterios_clinicos": (
            "El cuadro clasico es el colico nefritico: dolor subito e intenso, "
            "intermitente, con nauseas y sudoracion. Confirmar con ecografia o TC "
            "sin contraste. Derivar si hay fiebre, obstruccion completa o dolor "
            "no controlado."
        ),
        "sintomas": [
            ("Dolor lumbar intenso irradiado a ingle (colico nefritico)", 3, "Sintoma mas caracteristico."),
            ("Hematuria (sangre en la orina)", 3, "Muy frecuente por lesion de la via urinaria."),
            ("Nauseas y vomitos", 1, "Acompanan al dolor por reflejo visceral."),
            ("Sudoracion", 1, "Asociada a la intensidad del dolor."),
            ("Dolor suprapubico", 1, "Puede presentarse cuando el calculo desciende."),
            ("Polaquiuria (orinar con mucha frecuencia)", 1, "Si el calculo esta cerca de la vejiga."),
            ("Fiebre", 1, "Su presencia sugiere infeccion asociada; requiere atencion urgente."),
        ],
        "tratamientos": [
            ("Analgesicos AINE para colico renal", "Primera linea salvo contraindicacion.", 1),
            ("Alfabloqueante (tamsulosina) para expulsion de calculo", "Calculos ureterales menores de 10mm.", 2),
            ("Litotricia por ondas de choque", "Si el calculo no se expulsa espontaneamente.", 3),
            ("Derivacion urologica urgente", "Fiebre, obstruccion persistente o deterioro renal.", 4),
        ],
    },
    "Hiperplasia prostatica benigna (HPB)": {
        "categoria": "Urologia",
        "descripcion": (
            "Crecimiento no maligno de la glandula prostatica que obstruye "
            "progresivamente el flujo urinario, comun en hombres mayores de 50 anos."
        ),
        "criterios_clinicos": (
            "Diagnostico clinico apoyado en tacto rectal y, si procede, ecografia "
            "prostatica. La retencion urinaria aguda es una emergencia medica."
        ),
        "sintomas": [
            ("Chorro urinario debil", 3, "Sintoma obstructivo tipico."),
            ("Dificultad para iniciar la miccion", 3, "Sintoma obstructivo tipico."),
            ("Nicturia (orinar de noche)", 1, "Muy frecuente, afecta la calidad de vida."),
            ("Sensacion de vaciamiento incompleto", 1, "Sintoma irritativo/obstructivo comun."),
            ("Goteo terminal", 1, "Frecuente en HPB."),
            ("Retencion urinaria aguda", 3, "Complicacion grave; requiere atencion inmediata."),
        ],
        "tratamientos": [
            ("Alfabloqueante para HPB (tamsulosina)", "Primera linea para alivio sintomatico rapido.", 1),
            ("Inhibidor de 5-alfa reductasa (finasteride)", "Reduccion de tamano prostatico a largo plazo.", 2),
            ("Cirugia o procedimiento minimamente invasivo prostatico", "Retencion recurrente o sintomas refractarios.", 3),
        ],
    },
    "Conjuntivitis": {
        "categoria": "Oftalmologia",
        "descripcion": (
            "Inflamacion o infeccion de la conjuntiva, la membrana que recubre el "
            "parpado y la superficie del ojo. Puede ser viral, bacteriana o alergica."
        ),
        "criterios_clinicos": (
            "Diagnostico clinico. Derivar si hay dolor ocular intenso, disminucion "
            "de la vision, fotofobia marcada o falta de mejoria en 3-4 dias."
        ),
        "sintomas": [
            ("Enrojecimiento ocular", 3, "Signo cardinal de conjuntivitis."),
            ("Secrecion ocular purulenta o mucosa", 3, "Orienta a etiologia bacteriana si es amarillo-verdosa."),
            ("Picazon ocular", 1, "Muy caracteristica de la conjuntivitis alergica."),
            ("Lagrimeo excesivo", 1, "Comun en conjuntivitis viral y alergica."),
            ("Sensacion de cuerpo extrano en el ojo", 1, "Sintoma acompanante frecuente."),
            ("Costras en las pestanas al despertar", 1, "Tipico de conjuntivitis bacteriana."),
            ("Fotofobia (sensibilidad a la luz)", 1, "Si es intensa, sugiere descartar otras causas."),
        ],
        "tratamientos": [
            ("Compresas frias o tibias", "Medida general de alivio segun el tipo de conjuntivitis.", 1),
            ("Antibiotico topico oftalmico", "Conjuntivitis bacteriana confirmada o de alta sospecha.", 2),
            ("Antihistaminico topico oftalmico", "Conjuntivitis alergica.", 3),
        ],
    },
    "Glaucoma agudo de angulo cerrado": {
        "categoria": "Oftalmologia",
        "descripcion": (
            "Aumento subito y peligroso de la presion intraocular por bloqueo del "
            "drenaje del humor acuoso. Es una emergencia oftalmologica."
        ),
        "criterios_clinicos": (
            "EMERGENCIA MEDICA. Sin tratamiento puede causar ceguera en pocos dias. "
            "Requiere derivacion inmediata a oftalmologia o servicio de urgencias."
        ),
        "sintomas": [
            ("Dolor ocular intenso", 3, "Sintoma dominante y de alarma."),
            ("Vision borrosa subita", 3, "Aparece junto con el aumento de presion."),
            ("Halos de colores alrededor de las luces", 3, "Muy caracteristico del cuadro agudo."),
            ("Nauseas y vomitos", 1, "Frecuentes por el dolor intenso."),
            ("Enrojecimiento ocular", 1, "Acompana al cuadro agudo."),
            ("Dolor de cabeza", 1, "Puede ser unilateral, del lado del ojo afectado."),
        ],
        "tratamientos": [
            ("Derivacion oftalmologica urgente", "Obligatoria e inmediata ante sospecha de glaucoma agudo.", 1),
            ("Gotas hipotensoras oculares", "Reduccion inicial de la presion mientras se deriva al paciente.", 2),
            ("Iridotomia periferica con laser", "Tratamiento definitivo realizado por el especialista.", 3),
        ],
    },
    "Orzuelo": {
        "categoria": "Oftalmologia",
        "descripcion": (
            "Infeccion aguda de una glandula sebacea del parpado, generalmente por "
            "Staphylococcus aureus. Se presenta como un bulto rojo y doloroso."
        ),
        "criterios_clinicos": (
            "Diagnostico clinico por observacion directa. Derivar si no mejora en "
            "48-72 horas, hay fiebre o la hinchazon se extiende mas alla del parpado."
        ),
        "sintomas": [
            ("Bulto rojo y doloroso en el parpado", 3, "Signo cardinal del orzuelo."),
            ("Sensibilidad al tacto en el parpado", 1, "Frecuente al presionar la zona."),
            ("Sensacion de cuerpo extrano en el ojo", 1, "Sintoma acompanante comun."),
            ("Lagrimeo excesivo", 1, "Puede presentarse por la irritacion local."),
            ("Hinchazon del parpado", 1, "Inflamacion localizada del area afectada."),
        ],
        "tratamientos": [
            ("Compresas frias o tibias", "Compresas tibias 4 veces al dia; primera linea de tratamiento.", 1),
            ("Ungueento antibiotico para parpado", "Si no mejora con medidas generales o hay signos de extension.", 2),
        ],
    },
    "Faringoamigdalitis estreptococica": {
        "categoria": "Otorrinolaringologia (ORL)",
        "descripcion": (
            "Infeccion aguda de la faringe y las amigdalas causada por Streptococcus "
            "pyogenes (estreptococo beta-hemolitico del grupo A)."
        ),
        "criterios_clinicos": (
            "Criterios de Centor: exudado amigdalar, adenopatia cervical dolorosa, "
            "fiebre y ausencia de tos. A mayor numero de criterios presentes, mayor "
            "probabilidad de origen estreptococico; se recomienda test rapido de "
            "antigeno o cultivo antes de iniciar antibiotico cuando sea posible."
        ),
        "sintomas": [
            ("Exudado amigdalar (placas blanquecinas)", 3, "Criterio de Centor."),
            ("Adenopatia cervical dolorosa", 3, "Criterio de Centor."),
            ("Fiebre alta", 3, "Criterio de Centor."),
            ("Ausencia de tos", 1, "Criterio de Centor; su ausencia favorece origen bacteriano."),
            ("Odinofagia (dolor al tragar)", 1, "Sintoma muy comun pero poco especifico."),
            ("Cefalea", 1, "Sintoma acompanante frecuente."),
            ("Nauseas y vomitos", 1, "Mas frecuente en ninos."),
        ],
        "tratamientos": [
            ("Penicilina V oral", "Tratamiento de primera linea si se confirma o hay alta sospecha.", 1),
            ("Amoxicilina", "Alternativa razonable, especialmente en ninos.", 2),
            ("Analgesicos y antitermicos", "Manejo sintomatico del dolor y la fiebre.", 3),
        ],
    },
    "Otitis media aguda": {
        "categoria": "Otorrinolaringologia (ORL)",
        "descripcion": (
            "Infeccion bacteriana o viral del oido medio, frecuentemente posterior "
            "a un resfriado. Es mas comun entre los 6 y 24 meses de edad."
        ),
        "criterios_clinicos": (
            "Diagnostico por otoscopia (timpano abombado y eritematoso). En "
            "cuadros leves sin factores de riesgo se puede optar por observacion "
            "48-72 horas antes de iniciar antibiotico."
        ),
        "sintomas": [
            ("Otalgia (dolor de oido)", 3, "Sintoma principal en ninos mayores y adultos."),
            ("Otorrea (secrecion del oido)", 3, "Puede indicar perforacion timpanica."),
            ("Fiebre", 1, "Frecuente, especialmente en ninos pequenos."),
            ("Irritabilidad o llanto en ninos", 1, "En lactantes puede ser el unico signo."),
            ("Hipoacusia (perdida auditiva)", 1, "Comun mientras dura la infeccion."),
            ("Rechazo de la alimentacion", 1, "Frecuente en lactantes."),
        ],
        "tratamientos": [
            ("Analgesicos y antitermicos", "Manejo sintomatico inicial en todos los casos.", 1),
            ("Observacion clinica 48-72 horas", "Casos leves sin factores de riesgo.", 2),
            ("Amoxicilina", "Si hay indicacion de antibiotico segun edad y gravedad.", 3),
        ],
    },
    "Sinusitis aguda": {
        "categoria": "Otorrinolaringologia (ORL)",
        "descripcion": (
            "Inflamacion de los senos paranasales, generalmente secundaria a una "
            "infeccion respiratoria alta viral que se complica o se prolonga."
        ),
        "criterios_clinicos": (
            "Diagnostico clinico basado en sintomas catarrales mas prolongados o "
            "severos de lo habitual (mas de 10 dias) o empeoramiento tras mejoria inicial."
        ),
        "sintomas": [
            ("Dolor facial", 3, "Sintoma caracteristico sobre los senos afectados."),
            ("Secrecion nasal purulenta", 3, "Signo de apoyo diagnostico importante."),
            ("Congestion nasal", 1, "Muy frecuente pero poco especifica."),
            ("Cefalea", 1, "Sintoma acompanante comun."),
            ("Fiebre", 1, "Puede o no estar presente."),
            ("Tos", 1, "Especialmente por goteo posnasal."),
            ("Perdida del olfato", 1, "Puede presentarse en cuadros mas prolongados."),
        ],
        "tratamientos": [
            ("Lavados nasales con solucion salina", "Medida sintomatica de primera linea.", 1),
            ("Analgesicos y antitermicos", "Manejo del dolor facial y la fiebre.", 2),
            ("Amoxicilina", "Si el cuadro es bacteriano: mas de 10 dias o empeoramiento tras mejoria inicial.", 3),
        ],
    },
}


class Command(BaseCommand):
    help = "Puebla la ontologia medica (categorias, enfermedades, sintomas, tratamientos y sus relaciones)."

    @transaction.atomic
    def handle(self, *args, **options):
        # 1. Categorias
        categories_map = {}
        created_categories = 0
        for name, description in CATEGORIES:
            obj, created = MedicalCategory.objects.get_or_create(
                name=name, defaults={"description": description}
            )
            categories_map[name] = obj
            created_categories += created

        # 2. Sintomas
        symptoms_map = {}
        created_symptoms = 0
        for name, (description, relevance) in SYMPTOMS.items():
            obj, created = Symptom.objects.get_or_create(
                name=name, defaults={"description": description, "relevance_level": relevance}
            )
            symptoms_map[name] = obj
            created_symptoms += created

        # 3. Tratamientos
        treatments_map = {}
        created_treatments = 0
        for name, (ttype, conditions) in TREATMENTS.items():
            obj, created = Treatment.objects.get_or_create(
                name=name,
                defaults={"treatment_type": ttype, "application_conditions": conditions},
            )
            treatments_map[name] = obj
            created_treatments += created

        # 4. Enfermedades + relaciones
        created_diseases = 0
        created_symptom_relations = 0
        created_treatment_relations = 0

        for disease_name, data in DISEASES.items():
            disease_obj, created = Disease.objects.get_or_create(
                name=disease_name,
                defaults={
                    "description": data["descripcion"],
                    "category": categories_map[data["categoria"]],
                    "clinical_criteria": data["criterios_clinicos"],
                },
            )
            created_diseases += created

            for symptom_name, weight, notes in data["sintomas"]:
                _, rel_created = DiseaseSymptomRelation.objects.get_or_create(
                    disease=disease_obj,
                    symptom=symptoms_map[symptom_name],
                    defaults={"association_weight": weight, "notes": notes},
                )
                created_symptom_relations += rel_created

            for treatment_name, conditions, priority in data["tratamientos"]:
                _, rel_created = DiseaseTreatmentRelation.objects.get_or_create(
                    disease=disease_obj,
                    treatment=treatments_map[treatment_name],
                    defaults={"formal_conditions": conditions, "priority": priority},
                )
                created_treatment_relations += rel_created

        self.stdout.write(self.style.SUCCESS("Ontologia medica cargada correctamente."))
        self.stdout.write(f"  Categorias nuevas creadas   : {created_categories} (total: {MedicalCategory.objects.count()})")
        self.stdout.write(f"  Sintomas nuevos creados     : {created_symptoms} (total: {Symptom.objects.count()})")
        self.stdout.write(f"  Tratamientos nuevos creados : {created_treatments} (total: {Treatment.objects.count()})")
        self.stdout.write(f"  Enfermedades nuevas creadas : {created_diseases} (total: {Disease.objects.count()})")
        self.stdout.write(f"  Relaciones sintoma nuevas   : {created_symptom_relations} (total: {DiseaseSymptomRelation.objects.count()})")
        self.stdout.write(f"  Relaciones tratamiento nuevas: {created_treatment_relations} (total: {DiseaseTreatmentRelation.objects.count()})")
