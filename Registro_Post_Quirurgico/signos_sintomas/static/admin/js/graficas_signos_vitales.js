(function () {
    'use strict';

    function colorPunto(indice, alertas) {
        return alertas.includes(indice) ? '#dc2626' : 'transparent';
    }

    function radioPunto(indice, alertas, valor) {
        if (valor === null || valor === undefined) {
            return 0;
        }
        return alertas.includes(indice) ? 5 : 3;
    }

    function opcionesBase() {
        return {
            responsive: true,
            animation: false,
            plugins: {legend: {display: false}},
            scales: {
                x: {
                    grid: {color: '#f3f4f6'},
                    ticks: {font: {size: 10}, maxRotation: 45}
                },
                y: {
                    grid: {color: '#f3f4f6'},
                    ticks: {font: {size: 10}}
                }
            }
        };
    }

    function seriePrincipal(etiqueta, valores, color, datos) {
        return {
            label: etiqueta,
            data: valores,
            borderColor: color,
            borderWidth: 2,
            pointBackgroundColor: valores.map(function (valor, indice) {
                return colorPunto(indice, datos.alertas_idx);
            }),
            pointRadius: valores.map(function (valor, indice) {
                return radioPunto(indice, datos.alertas_idx, valor);
            }),
            tension: 0.3,
            spanGaps: false
        };
    }

    function serieUmbral(etiqueta, valor, color, guiones) {
        return {
            label: etiqueta,
            data: [],
            valorUmbral: valor,
            borderColor: color,
            borderWidth: 1,
            borderDash: guiones,
            pointRadius: 0,
            tension: 0
        };
    }

    function completarUmbrales(datasets, labels) {
        datasets.slice(1).forEach(function (dataset) {
            dataset.data = labels.map(function () {
                return dataset.valorUmbral;
            });
        });
    }

    // Los umbrales llegan del panel (`data-umbrales`), que los lee de
    // `alert_engine`. Aquí no se escribe ninguno a mano (BE-02).
    function crearGraficas(contenedor, datos, umbrales) {
        const inicial = datos['7'];
        const charts = {};

        const temperatura = [
            seriePrincipal('Temperatura', inicial.temps, '#dc2626', inicial),
            serieUmbral('Umbral fiebre', umbrales.fiebre, '#fca5a5', [4, 4])
        ];
        completarUmbrales(temperatura, inicial.labels);
        const opcionesTemperatura = opcionesBase();
        // UX-P05: 35-40 es el rango que se ve por defecto, no un tope. Con
        // `min`/`max` fijos, una temperatura de 41 (el bot acepta hasta 45)
        // quedaba fuera del lienzo: el valor más grave era el único que no se
        // dibujaba. `suggested*` abre la escala si el dato se sale.
        opcionesTemperatura.scales.y = {
            grid: {color: '#f3f4f6'},
            suggestedMin: 35,
            suggestedMax: 40,
            ticks: {stepSize: 0.5, font: {size: 10}}
        };
        charts.temp = new Chart(
            contenedor.querySelector('[data-serie="temperatura"]'),
            {
                type: 'line',
                data: {labels: inicial.labels, datasets: temperatura},
                options: opcionesTemperatura
            }
        );

        const opcionesDolor = opcionesBase();
        opcionesDolor.scales.y = {
            grid: {color: '#f3f4f6'},
            min: 0,
            max: 10,
            ticks: {stepSize: 2, font: {size: 10}}
        };
        charts.eva = new Chart(
            contenedor.querySelector('[data-serie="dolor"]'),
            {
                type: 'line',
                data: {
                    labels: inicial.labels,
                    datasets: [
                        seriePrincipal('Dolor EVA', inicial.evas, '#f59e0b', inicial)
                    ]
                },
                options: opcionesDolor
            }
        );

        const frecuencia = [
            seriePrincipal('FC', inicial.fcs, '#3b82f6', inicial),
            serieUmbral('Taquicardia leve', umbrales.fc_baja, '#fcd34d', [3, 3]),
            serieUmbral('Taquicardia', umbrales.fc_media, '#f87171', [3, 3])
        ];
        completarUmbrales(frecuencia, inicial.labels);
        charts.fc = new Chart(
            contenedor.querySelector('[data-serie="frecuencia"]'),
            {
                type: 'line',
                data: {labels: inicial.labels, datasets: frecuencia},
                options: opcionesBase()
            }
        );

        return charts;
    }

    function cambiarPeriodo(contenedor, charts, datos, dias) {
        const nuevos = datos[String(dias)];
        if (!nuevos) {
            return;
        }

        contenedor.querySelectorAll('.js-grafica-periodo').forEach(function (boton) {
            const activo = boton.dataset.dias === String(dias);
            boton.setAttribute('aria-pressed', activo ? 'true' : 'false');
            boton.style.fontWeight = activo ? '600' : '';
            boton.style.color = activo ? '#374151' : '#6b7280';
        });

        const valores = {temp: nuevos.temps, eva: nuevos.evas, fc: nuevos.fcs};
        Object.keys(charts).forEach(function (tipo) {
            const chart = charts[tipo];
            const serie = valores[tipo];
            chart.data.labels = nuevos.labels;
            chart.data.datasets[0].data = serie;
            chart.data.datasets[0].pointBackgroundColor = serie.map(
                function (valor, indice) {
                    return colorPunto(indice, nuevos.alertas_idx);
                }
            );
            chart.data.datasets[0].pointRadius = serie.map(
                function (valor, indice) {
                    return radioPunto(indice, nuevos.alertas_idx, valor);
                }
            );
            completarUmbrales(chart.data.datasets, nuevos.labels);
            chart.update();
        });
    }

    function iniciar() {
        if (typeof Chart === 'undefined') {
            return;
        }

        document.querySelectorAll('.js-graficas-signos').forEach(function (contenedor) {
            if (contenedor.dataset.inicializada === 'true') {
                return;
            }

            let datos;
            let umbrales;
            try {
                datos = JSON.parse(contenedor.dataset.graficas);
                umbrales = JSON.parse(contenedor.dataset.umbrales);
            } catch (error) {
                return;
            }
            if (!datos['7']) {
                return;
            }

            // UX-P04: el aviso de «no se pudieron dibujar» viene del servidor
            // y solo se quita cuando las gráficas existen. Si Chart.js no
            // llega o algo falla aquí, el médico lo ve en vez de tres
            // lienzos en blanco que parecen «no hay datos».
            let charts;
            try {
                charts = crearGraficas(contenedor, datos, umbrales);
            } catch (error) {
                return;
            }
            const aviso = contenedor.querySelector('.js-graficas-aviso');
            if (aviso) {
                aviso.remove();
            }
            contenedor.querySelectorAll('.js-grafica-periodo').forEach(function (boton) {
                boton.addEventListener('click', function () {
                    cambiarPeriodo(contenedor, charts, datos, boton.dataset.dias);
                });
            });
            contenedor.dataset.inicializada = 'true';
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciar);
    } else {
        iniciar();
    }
}());
