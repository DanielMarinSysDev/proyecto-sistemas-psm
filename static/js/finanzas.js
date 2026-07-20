/**
 * TaskCore - Module Finanzas Alpine.js Component
 * Lógica del panel de cuentas por cobrar, deudores, registros de abonos y liquidación de facturas.
 */

document.addEventListener('alpine:init', () => {
    Alpine.data('finanzasModule', () => ({
        deudores: [],
        searchQuery: '',
        loadingDeudores: false,
        
        activeClient: null,
        pedidosActivos: [],
        loadingPedidos: false,
        
        pedidosSeleccionados: [],
        detallesPago: '',
        metodoPagoLiquidar: '',
        procesandoPago: false,
        pagoMsg: '',
        pagoError: false,
        
        modalAbono: false,
        pedidoAbono: null,
        procesandoAbono: false,
        abonoForm: { monto: '', metodo_pago: '', detalles: '' },
        intervaloRecordatorio: '3',
        
        initModule() {
            this.fetchDeudores();
            this.cargarIntervalo();
        },
        
        async cargarIntervalo() {
            try {
                const res = await fetch('/api/configuracion/intervalo_recordatorio');
                if (res.ok) {
                    const data = await res.json();
                    this.intervaloRecordatorio = data.valor;
                }
            } catch (e) {
                console.error("Error cargando intervalo de recordatorio:", e);
            }
        },
        
        async guardarIntervalo() {
            try {
                const res = await fetch('/api/configuracion/intervalo_recordatorio', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ valor: this.intervaloRecordatorio })
                });
                if (!res.ok) {
                    alert("Error guardando intervalo");
                }
            } catch (e) {
                console.error("Error guardando intervalo:", e);
                alert("Error en la conexión con el servidor.");
            }
        },
        
        get filteredDeudores() {
            if (this.searchQuery === '') {
                return this.deudores;
            }
            const lowerCaseQuery = this.searchQuery.toLowerCase();
            return this.deudores.filter(c => {
                return c.nombre_empresa.toLowerCase().includes(lowerCaseQuery) ||
                       c.contacto_nombre.toLowerCase().includes(lowerCaseQuery);
            });
        },
        
        async fetchDeudores() {
            this.loadingDeudores = true;
            try {
                const res = await fetch('/api/finanzas/deudores');
                if (res.ok) {
                    this.deudores = await res.json();
                }
            } catch (e) {
                console.error("Error al cargar deudores:", e);
            } finally {
                this.loadingDeudores = false;
            }
        },
        
        async seleccionarCliente(cliente) {
            this.activeClient = cliente;
            this.pedidosSeleccionados = [];
            this.detallesPago = '';
            this.pagoMsg = '';
            await this.fetchPedidosCliente(cliente.id);
        },
        
        async fetchPedidosCliente(clienteId) {
            this.loadingPedidos = true;
            this.pedidosActivos = [];
            try {
                const res = await fetch(`/api/finanzas/deudores/${clienteId}/pedidos`);
                if (res.ok) {
                    this.pedidosActivos = await res.json();
                }
            } catch (e) {
                console.error("Error al cargar pedidos:", e);
            } finally {
                this.loadingPedidos = false;
            }
        },
        
        async procesarPago() {
            if(this.pedidosSeleccionados.length === 0 || !this.metodoPagoLiquidar) return;
            
            this.procesandoPago = true;
            this.pagoMsg = '';
            this.pagoError = false;
            
            try {
                const res = await fetch('/api/finanzas/pagar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        pedidos: this.pedidosSeleccionados,
                        detalles: this.detallesPago,
                        metodo_pago: this.detallesPago ? `${this.metodoPagoLiquidar} (Ref: ${this.detallesPago})` : this.metodoPagoLiquidar
                    })
                });
                
                const data = await res.json();
                
                if (res.ok) {
                    this.pagoError = false;
                    this.pagoMsg = "¡Pagos registrados exitosamente!";
                    this.pedidosSeleccionados = [];
                    this.detallesPago = '';
                    this.metodoPagoLiquidar = '';
                    
                    // Refrescar datos
                    await this.fetchPedidosCliente(this.activeClient.id);
                    await this.fetchDeudores();
                    
                    // Si ya no tiene pedidos, cerramos el panel
                    if(this.pedidosActivos.length === 0) {
                        setTimeout(() => {
                            this.activeClient = null;
                            this.pagoMsg = '';
                        }, 2000);
                    }
                } else {
                    this.pagoError = true;
                    this.pagoMsg = data.error || "Error al procesar el pago.";
                }
            } catch(e) {
                this.pagoError = true;
                this.pagoMsg = "Error de red al procesar el pago.";
            } finally {
                this.procesandoPago = false;
                setTimeout(() => { this.pagoMsg = ''; }, 5000);
            }
        },
        
        abrirModalAbono(pedido) {
            this.pedidoAbono = pedido;
            this.abonoForm.monto = '';
            this.abonoForm.metodo_pago = '';
            this.abonoForm.detalles = '';
            this.modalAbono = true;
        },
        
        async guardarAbono() {
            if (!this.pedidoAbono || !this.abonoForm.monto || !this.abonoForm.metodo_pago) return;
            this.procesandoAbono = true;
            
            try {
                const res = await fetch('/api/finanzas/abonar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        pedido_id: this.pedidoAbono.id,
                        monto: this.abonoForm.monto,
                        detalles: this.abonoForm.detalles,
                        metodo_pago: this.abonoForm.detalles ? `${this.abonoForm.metodo_pago} (Ref: ${this.abonoForm.detalles})` : this.abonoForm.metodo_pago
                    })
                });
                
                const data = await res.json();
                if (res.ok) {
                    this.modalAbono = false;
                    this.pagoError = false;
                    this.pagoMsg = "¡Abono registrado exitosamente!";
                    
                    // Refrescar datos
                    await this.fetchPedidosCliente(this.activeClient.id);
                    await this.fetchDeudores();
                } else {
                    alert(data.error || "Error al registrar el abono.");
                }
            } catch (e) {
                console.error("Error al registrar abono:", e);
                alert("Error de red al registrar el abono.");
            } finally {
                this.procesandoAbono = false;
                setTimeout(() => { this.pagoMsg = ''; }, 5000);
            }
        }
    }));
});
