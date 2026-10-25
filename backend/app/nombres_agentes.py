"""Nombres de los 5 agentes de IA."""

CONOCIMIENTO_GENERAL = "Nova"
TUTOR_ONBOARDING = "Navi"
EVALUADOR = "Vera"
RECOMENDADOR = "Senda"
ASISTENTE_RH = "Omnia"


def todos() -> dict:
    """Para mandarlos al frontend en /api/config."""
    return {
        "conocimiento": CONOCIMIENTO_GENERAL,
        "tutor": TUTOR_ONBOARDING,
        "evaluador": EVALUADOR,
        "recomendador": RECOMENDADOR,
        "asistente_rh": ASISTENTE_RH,
    }
