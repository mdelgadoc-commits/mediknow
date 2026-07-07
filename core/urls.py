from django.urls import path
from . import views

urlpatterns = [
    path('', views.menu, name='menu'),
    path('sintomas/', views.cuestionario, name='cuestionario'),
    path('enfermedades/', views.enfermedades, name='enfermedades'),
    path('registro-medico/', views.registro_medico, name='registro_medico'),
    path('registro-paciente/', views.registro_paciente, name='registro_paciente'),
    path('exportar-reporte/', views.exportar_reporte, name='exportar_reporte'),
    path('reportes/', views.reportes, name='reportes'),
    path('antecedentes/', views.actualizar_antecedentes, name='actualizar_antecedentes'),
    path('sintomas-registro/', views.sintomas, name='sintomas'),
    path('tratamientos/', views.tratamientos, name='tratamientos'),
    path('relaciones/', views.relaciones, name='relaciones'),
    path('consultas-avanzadas/', views.consultas_avanzadas, name='consultas_avanzadas'),
]
