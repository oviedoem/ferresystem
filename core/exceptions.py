"""
exceptions.py — Excepciones custom de FerreSystem.

Nunca usar sys.exit() dentro del motor. Lanzar estas excepciones
y dejar que el caller (CLI, scheduler, test) decida cómo reaccionar.
"""


class FerreSystemError(Exception):
    """Base para todas las excepciones del sistema."""
    pass


class TenantNotFoundError(FerreSystemError):
    """No existe tenants/{tenant_id}.json."""
    pass


class ERPTypeNotSupportedError(FerreSystemError):
    """erp.tipo no está en ADAPTERS_DISPONIBLES."""
    pass


class ERPConnectionError(FerreSystemError):
    """test_conexion() devolvió False o lanzó excepción."""
    pass


class PipelineLockedError(FerreSystemError):
    """Otra instancia del pipeline está corriendo para este tenant."""
    pass


class ValidationError(FerreSystemError):
    """Los JSONs generados no pasaron la validación post-pipeline."""
    pass


class StagingError(FerreSystemError):
    """Fallo al promover archivos de staging a producción."""
    pass
