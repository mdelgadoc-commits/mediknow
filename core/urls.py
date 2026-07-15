from django.urls import path
from . import views

urlpatterns = [
    # Rutas principales del menú y registros
    path('', views.menu, name='menu'),
    path('cuestionario/', views.cuestionario, name='cuestionario'),
    path('sintomas/', views.sintomas, name='sintomas'),
    path('enfermedades/', views.enfermedades, name='enfermedades'),
    path('registro-medico/', views.registro_medico, name='registro_medico'),
    path('registro-paciente/', views.registro_paciente, name='registro_paciente'),

    # Exportador de PDF oficial
    path('exportar-reporte/', views.exportar_reporte, name='exportar_reporte'),

    # Secciones clínicas y consultas
    path('antecedentes/', views.actualizar_antecedentes, name='actualizar_antecedentes'),
    path('tratamientos/', views.tratamientos, name='tratamientos'),
    path('relaciones/', views.relaciones, name='relaciones'),
    path('consultas-avanzadas/', views.consultas_avanzadas, name='consultas_avanzadas'),
    path('pacientes/', views.pacientes, name='pacientes'),
    path('doctores/', views.doctores, name='doctores'),

    # Detección de Inconsistencias
    path('inconsistencias/', views.deteccion_inconsistencias, name='deteccion_inconsistencias'),

    # Eliminación de elementos inconsistentes individuales (Panel de Inconsistencias)
    path('inconsistencias/eliminar-sintoma/<int:symptom_id>/', views.eliminar_sintoma_inconsistente, name='eliminar_sintoma_inconsistente'),
    path('inconsistencias/eliminar-treatment/<int:treatment_id>/', views.eliminar_tratamiento_inconsistente, name='eliminar_tratamiento_inconsistente'),

    # Rutas definitivas y seguras de eliminación (¡Con los botones de tachito!)
    path('enfermedad/eliminar/<int:pk>/', views.eliminar_disease, name='eliminar_disease'),
    path('sintoma/eliminar/<int:pk>/', views.eliminar_sintoma, name='eliminar_sintoma'),
    path('tratamiento/eliminar/<int:pk>/', views.eliminar_tratamiento, name='eliminar_tratamiento'),
    path('paciente/eliminar/<int:pk>/', views.eliminar_paciente, name='eliminar_paciente'),
    path('reportes/exportar/pdf/', views.exportar_reporte_real, name='exportar_reporte_real'),

    # Reporte 1: Inconsistencias de la base de conocimiento
    path('reportes/exportar/pdf/', views.exportar_reporte_real, name='exportar_reporte_real'),

    # Reporte 2: Historial clínico detallado de un paciente individual
    path('paciente/<int:paciente_id>/historial/pdf/', views.exportar_historial_paciente, name='exportar_historial_paciente'),

]
