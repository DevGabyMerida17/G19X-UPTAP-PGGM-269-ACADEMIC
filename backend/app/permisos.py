"""Permisos que revisan las rutas de la API.

Qué rol tiene cada permiso NO está en el código: se guarda en las tablas roles, permisos y rol_permisos
(los valores iniciales los crea la migración 0003). Para dar o quitar un permiso a un rol basta con
agregar o borrar su fila en rol_permisos.
"""
ONBOARDING_PROPIO = "onboarding.propio"            # ruta, documentos, capacitación, evaluaciones y Tutor propios
EQUIPO_SEGUIMIENTO = "equipo.seguimiento"          # ver y dar seguimiento a los colaboradores asignados
EVALUACIONES_INTENTO_EXTRA = "evaluaciones.intento_extra"  # conceder un intento más en una evaluación
EVENTOS_TIEMPO_REAL = "eventos.tiempo_real"        # recibir avisos en vivo de los paneles
PANEL_VER = "panel.ver"                            # panel general de onboarding
PERSONAL_GESTIONAR = "personal.gestionar"          # altas, bajas, responsables y contraseñas temporales de todos
CAPACITACION_GESTIONAR = "capacitacion.gestionar"  # programas, módulos y preguntas
DOCUMENTOS_REVISAR = "documentos.revisar"          # ver, validar y rechazar documentos
CONOCIMIENTO_GESTIONAR = "conocimiento.gestionar"  # base de conocimiento del Tutor
ASISTENTE_RH_USAR = "asistente_rh.usar"            # consultar al Asistente de RH
