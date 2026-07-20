/**
 * TaskCore - Kanban Board Alpine.js Component
 * Módulo desacoplado para la gestión del flujo visual de producción y diagnóstico técnico.
 */

document.addEventListener('alpine:init', () => {
    Alpine.data('kanbanBoard', (initialOrders, initialDisenadores, currentUserId) => ({
        orders: initialOrders || [],
        disenadoresList: initialDisenadores || [],
        currentUserId: parseInt(currentUserId) || null,
        filtroMisTareas: false,
        vistaCompacta: false,
        incidenciaModalOpen: false,
        incidenciaOrderId: null,
        incidenciaTipo: 'Falta Material',
        incidenciaDetalle: '',
        cancelarModalOpen: false,
        cancelarOrderId: null,
        cancelarOrderName: '',
        cancelarOrderSaldo: 0.0,
        cancelarMotivo: '',
        cancelarSaldoADevolver: 0.0,
        deudaModalOpen: false,
        deudaOrderId: null,
        deudaSaldo: 0.0,
        deudaContacto: '',
        deudaTelefono: '',
        deudaAccion: 'enviar',
        filesModalOpen: false,
        filesModalOrderId: null,
        filesModalLoading: false,
        filesModalList: [],
        qrModalOpen: false,
        qrModalUrl: '',
        qrModalPedidoId: '',
        presupuestoModalOpen: false,
        presupuestoOrderId: null,
        presupuestoOrderName: '',
        presupuestoMonto: 0.0,
        diagnosticoModalOpen: false,
        diagnosticoOrderId: null,
        diagnosticoForm: {
            defectos: '',
            detalles: '',
            insumos: '',
            observaciones: ''
        },
        statesList: [
            "Borrador",
            "Pendiente (Ingreso)",
            "En Diagnóstico",
            "En Revisión (Presupuesto)",
            "Reparación Aprobada",
            "En Reparación / Servicio",
            "Listo para Entregar",
            "Completado / Entregado",
            "Cancelado"
        ],
        columns: [
            { id: 'Pendiente (Ingreso)', title: 'Ingreso / Pendiente', headerClass: 'from-slate-800 to-slate-800 border-b-slate-600', accentColor: 'bg-slate-500' },
            { id: 'En Diagnóstico', title: 'En Diagnóstico', headerClass: 'from-blue-900/40 to-slate-800 border-b-blue-500/50', accentColor: 'bg-blue-500' },
            { id: 'En Revisión (Presupuesto)', title: 'En Revisión (Presupuesto)', headerClass: 'from-amber-900/40 to-slate-800 border-b-amber-500/50', accentColor: 'bg-amber-500' },
            { id: 'Reparación Aprobada', title: 'Reparación Aprobada', headerClass: 'from-emerald-900/40 to-slate-800 border-b-emerald-500/50', accentColor: 'bg-emerald-500' },
            { id: 'En Reparación / Servicio', title: 'En Reparación', headerClass: 'from-purple-900/40 to-slate-800 border-b-purple-500/50', accentColor: 'bg-purple-500' },
            { id: 'Listo para Entregar', title: 'Listo para Entregar', headerClass: 'from-orange-900/40 to-slate-800 border-b-orange-500/50', accentColor: 'bg-orange-500' }
        ],
        
        getOrdersForStatus(status) {
            let list = this.orders.filter(o => o.estado === status);
            if (this.filtroMisTareas) {
                list = list.filter(o => o.disenador_id === this.currentUserId);
            }
            return list;
        },
        
        toggleMisTareas() {
            this.filtroMisTareas = !this.filtroMisTareas;
        },
        
        async asignarDisenador(orderId, disenadorId) {
            try {
                const response = await fetch(`/api/ordenes/${orderId}/asignar`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ disenador_id: disenadorId })
                });
                
                if(response.ok) {
                    const data = await response.json();
                    const order = this.orders.find(o => o.id === orderId);
                    if(order) {
                        order.disenador_id = disenadorId;
                        order.disenador_nombre = data.disenador_nombre;
                    }
                } else {
                    const data = await response.json();
                    alert('Error: ' + data.error);
                }
            } catch(e) {
                alert('Error de conexión');
            }
        },
        
        async changeState(orderId, newState, enviarRecordatorio = false) {
            try {
                const response = await fetch(`/api/ordenes/${orderId}/estado`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        nuevo_estado: newState,
                        usuario_id: 1, // Por defecto, simulamos el ID del admin
                        enviar_recordatorio: enviarRecordatorio
                    })
                });
                
                if(response.ok) {
                    const order = this.orders.find(o => o.id === orderId);
                    if(order) order.estado = newState;
                } else {
                    const data = await response.json();
                    alert('Error: ' + data.error);
                }
            } catch(e) {
                alert('Error de conexión');
            }
        },
        
        async selectState(orderId, newState) {
            if (newState === 'En Reparación / Servicio' || newState === 'Listo para Entregar') {
                if (!confirm(`Este estado normalmente se actualiza AUTOMÁTICAMENTE cuando los técnicos procesan o completan el servicio en los laboratorios.\n\n¿Deseas forzar este cambio manualmente?`)) {
                    return;
                }
            }
            if (newState === 'Completado / Entregado') {
                const order = this.orders.find(o => o.id === orderId);
                if (order && order.saldo_pendiente > 0) {
                    this.deudaOrderId = orderId;
                    this.deudaSaldo = order.saldo_pendiente;
                    this.deudaContacto = order.cliente_contacto;
                    this.deudaTelefono = order.cliente_telefono;
                    this.deudaAccion = 'enviar';
                    this.deudaModalOpen = true;
                    return;
                }
            }
            await this.changeState(orderId, newState);
        },
        
        async confirmarCompletarConDeuda() {
            this.deudaModalOpen = false;
            const enviarRecordatorio = this.deudaAccion === 'enviar';
            await this.changeState(this.deudaOrderId, 'Completado / Entregado', enviarRecordatorio);
        },
        
        abrirModalQr(orden) {
            this.qrModalPedidoId = orden.pedido_id;
            this.qrModalUrl = orden.public_url;
            this.qrModalOpen = true;
        },
        
        copiarEnlaceQr() {
            navigator.clipboard.writeText(window.location.origin + this.qrModalUrl);
            alert('¡Enlace de seguimiento copiado al portapapeles!');
        },
        
        async uploadMuestra(orden, event) {
            const file = event.target.files[0];
            if (!file) return;
            
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                const response = await fetch(`/api/ordenes/${orden.id}/upload-muestra`, {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    const data = await response.json();
                    orden.ruta_muestra = data.ruta;
                    const statusEl = document.getElementById('upload_status_' + orden.id);
                    if(statusEl) {
                        statusEl.classList.remove('hidden');
                        setTimeout(() => { statusEl.classList.add('hidden'); }, 3000);
                    }
                } else {
                    const data = await response.json();
                    alert('Error al subir: ' + data.error);
                }
            } catch(e) {
                alert('Error de conexión al subir archivo');
            }
        },
        
        abrirModalIncidencia(orderId) {
            this.incidenciaOrderId = orderId;
            this.incidenciaTipo = 'Falta Repuesto';
            this.incidenciaDetalle = '';
            this.incidenciaModalOpen = true;
        },
        
        async enviarIncidencia() {
            if(!this.incidenciaDetalle.trim()) {
                alert('Por favor describe los detalles de la incidencia.');
                return;
            }
            try {
                const response = await fetch(`/api/ordenes/${this.incidenciaOrderId}/incidencias`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        usuario_id: this.currentUserId || 1,
                        tipo_problema: this.incidenciaTipo,
                        detalles: this.incidenciaDetalle
                    })
                });
                
                if(response.ok) {
                    const data = await response.json();
                    const order = this.orders.find(o => o.id === this.incidenciaOrderId);
                    if(order) {
                        order.tiene_incidencia = true;
                        order.tipo_incidencia = this.incidenciaTipo;
                        order.detalle_incidencia = this.incidenciaDetalle;
                        order.incidencia_id = data.incidencia_id;
                    }
                    this.incidenciaModalOpen = false;
                } else {
                    const data = await response.json();
                    alert('Error al reportar: ' + data.error);
                }
            } catch(e) {
                alert('Error de conexión');
            }
        },

        abrirModalCancelar(orderId) {
            const order = this.orders.find(o => o.id === orderId);
            if (order) {
                this.cancelarOrderId = orderId;
                this.cancelarOrderName = `[P${order.pedido_id}_A${order.id}] - ${order.nombre_proyecto}`;
                const total = parseFloat(order.monto_total || 0);
                const saldo = parseFloat(order.saldo_pendiente || 0);
                const abono = Math.max(0.0, total - saldo);
                
                this.cancelarOrderSaldo = abono;
                this.cancelarSaldoADevolver = abono;
                this.cancelarMotivo = '';
                this.cancelarModalOpen = true;
            }
        },

        async enviarCancelar() {
            if (parseFloat(this.cancelarSaldoADevolver) > parseFloat(this.cancelarOrderSaldo)) {
                alert('El monto a devolver no puede ser mayor que el abono registrado.');
                return;
            }
            try {
                const response = await fetch(`/api/ordenes/${this.cancelarOrderId}/cancelar`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        usuario_id: this.currentUserId || 1,
                        motivo: this.cancelarMotivo,
                        saldo_a_devolver: parseFloat(this.cancelarSaldoADevolver || 0)
                    })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    alert(`¡Orden cancelada con éxito!\nSaldo a favor actual del cliente: $${parseFloat(data.saldo_favor_actual).toFixed(2)} USD`);
                    this.cancelarModalOpen = false;
                    window.location.reload();
                } else {
                    const data = await response.json();
                    alert('Error al cancelar orden: ' + data.error);
                }
            } catch(e) {
                alert('Error de conexión');
            }
        },

        abrirModalPresupuesto(orden) {
            this.presupuestoOrderId = orden.id;
            this.presupuestoOrderName = `[P${orden.pedido_id}_A${orden.id}] - ${orden.nombre_proyecto}`;
            this.presupuestoMonto = parseFloat(orden.monto_total || 0).toFixed(2);
            this.presupuestoModalOpen = true;
        },

        async enviarPresupuesto(aprobar = false) {
            if (isNaN(parseFloat(this.presupuestoMonto)) || parseFloat(this.presupuestoMonto) < 0) {
                alert('Por favor ingresa un monto válido.');
                return;
            }
            try {
                const response = await fetch(`/api/ordenes/${this.presupuestoOrderId}/presupuesto`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        monto_total: parseFloat(this.presupuestoMonto),
                        aprobar: aprobar
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    alert(`¡Presupuesto actualizado exitosamente!\nNuevo Monto: $${parseFloat(data.nuevo_monto).toFixed(2)} USD`);
                    this.presupuestoModalOpen = false;
                    window.location.reload();
                } else {
                    const data = await response.json();
                    alert('Error al actualizar presupuesto: ' + data.error);
                }
            } catch(e) {
                alert('Error de conexión');
            }
        },
        
        async resolverIncidencia(orderId, incidenciaId, extraData = {}) {
            if(!confirm('¿Estás seguro de marcar esta incidencia como resuelta?')) return;
            try {
                const response = await fetch(`/api/incidencias/${incidenciaId}/resolver`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        usuario_id: this.currentUserId || 1,
                        ...extraData
                    })
                });
                
                if(response.ok) {
                    const order = this.orders.find(o => o.id === orderId);
                    if(order) {
                        order.tiene_incidencia = false;
                        order.tipo_incidencia = '';
                        order.detalle_incidencia = '';
                        order.incidencia_id = null;
                        if (extraData.monto_aprobado !== undefined) {
                            order.saldo_pendiente = extraData.ocultar_precio_ventas ? null : parseFloat(extraData.monto_aprobado);
                            order.monto_total = extraData.ocultar_precio_ventas ? null : parseFloat(extraData.monto_aprobado);
                            order.ocultar_precio = extraData.ocultar_precio_ventas;
                        }
                    }
                } else {
                    const data = await response.json();
                    alert('Error al resolver: ' + data.error);
                }
            } catch(e) {
                alert('Error de conexión');
            }
        },
        
        abrirCarpetaEnServidor(ruta) {
            if(!ruta) {
                alert("Esta orden no tiene una ruta de carpeta asignada.");
                return;
            }
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(ruta).catch(() => {});
            }
            const utf8Ruta = unescape(encodeURIComponent(ruta));
            const rutaCodificada = btoa(utf8Ruta);
            window.location.href = `taskcore://${rutaCodificada}?server=${window.location.hostname}`;
        },

        async abrirModalArchivos(ordenId) {
            this.filesModalOrderId = ordenId;
            this.filesModalOpen = true;
            this.filesModalLoading = true;
            this.filesModalList = [];
            try {
                const response = await fetch(`/api/ordenes/${ordenId}/archivos`);
                if (response.ok) {
                    const data = await response.json();
                    this.filesModalList = data.archivos || [];
                } else {
                    console.error("Error al obtener archivos");
                }
            } catch (e) {
                console.error("Error de conexión al obtener archivos:", e);
            } finally {
                this.filesModalLoading = false;
            }
        },

        abrirDiagnostico(orden) {
            this.diagnosticoOrderId = orden.id;
            this.diagnosticoForm.defectos = orden.diagnostico_defectos || '';
            this.diagnosticoForm.detalles = orden.diagnostico_detalles || '';
            this.diagnosticoForm.insumos = orden.diagnostico_insumos || '';
            this.diagnosticoForm.observaciones = orden.diagnostico_observaciones || '';
            this.diagnosticoModalOpen = true;
        },

        async guardarDiagnostico() {
            try {
                const response = await fetch(`/api/ordenes/${this.diagnosticoOrderId}/diagnostico`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.diagnosticoForm)
                });
                
                if (response.ok) {
                    const order = this.orders.find(o => o.id === this.diagnosticoOrderId);
                    if (order) {
                        order.diagnostico_defectos = this.diagnosticoForm.defectos;
                        order.diagnostico_detalles = this.diagnosticoForm.detalles;
                        order.diagnostico_insumos = this.diagnosticoForm.insumos;
                        order.diagnostico_observaciones = this.diagnosticoForm.observaciones;
                    }
                    this.diagnosticoModalOpen = false;
                    alert('¡Diagnóstico guardado exitosamente!');
                } else {
                    const data = await response.json();
                    alert('Error al guardar: ' + data.error);
                }
            } catch(e) {
                alert('Error de conexión');
            }
        }
    }));
});
