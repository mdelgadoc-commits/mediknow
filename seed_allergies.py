from core.models import Allergy

ALLERGIES = [
    ("Penicilina y derivados (amoxicilina, ampicilina…)", "Antibióticos", "Reacción alérgica al grupo betalactámico. Puede causar anafilaxia."),
    ("Cefalosporinas", "Antibióticos", "Reactividad cruzada posible con penicilinas (~10%)."),
    ("Sulfonamidas (Trimetoprim-Sulfametoxazol)", "Antibióticos", "Incluye el TMP-SMX. Frecuente en pacientes con VIH."),
    ("Macrólidos (azitromicina, eritromicina)", "Antibióticos", "Menos frecuente. Puede causar reacciones cutáneas."),
    ("Quinolonas (ciprofloxacino, levofloxacino)", "Antibióticos", "Puede causar reacciones cutáneas y fototoxicidad."),
    ("AINEs (ibuprofeno, naproxeno, diclofenaco)", "AINEs / Analgésicos", "Puede desencadenar urticaria, angioedema o asma."),
    ("Ácido acetilsalicílico (Aspirina)", "AINEs / Analgésicos", "Síndrome de Samter: tríada asma + pólipos nasales."),
    ("Paracetamol / Acetaminofén", "AINEs / Analgésicos", "Rara, pero posible en hipersensibilidad a AINEs."),
    ("Metamizol (Dipirona)", "AINEs / Analgésicos", "Puede causar agranulocitosis y reacciones alérgicas."),
    ("Opioides (morfina, codeína, tramadol)", "AINEs / Analgésicos", "La codeína libera histamina directamente."),
    ("Anestésicos locales tipo amida (lidocaína, bupivacaína)", "Anestésicos", "La alergia verdadera es extremadamente rara."),
    ("Látex", "Anestésicos / Material quirúrgico", "Importante en procedimientos quirúrgicos y odontológicos."),
    ("Medios de contraste yodados", "Radiología", "Reacción anafilactoide."),
    ("Corticoides (prednisona, dexametasona)", "Corticoides", "Poco frecuente."),
    ("Mariscos y moluscos", "Alimentos", "Relevante antes de medios de contraste yodados."),
    ("Huevo", "Alimentos", "Relevante para ciertas vacunas."),
]

count = 0
for name, category, description in ALLERGIES:
    obj, created = Allergy.objects.get_or_create(
        name=name,
        defaults={"category": category, "description": description},
    )
    if created:
        count += 1

print(f"✅ {count} alergias nuevas cargadas. Total en BD: {Allergy.objects.count()}")
