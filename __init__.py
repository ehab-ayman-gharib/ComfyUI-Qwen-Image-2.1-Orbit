from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

try:
    from .viggle_turbo import ViggleTurboSigmas, ViggleTurboLora
    NODE_CLASS_MAPPINGS.setdefault("ViggleTurboSigmas", ViggleTurboSigmas)
    NODE_CLASS_MAPPINGS.setdefault("ViggleTurboLora", ViggleTurboLora)
    NODE_DISPLAY_NAME_MAPPINGS.setdefault("ViggleTurboSigmas", "Qwen-Image-2.1 Viggle Turbo Sigmas")
    NODE_DISPLAY_NAME_MAPPINGS.setdefault("ViggleTurboLora", "Qwen-Image-2.1 Viggle Turbo LoRA (unmerged)")
except Exception as e:
    pass

WEB_DIRECTORY = "./web/js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
