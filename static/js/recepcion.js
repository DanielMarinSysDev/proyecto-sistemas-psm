/**
 * TaskCore - Module Recepción Alpine.js Component
 * Lógica del formulario reactivo para creación de clientes, cálculo dinámico de precios y generación de pedidos.
 */

document.addEventListener('alpine:init', () => {
    Alpine.data('recepcionModule', (currentUserId) => ({
        mostrarNuevoCliente: false,
        currentStep: 1,
        currentUserId: parseInt(currentUserId) || 1,
        
        siguientePaso() {
            if (this.currentStep === 1) {
                if (this.ordenForm.articulos.length === 0) {
                    alert("Por favor añada al menos un artículo/dispositivo.");
                    return;
                }
                for (let i = 0; i < this.ordenForm.articulos.length; i++) {
                    const art = this.ordenForm.articulos[i];
                    if (!art.tipo_trabajo) {
                        alert(`Debe seleccionar la categoría para el artículo #${i + 1}.`);
                        return;
                    }
                    if (!art.material) {
                        alert(`Debe seleccionar el servicio/repuesto para el artículo #${i + 1}.`);
                        return;
                    }
                    if (!art.cantidad || art.cantidad < 1) {
                        alert(`La cantidad para el artículo #${i + 1} debe ser mayor o igual a 1.`);
                        return;
                    }
                    if (!art.specs) {
                        alert(`Debe ingresar los detalles y falla para el artículo #${i + 1}.`);
                        return;
                    }
                }
                this.currentStep = 2;
            }
        },
        
        initModule() {
            this.fetchClientes();
            this.generarReferencia();
            this.fetchBCV();
            this.fetchDisenadores();
            this.fetchPrecios();
        },
        
        // Estado de Clientes
        clientesList: [],
        disenadoresList: [],
        preciosList: [],
        clienteForm: { nombre_empresa: '', contacto_nombre: '', email: '', telefono: '' },
        clienteLoading: false,
        clienteError: false,
        clienteMsg: '',
        historicoArticulos: [],
        historicoSeleccionadoId: '',
        
        // Estado de Pedidos
        ordenForm: { 
            cliente_id: '', 
            referencia: '',
            monto_total: '',
            moneda: 'USD',
            tasa_bcv: '',
            tasa_eur_bcv: '',
            estado_pago: 'Por Cancelar',
            monto_abono: '',
            metodo_pago: '',
            notas_pago: '',
            usar_saldo_favor: false,
            ocultar_precio_ventas: false,
            motivo_sin_costo: '',
            articulos: [ {tipo_trabajo: '', material: '', cantidad: 1, specs: '', enlace_recursos: '', disenador_id: '', precio_estimado: 0.0, requiere_cotizacion_especial: false} ] 
        },
        ordenLoading: false,
        ordenError: false,
        ordenMsg: '',
        ordenRuta: '',
        showSuccessModal: false,
        successPublicUrl: '',
        successPedidoId: '',
        
        copiarEnlaceExito() {
            if (!this.successPublicUrl) return;
            const url = window.location.origin + this.successPublicUrl;
            navigator.clipboard.writeText(url);
            alert('¡Copiado al portapapeles!');
        },

        async generarReferencia() {
            try {
                const res = await fetch('/api/siguiente-referencia');
                if(res.ok) {
                    const data = await res.json();
                    this.ordenForm.referencia = data.referencia;
                }
            } catch(e) {
                console.error("Error al obtener la referencia secuencial", e);
            }
        },

        async onClienteChange() {
            const clienteId = this.ordenForm.cliente_id;
            if (!clienteId) {
                this.historicoArticulos = [];
                this.historicoSeleccionadoId = '';
                return;
            }
            
            this.historicoArticulos = [];
            this.historicoSeleccionadoId = '';
            
            try {
                const res = await fetch(`/api/clientes/${clienteId}/historico-articulos`);
                if (res.ok) {
                    this.historicoArticulos = await res.json();
                }
            } catch(e) {
                console.error("Error al obtener histórico", e);
            }
        },

        cargarTrabajoHistorico() {
            if (!this.historicoSeleccionadoId) {
                alert("Por favor seleccione un trabajo anterior.");
                return;
            }
            const artPrevio = this.historicoArticulos.find(a => a.id == this.historicoSeleccionadoId);
            if (!artPrevio) return;
            
            const nuevoArt = {
                tipo_trabajo: '',
                material: '',
                cantidad: 1,
                specs: artPrevio.especificaciones || '',
                enlace_recursos: '',
                disenador_id: artPrevio.disenador_id || '',
                precio_estimado: 0.0,
                requiere_cotizacion_especial: false,
                duplicar_de_articulo_id: artPrevio.id,
                nombre_proyecto_manual: artPrevio.nombre_proyecto
            };
            
            if (this.ordenForm.articulos.length === 1 && !this.ordenForm.articulos[0].tipo_trabajo && !this.ordenForm.articulos[0].specs) {
                this.ordenForm.articulos[0] = nuevoArt;
            } else {
                this.ordenForm.articulos.push(nuevoArt);
            }
            
            alert(`¡Detalles de "${artPrevio.nombre_proyecto}" cargados en la orden!`);
        },
        
        agregarArticulo() {
            this.ordenForm.articulos.push({tipo_trabajo: '', material: '', cantidad: 1, specs: '', enlace_recursos: '', disenador_id: '', precio_estimado: 0.0, requiere_cotizacion_especial: false});
        },
        
        eliminarArticulo(index) {
            this.ordenForm.articulos.splice(index, 1);
            this.actualizarMontoTotal();
        },

        async recalcularPrecio(index) {
            const art = this.ordenForm.articulos[index];
            if (art.requiere_cotizacion_especial) {
                art.precio_estimado = 0.0;
                this.actualizarMontoTotal();
                return;
            }
            if (!art.tipo_trabajo || !art.material) {
                art.precio_estimado = 0.0;
                this.actualizarMontoTotal();
                return;
            }
            try {
                const res = await fetch('/api/precios/calcular', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        tipo_trabajo: art.tipo_trabajo,
                        material: art.material,
                        cantidad: art.cantidad
                    })
                });
                if (res.ok) {
                    const data = await res.json();
                    art.precio_estimado = data.subtotal || 0.0;
                } else {
                    art.precio_estimado = 0.0;
                }
            } catch(e) {
                console.error("Error al calcular el precio del artículo", e);
                art.precio_estimado = 0.0;
            }
            this.actualizarMontoTotal();
        },

        actualizarMontoTotal() {
            let total = 0.0;
            this.ordenForm.articulos.forEach(art => {
                total += parseFloat(art.precio_estimado || 0.0);
            });
            this.ordenForm.monto_total = total > 0 ? total.toFixed(2) : '';
        },
        async fetchDisenadores() {
            try {
                const res = await fetch('/api/disenadores');
                if(res.ok) {
                    this.disenadoresList = await res.json();
                }
            } catch(e) {
                console.error("Error al cargar diseñadores", e);
            }
        },
        
        async fetchClientes() {
            try {
                const res = await fetch('/api/clientes');
                if(res.ok) {
                    this.clientesList = await res.json();
                }
            } catch(e) {
                console.error("Error al cargar clientes", e);
            }
        },
        
        async fetchBCV() {
            try {
                const res = await fetch('/api/bcv');
                if(res.ok) {
                    const data = await res.json();
                    if(data.tasa) {
                        this.ordenForm.tasa_bcv = data.tasa;
                    }
                    if(data.tasa_eur) {
                        this.ordenForm.tasa_eur_bcv = data.tasa_eur;
                    }
                }
            } catch(e) {
                console.error("Error al obtener la tasa del BCV", e);
            }
        },
        
        async fetchPrecios() {
            try {
                const res = await fetch('/api/precios/listar');
                if(res.ok) {
                    this.preciosList = await res.json();
                }
            } catch(e) {
                console.error("Error al cargar tarifas", e);
            }
        },
        
        getMaterialesDisponibles(tipoTrabajo) {
            if (!tipoTrabajo || !this.preciosList) return [];
            let items = this.preciosList.filter(p => p.tipo_trabajo === tipoTrabajo && !p.es_adicional);
            return [...new Set(items.map(p => p.material))];
        },
        
        async submitCliente() {
            this.clienteLoading = true;
            this.clienteMsg = '';
            try {
                const res = await fetch('/api/clientes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.clienteForm)
                });
                const data = await res.json();
                
                if(res.ok) {
                    this.clienteError = false;
                    this.clienteMsg = `Cliente registrado (Master Data creada en ${data.ruta_master_data})`;
                    this.clienteForm = { nombre_empresa: '', contacto_nombre: '', email: '', telefono: '' };
                    this.fetchClientes();
                    setTimeout(() => { this.mostrarNuevoCliente = false; this.clienteMsg = ''; }, 2500);
                } else {
                    this.clienteError = true;
                    this.clienteMsg = data.error;
                }
            } catch(e) {
                this.clienteError = true;
                this.clienteMsg = "Error de conexión";
            } finally {
                this.clienteLoading = false;
            }
        },
        
        async submitOrden(esBorrador = false) {
            if (!esBorrador) {
                for (let i = 0; i < this.ordenForm.articulos.length; i++) {
                    const art = this.ordenForm.articulos[i];
                    if (!art.tipo_trabajo) {
                        alert(`Debe seleccionar la categoría para el artículo #${i + 1}.`);
                        this.currentStep = 1;
                        return;
                    }
                    if (!art.material) {
                        alert(`Debe seleccionar el servicio/repuesto para el artículo #${i + 1}.`);
                        this.currentStep = 1;
                        return;
                    }
                    if (!art.cantidad || art.cantidad < 1) {
                        alert(`La cantidad para el artículo #${i + 1} debe ser mayor o igual a 1.`);
                        this.currentStep = 1;
                        return;
                    }
                    if (!art.specs) {
                        alert(`Debe ingresar los detalles y falla para el artículo #${i + 1}.`);
                        this.currentStep = 1;
                        return;
                    }
                }
                if (!this.ordenForm.cliente_id) {
                    alert("Por favor seleccione un cliente.");
                    this.currentStep = 2;
                    return;
                }
            }
            
            this.ordenLoading = true;
            this.ordenMsg = '';
            this.ordenRuta = '';
            try {
                const res = await fetch('/api/ordenes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        cliente_id: this.ordenForm.cliente_id,
                        creador_id: this.currentUserId,
                        referencia: this.ordenForm.referencia,
                        monto_total: this.ordenForm.monto_total ? parseFloat(this.ordenForm.monto_total) : null,
                        moneda: this.ordenForm.moneda,
                        tasa_bcv: this.ordenForm.tasa_bcv ? parseFloat(this.ordenForm.tasa_bcv) : null,
                        tasa_eur_bcv: this.ordenForm.tasa_eur_bcv ? parseFloat(this.ordenForm.tasa_eur_bcv) : null,
                        estado_pago: this.ordenForm.estado_pago,
                        monto_abono: this.ordenForm.estado_pago === 'Abono' 
                            ? (this.ordenForm.notas_pago ? `${this.ordenForm.monto_abono} (${this.ordenForm.notas_pago})` : this.ordenForm.monto_abono) 
                            : (this.ordenForm.estado_pago === 'Cancelado' ? `Cancelado (${this.ordenForm.notas_pago || 'Pago completo'})` : ''),
                        metodo_pago: (this.ordenForm.estado_pago !== 'Por Cancelar' && this.ordenForm.notas_pago)
                            ? `${this.ordenForm.metodo_pago} (Ref: ${this.ordenForm.notas_pago})` 
                            : this.ordenForm.metodo_pago,
                        usar_saldo_favor: this.ordenForm.usar_saldo_favor,
                        es_borrador: esBorrador,
                        ocultar_precio_ventas: this.ordenForm.ocultar_precio_ventas,
                        motivo_sin_costo: this.ordenForm.motivo_sin_costo || '',
                        articulos: this.ordenForm.articulos
                    })
                });
                const data = await res.json();
                
                if(res.ok) {
                    this.ordenError = false;
                    if (esBorrador) {
                        this.ordenMsg = `¡Borrador de Pedido #${data.pedido_id} guardado con éxito!`;
                    } else {
                        this.ordenMsg = `¡Pedido #${data.pedido_id} generado con éxito (${data.articulos_creados} artículos)!`;
                        this.successPublicUrl = data.public_url || '';
                        this.successPedidoId = data.pedido_id || '';
                        this.showSuccessModal = true;
                    }
                    this.ordenRuta = data.ruta_archivos;
                    this.ordenForm = { cliente_id: '', referencia: '', monto_total: '', moneda: 'USD', tasa_bcv: '', tasa_eur_bcv: '', estado_pago: 'Por Cancelar', monto_abono: '', metodo_pago: '', notas_pago: '', usar_saldo_favor: false, ocultar_precio_ventas: false, motivo_sin_costo: '', articulos: [ {tipo_trabajo: '', material: '', cantidad: 1, specs: '', enlace_recursos: '', disenador_id: '', precio_estimado: 0.0, requiere_cotizacion_especial: false} ] };
                    this.currentStep = 1;
                } else {
                    this.ordenError = true;
                    this.ordenMsg = data.error;
                }
            } catch(e) {
                this.ordenError = true;
                this.ordenMsg = "Error de conexión";
            } finally {
                this.ordenLoading = false;
            }
        },
        
        abrirCarpetaEnServidor(ruta) {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(ruta).catch(() => {});
            }
            const utf8Ruta = unescape(encodeURIComponent(ruta));
            const rutaCodificada = btoa(utf8Ruta);
            window.location.href = `taskcore://${rutaCodificada}?server=${window.location.hostname}`;
        }
    }));
});
