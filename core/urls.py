from django.urls import path
from . import views

urlpatterns = [
    path('', views.menu, name='menu'),
    path('cuestionario/', views.cuestionario, name='cuestionario'),
    path('sintomas/', views.sintomas, name='sintomas'),
    path('enfermedades/', views.enfermedades, name='enfermedades'),
    path('registro-medico/', views.registro_medico, name='registro_medico'),
    path('registro-paciente/', views.registro_paciente, name='registro_paciente'),
    path('exportar-reporte/', views.exportar_reporte, name='exportar_reporte'), 
    path('antecedentes/', views.actualizar_antecedentes, name='actualizar_antecedentes'),
    path('tratamientos/', views.tratamientos, name='tratamientos'),
    path('relaciones/', views.relaciones, name='relaciones'),
    path('consultas-avanzadas/', views.consultas_avanzadas, name='consultas_avanzadas'),
    path('pacientes/', views.pacientes, name='pacientes'),
    path('doctores/', views.doctores, name='doctores'),

    path('inconsistencias/', views.deteccion_inconsistencias, name='deteccion_inconsistencias'),


    path('reporte/exportar/', views.exportar_reporte_texto, name='exportar_reporte'),


    path('inconsistencias/eliminar-sintoma/<int:symptom_id>/', views.eliminar_sintoma_inconsistente, name='eliminar_sintoma_inconsistente'),
    path('inconsistencias/eliminar-tratamiento/<int:treatment_id>/', views.eliminar_tratamiento_inconsistente, name='eliminar_tratamiento_inconsistente'),
]
