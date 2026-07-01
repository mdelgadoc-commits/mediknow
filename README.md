# MediKnow

Sistema de apoyo al diagnóstico médico basado en una ontología de enfermedades, síntomas y tratamientos, con un motor de inferencia por puntaje ponderado.

## ¿Qué hace?

El médico registra pacientes, marca los síntomas presentes y ajusta su intensidad (1–10). El sistema calcula un diagnóstico diferencial ponderado, sugiere tratamientos y alerta sobre posibles conflictos con las alergias del paciente.

## Stack

- **Backend:** Django 6.0 (Python 3.12)
- **Base de datos:** SQLite (desarrollo)
- **Frontend:** HTML + CSS + JS vanilla (sin frameworks)

## Modelo de datos

- `MedicalCategory`, `Disease`, `Symptom`, `Treatment` — entidades base de la ontología.
- `DiseaseSymptomRelation`, `DiseaseTreatmentRelation` — tripletas `(Enfermedad, Síntoma/Tratamiento, Peso)` que forman el grafo de conocimiento.
- `Patient`, `Allergy`, `ClinicalCase`, `DiagnosisResult` — datos clínicos y trazabilidad de cada consulta.

## Motor de inferencia

`core/inference_engine.py` calcula, para cada enfermedad:

```
score = Σ (peso_asociación × intensidad_reportada)
score_normalizado = (score / score_máximo_posible) × 100
```

Los resultados se ordenan por score y se filtran por un umbral mínimo para evitar ruido.

## Instalación

```bash
git clone https://github.com/mdelgadoc-commits/mediknow.git
cd mediknow
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt   # o: pip install django
python3 manage.py migrate
python3 manage.py createsuperuser
python3 manage.py seed             # carga la ontología médica (Urología, Oftalmología, ORL)
python3 manage.py runserver
```

Luego entra a `http://127.0.0.1:8000/` e inicia sesión con el superusuario creado.

## Comandos útiles

| Comando | Descripción |
|---|---|
| `python3 manage.py seed` | Carga/actualiza enfermedades, síntomas y tratamientos (idempotente). |
| `python3 manage.py shell < seed_allergies.py` | Carga el catálogo de alergias comunes. |
| Vista `/reportes/` | Muestra inconsistencias en la ontología (síntomas huérfanos, enfermedades sin tratamiento, etc.). |

## Estado actual

Ontología cargada: **Urología**, **Oftalmología** y **ORL** (9 enfermedades). Pendiente ampliar a otras categorías médicas.

## Aviso

Herramienta de apoyo académico/clínico. No sustituye el juicio clínico profesional ni constituye asesoría médica.
