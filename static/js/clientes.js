/**
 * TaskCore - Clients Directory Alpine.js Component & Utilities
 * Módulo desacoplado para la gestión de clientes, saldos a favor y Master Data.
 */

document.addEventListener('alpine:init', () => {
    Alpine.data('clientesModule', () => ({
        modalCrearAbierto: false,
        modalEditarAbierto: false,
        loading: false,
        
        nuevoCliente: {
            nombre_empresa: '',
            contacto_nombre: '',
            email: '',
            telefono: ''
        },
        
        clienteActual: {
            id: null,
            nombre_empresa: '',
            contacto_nombre: '',
            email: '',
            telefono: ''
        },
        
        abrirModalCrear() {
            this.nuevoCliente = {
                nombre_empresa: '',
                contacto_nombre: '',
                email: '',
                telefono: ''
            };
            this.modalCrearAbierto = true;
        },
        
        cerrarModalCrear() {
            this.modalCrearAbierto = false;
        },
        
        async guardarNuevoCliente() {
            if (!this.nuevoCliente.nombre_empresa.trim()) {
                alert("El nombre de la empresa es obligatorio.");
                return;
            }
            
            this.loading = true;
            try {
                const res = await fetch('/api/clientes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.nuevoCliente)
                });
                
                const data = await res.json();
                if (res.ok) {
                    alert("¡Cliente y carpeta Master Data creados exitosamente!");
                    this.cerrarModalCrear();
                    window.location.reload();
                } else {
                    alert("Error: " + (data.error || "No se pudo registrar el cliente."));
                }
            } catch (e) {
                alert("Error de conexión al servidor.");
                console.error(e);
            } finally {
                this.loading = false;
            }
        },
        
        abrirModalEditar(cliente) {
            this.clienteActual = { ...cliente };
            this.modalEditarAbierto = true;
        },
        
        cerrarModalEditar() {
            this.modalEditarAbierto = false;
        },
        
        async guardarEdicion() {
            if (!this.clienteActual.nombre_empresa.trim()) {
                alert("El nombre de la empresa es obligatorio.");
                return;
            }
            
            this.loading = true;
            try {
                const res = await fetch(`/api/clientes/${this.clienteActual.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.clienteActual)
                });
                
                const data = await res.json();
                if (res.ok) {
                    alert("Cliente actualizado correctamente.");
                    this.cerrarModalEditar();
                    window.location.reload();
                } else {
                    alert("Error: " + (data.error || "No se pudo actualizar el cliente."));
                }
            } catch (e) {
                alert("Error de conexión al servidor.");
                console.error(e);
            } finally {
                this.loading = false;
            }
        },
        
        async eliminarCliente(id, nombreEmpresa) {
            if (!confirm(`¿Estás seguro de que deseas eliminar al cliente "${nombreEmpresa}"?\n\nEsta acción eliminará todas las órdenes de trabajo asociadas y no se puede deshacer.`)) {
                return;
            }
            
            try {
                const res = await fetch(`/api/clientes/${id}`, {
                    method: 'DELETE'
                });
                
                const data = await res.json();
                if (res.ok) {
                    alert(data.mensaje || "Cliente eliminado con éxito.");
                    window.location.reload();
                } else {
                    alert("Error: " + (data.error || "No se pudo eliminar el cliente."));
                }
            } catch (err) {
                console.error(err);
                alert("Error de conexión al intentar eliminar.");
            }
        },
        
        abrirCarpetaEnServidor(ruta) {
            if (!ruta) {
                alert("Este cliente no tiene una carpeta de Master Data asignada.");
                return;
            }
            
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(ruta).catch(() => {});
            }
            
            const utf8Ruta = unescape(encodeURIComponent(ruta));
            const rutaCodificada = btoa(utf8Ruta);
            window.location.href = `taskcore://${rutaCodificada}?server=${window.location.hostname}`;
        }
    }));
});
