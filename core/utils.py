import os
from django.conf import settings
from owlready2 import get_ontology, sync_reasoner_hermit

def inferir_categoria_sintoma(symptom_name):
    """
    Busca un síntoma en la ontología OWL y deduce su categoría médica.
    """
    try:
        # 1. Ruta de tu ontología (ajústala a donde esté tu archivo .owl)
        # Ejemplo: guardada en una carpeta 'ontologias' dentro de tu app core
        onto_path = os.path.join(settings.BASE_DIR, 'core', 'ontologias', 'mediknow.owl')
        
        if not os.path.exists(onto_path):
            return "Sin Clasificar (Archivo OWL no encontrado)"
            
        onto = get_ontology(onto_path).load()
        
        # 2. Normalizar el nombre para buscar el individuo (ej: "Dolor de cabeza" -> "dolor_de_cabeza")
        individuo_iri = symptom_name.lower().strip().replace(" ", "_")
        
        # 3. Buscar el individuo en la ontología
        individuo = onto.search_one(iri=f"*{individuo_iri}")
        
        if individuo:
            # Ejecutar el razonador lógico HermiT para inferir jerarquías complejas
            with onto:
                sync_reasoner_hermit()
            
            # Obtener todas las clases a las que pertenece el individuo
            clases = individuo.is_a
            
            for clase in clases:
                nombre_clase = clase.name
                # Descartamos clases genéricas de la ontología
                if nombre_clase not in ["Symptom", "Sintoma", "Thing", "OwlreadyActiveConcept"]:
                    # Formateamos el nombre de la clase para que sea legible en el frontend
                    # Ej: "SintomaNeurologico" -> "Síntoma Neurologico"
                    return nombre_clase.replace("Sintoma", "Síntoma ").replace("Symptom", "Síntoma ")
                    
        return "General / No clasificado en Ontología"
        
    except Exception as e:
        # En caso de error de carga o del razonador, devolvemos un fallback seguro para que la web no se caiga
        return "Categoría Clínica"
