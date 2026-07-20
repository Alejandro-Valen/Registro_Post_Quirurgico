(function () {
    'use strict';

    function iniciar() {
        const select = document.querySelector('[name="motivo_resolucion"]');
        const campoDetalle = document.querySelector(
            '[name="motivo_resolucion_detalle"]'
        );
        if (!select || !campoDetalle) {
            return;
        }

        const contenedor = campoDetalle.closest('p') || campoDetalle.parentNode;
        const actualizar = function () {
            contenedor.style.display = select.value === 'OTRO' ? '' : 'none';
        };

        select.addEventListener('change', actualizar);
        actualizar();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciar);
    } else {
        iniciar();
    }
}());
