/**
 * MediKnow — script.js
 * Gestiona la interactividad del cuestionario de síntomas:
 *   - Mostrar/ocultar slider de intensidad al marcar un checkbox
 *   - Actualizar el valor numérico del slider en tiempo real
 *   - Colorear la barra del slider según la intensidad
 *   - Contador de síntomas seleccionados
 *   - Validación antes de enviar el formulario
 */

document.addEventListener('DOMContentLoaded', () => {

  /* ── Referencias globales ────────────────────────────── */
  const form          = document.getElementById('symptom-form');
  const selectedCount = document.getElementById('selected-count');
  const submitBtn     = document.getElementById('btn-diagnose');

  /* ── Inicializar cada fila de síntoma ────────────────── */
  document.querySelectorAll('.symptom-row').forEach(row => {
    const checkbox = row.querySelector('input[type="checkbox"]');
    const panel    = row.querySelector('.intensity-panel');
    const slider   = row.querySelector('input[type="range"]');
    const display  = row.querySelector('.intensity-value-display');

    if (!checkbox || !panel || !slider || !display) return;

    /* Estado inicial: sincronizar con recarga de página */
    if (checkbox.checked) {
      panel.classList.add('visible');
      row.classList.add('is-active');
      updateSliderAppearance(slider, display);
    }

    /* Toggle del panel al marcar/desmarcar */
    checkbox.addEventListener('change', () => {
      const checked = checkbox.checked;
      panel.classList.toggle('visible', checked);
      row.classList.toggle('is-active', checked);

      if (checked) {
        /* Forzar valor mínimo en 1 si el slider estaba en 0 */
        if (parseInt(slider.value) < 1) slider.value = 1;
        updateSliderAppearance(slider, display);
        /* Dar foco al slider para accesibilidad */
        slider.focus();
      } else {
        /* Resetear a 5 para que el estado sea neutral en el próximo uso */
        slider.value = 5;
        display.textContent = '5';
        resetSliderColor(slider);
      }

      updateCounter();
    });

    /* Actualizar display mientras el usuario mueve el slider */
    slider.addEventListener('input', () => {
      updateSliderAppearance(slider, display);
    });
  });

  /* ── Contador de síntomas seleccionados ──────────────── */
  function updateCounter() {
    const total = document.querySelectorAll('.symptom-row input[type="checkbox"]:checked').length;
    if (selectedCount) {
      selectedCount.textContent = total;
      selectedCount.closest('.submit-hint').style.opacity = total > 0 ? '1' : '.5';
    }
    if (submitBtn) {
      submitBtn.disabled = total === 0;
      submitBtn.style.opacity = total === 0 ? '.55' : '1';
    }
  }

  /* Estado inicial del contador */
  updateCounter();

  /* ── Apariencia dinámica del slider ──────────────────── */
  function updateSliderAppearance(slider, display) {
    const val = parseInt(slider.value);
    display.textContent = val;

    /* Color de relleno dinámico según intensidad */
    let fillColor;
    if (val <= 3)      fillColor = '#2B7FD4'; /* Azul — leve */
    else if (val <= 6) fillColor = '#D97706'; /* Ámbar — moderado */
    else               fillColor = '#DC2626'; /* Rojo — severo */

    const pct = ((val - 1) / 9) * 100;
    slider.style.background = `linear-gradient(to right, ${fillColor} ${pct}%, #E5E7EB ${pct}%)`;
    display.style.color = fillColor;
  }

  function resetSliderColor(slider) {
    slider.style.background = '#E5E7EB';
  }

  /* ── Validación antes de enviar ──────────────────────── */
  if (form) {
    form.addEventListener('submit', event => {
      const anyChecked = form.querySelectorAll('input[type="checkbox"]:checked').length > 0;

      if (!anyChecked) {
        event.preventDefault();
        showAlert('Selecciona al menos un síntoma antes de calcular el diagnóstico.');
        return;
      }

      /* Deshabilitar botón para evitar envíos dobles */
      submitBtn.disabled = true;
      submitBtn.innerHTML = `
        <svg viewBox="0 0 24 24" style="animation: spin .8s linear infinite; width:18px; height:18px; stroke:white; fill:none; stroke-width:2; stroke-linecap:round;">
          <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4"/>
        </svg>
        Calculando…
      `;
    });
  }

  /* ── Mensaje de alerta inline ────────────────────────── */
  function showAlert(message) {
    let alertEl = document.getElementById('form-alert');
    if (!alertEl) {
      alertEl = document.createElement('div');
      alertEl.id = 'form-alert';
      alertEl.className = 'alert-warning';
      alertEl.setAttribute('role', 'alert');
      form.insertBefore(alertEl, form.querySelector('.submit-area'));
    }
    alertEl.textContent = message;
    alertEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setTimeout(() => alertEl.remove(), 4000);
  }

  /* ── Animación del spinner (inyectada en <head>) ─────── */
  if (!document.getElementById('mk-spin-style')) {
    const style = document.createElement('style');
    style.id = 'mk-spin-style';
    style.textContent = '@keyframes spin { to { transform: rotate(360deg); } }';
    document.head.appendChild(style);
  }

  /* ── Scroll suave a resultados si existen en la página── */
  const resultsSection = document.getElementById('results-section');
  if (resultsSection) {
    setTimeout(() => {
      resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 200);
  }

});
// ── Filtrado de tablas en tiempo real (Agregado) ──
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-table-filter]').forEach(input => {
    const table = document.querySelector(input.dataset.tableFilter);
    if (!table) return;
    const tbody = table.querySelector('tbody');
    if (!tbody) return;

    const rows = Array.from(tbody.querySelectorAll('tr'));
    let emptyRow = null;

    input.addEventListener('input', () => {
      const term = input.value.trim().toLowerCase();
      let visibleCount = 0;

      rows.forEach(row => {
        if (row.dataset.tableEmpty) return;
        const match = row.textContent.toLowerCase().includes(term);
        row.classList.toggle('search-hidden', !match);
        if (match) visibleCount += 1;
      });

      if (!emptyRow) {
        const colCount = table.querySelectorAll('thead th').length || 1;
        emptyRow = document.createElement('tr');
        emptyRow.className = 'search-empty-row';
        emptyRow.innerHTML = `<td colspan="${colCount}">No se encontraron resultados para "<span></span>".</td>`;
        tbody.appendChild(emptyRow);
      }

      emptyRow.querySelector('span').textContent = input.value.trim();
      emptyRow.classList.toggle('search-hidden', visibleCount !== 0 || term === '');
    });
  });
});
