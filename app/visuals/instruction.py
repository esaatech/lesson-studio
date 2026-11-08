"""The visual system instruction is the saved rules plus the live component catalog."""

from app.visuals.components import component_catalog


def build_visual_instruction(rules: str, kind: str | None = None) -> str:
    return (
        rules.strip()
        + "\n\n"
        + component_catalog(kind)
        + "\n\nReturn one component and its settings. Do not return HTML or an end state."
        + " Do not choose a component from another beat kind."
    )
