document.addEventListener('DOMContentLoaded', () => {
    const clienteSelect = document.getElementById('cliente_id');
    const form = document.getElementById('ordenTrabajoForm');
    const alertContainer = document.getElementById('alert-container');
    const submitBtn = document.getElementById('submitBtn');
    const submitSpinner = document.getElementById('submitSpinner');
    const submitIcon = document.getElementById('submitIcon');

    // Cargar la lista de clientes al iniciar
    cargarClientes();

    // Manejar el envío del formulario
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // UI Feedback: Loading state
        setLoadingState(true);
        alertContainer.innerHTML = ''; // Limpiar alertas previas

        const payload = {
            nombre_proyecto: document.getElementById('nombre_proyecto').value.trim(),
            cliente_id: parseInt(clienteSelect.value, 10),
            creador_id: parseInt(document.getElementById('creador_id').value, 10),
            especificaciones: document.getElementById('especificaciones').value.trim()
        };

        try {
            const response = await fetch('/api/ordenes', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (response.ok) {
                showAlert('success', '¡Éxito!', `La orden de trabajo se ha creado correctamente (ID: ${data.orden_id}, Estado: ${data.estado}).`);
                form.reset(); // Limpiar el formulario
            } else {
                showAlert('danger', 'Error', data.error || 'Ocurrió un error al crear la orden.');
            }
        } catch (error) {
            console.error('Error enviando la solicitud:', error);
            showAlert('danger', 'Error de Conexión', 'No se pudo comunicar con el servidor.');
        } finally {
            setLoadingState(false);
        }
    });

    // Función para obtener clientes del backend
    async function cargarClientes() {
        try {
            const response = await fetch('/api/clientes');
            const data = await response.json();

            if (response.ok) {
                // Populate el select list
                data.forEach(cliente => {
                    const option = document.createElement('option');
                    option.value = cliente.id;
                    option.textContent = `${cliente.nombre_empresa} ${cliente.contacto_nombre ? '(' + cliente.contacto_nombre + ')' : ''}`;
                    clienteSelect.appendChild(option);
                });
            } else {
                showAlert('warning', 'Aviso', 'No se pudieron cargar los clientes del sistema.');
            }
        } catch (error) {
            console.error('Error cargando clientes:', error);
            showAlert('danger', 'Error', 'Fallo al conectar con el servidor para obtener los clientes.');
        }
    }

    // Funciones auxiliares para la UI
    function setLoadingState(isLoading) {
        submitBtn.disabled = isLoading;
        if (isLoading) {
            submitSpinner.classList.remove('d-none');
            submitIcon.classList.add('d-none');
        } else {
            submitSpinner.classList.add('d-none');
            submitIcon.classList.remove('d-none');
        }
    }

    function showAlert(type, title, message) {
        const alertHtml = `
            <div class="alert alert-${type} alert-dismissible fade show shadow-sm" role="alert">
                <strong>${title}</strong> ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
        alertContainer.innerHTML = alertHtml;
    }
});
