"""Qwen-Image-2.1 Viewpoint Orbit LoRA Nodes for ComfyUI.
Replicates camera angle / elevation selection and prompt generation from
ML-Intern-lab/Qwen-Image-2.1-viewpoint-orbit-LoRA.
"""

import os
import random
import shutil
import subprocess
import torch
import torch.nn.functional as F
import numpy as np
from PIL import Image
import folder_paths

MOVES = [
    "45 left",
    "90 left",
    "135 left",
    "180",
    "135 right",
    "90 right",
    "45 right",
    "keep angle",
]

ELEVATIONS = [
    "low angle",
    "eye level",
    "elevated",
]

DEFAULT_SUFFIX = ". The image has alpha channel and the background is transparent."


def build_orbit_instruction(move: str, elevation: str) -> str:
    """Build one of the 23 training instructions matching the official Gradio app."""
    if move == "keep angle":
        if elevation == "eye level":
            return "<orbit> keep the camera angle, eye level"
        return f"<orbit> keep the camera angle, {elevation}"
    if move == "180":
        return f"<orbit> rotate the camera 180 degrees, {elevation}"
    parts = (move or "").strip().split()
    if len(parts) >= 2:
        deg, side = parts[0], parts[1]
        return f"<orbit> rotate the camera {deg} degrees to the {side}, {elevation}"
    return f"<orbit> rotate the camera {move}, {elevation}"


MODES = [
    "Full Turntable 360",
    "Patch Single Frame",
    "Single View",
]

TURNTABLE_8_MOVES = [
    "keep angle",
    "45 right",
    "90 right",
    "135 right",
    "180",
    "135 left",
    "90 left",
    "45 left",
]

TURNTABLE_MOVES = TURNTABLE_8_MOVES

ANGLE_TO_SLOT_8 = {
    "keep angle": 0,
    "0": 0,
    "0°": 0,
    "front": 0,
    "45 right": 1,
    "90 right": 2,
    "135 right": 3,
    "180": 4,
    "135 left": 5,
    "90 left": 6,
    "45 left": 7,
}


class QwenOrbitPrompt:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (MODES, {
                    "default": "Full Turntable 360",
                    "tooltip": "Turntable mode: 'Full Turntable 360' generates all 8 seamless unified views. 'Patch Single Frame' generates only the selected camera_angle and surgically replaces that slot in the saved turntable. 'Single View' generates 1 standalone view without turntable buffering."
                }),
                "camera_angle": (MOVES, {"default": "keep angle", "tooltip": "Rotate camera degrees relative to the input image view. In 'Patch Single Frame' or 'Single View', this specifies which angle is generated."}),
                "camera_elevation": (ELEVATIONS, {"default": "eye level", "tooltip": "Camera elevation: low angle (~ -20°), eye level (0°), elevated (~ +40°)."}),
                "include_suffix": ("BOOLEAN", {"default": True, "tooltip": "Append the verified training suffix for alpha channel and transparent background."}),
            },
            "optional": {
                "custom_prefix": ("STRING", {"default": "", "multiline": False, "placeholder": "Optional object description (e.g. 'a vintage brass clock, ')"}),
                "custom_suffix": ("STRING", {"default": DEFAULT_SUFFIX, "multiline": True}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("prompt", "angle", "elevation", "display_info")
    OUTPUT_IS_LIST = (True, False, False, False)
    FUNCTION = "build_prompt"
    CATEGORY = "QwenImage21/prompt"
    DESCRIPTION = "Formats viewpoint orbit prompts for Qwen-Image-2.1 Orbit LoRA. Supports Full Turntable 360 (all 8 views), Patch Single Frame (surgical slot replacement), and Single View."

    def build_prompt(
        self,
        mode="Full Turntable 360",
        camera_angle="keep angle",
        camera_elevation="eye level",
        include_suffix=True,
        custom_prefix="",
        custom_suffix=DEFAULT_SUFFIX,
        **kwargs
    ):
        # Defensive unwrapping of parameters
        if isinstance(mode, (list, tuple)) and len(mode) > 0:
            mode = mode[0]
        if isinstance(camera_angle, (list, tuple)) and len(camera_angle) > 0:
            camera_angle = camera_angle[0]
        if isinstance(camera_elevation, (list, tuple)) and len(camera_elevation) > 0:
            camera_elevation = camera_elevation[0]
        if isinstance(include_suffix, (list, tuple)) and len(include_suffix) > 0:
            include_suffix = include_suffix[0]

        # Handle legacy positional arguments or old workflows
        if mode in MOVES:
            camera_angle = mode
            mode = "Full Turntable 360" if kwargs.get("turntable_7_views") else "Single View"

        mode_str = str(mode).lower() if mode else ""
        if "360" in mode_str or "turntable" in mode_str:
            clean_mode = "Full Turntable 360"
        elif "patch" in mode_str:
            clean_mode = "Patch Single Frame"
        else:
            clean_mode = "Single View"

        include_suffix = bool(include_suffix)

        pref = custom_prefix.strip() if isinstance(custom_prefix, str) else ""
        suff = custom_suffix if isinstance(custom_suffix, str) else DEFAULT_SUFFIX

        def format_single(move):
            instruction = build_orbit_instruction(move, camera_elevation)
            full_inst = f"{pref} {instruction}" if pref else instruction
            if include_suffix and suff:
                return full_inst + suff
            return full_inst

        if clean_mode == "Full Turntable 360":
            prompts = [format_single(m) for m in TURNTABLE_8_MOVES]
            angle_str = "turntable_8_views"
            info = f"Mode: Full Turntable 360 (8 Unified Views) | Elevation: {camera_elevation}"
        elif clean_mode == "Patch Single Frame":
            prompts = [format_single(camera_angle)]
            angle_str = f"patch_{camera_angle}"
            info = f"Mode: Patch Single Frame ({camera_angle}) | Elevation: {camera_elevation}"
        else: # "Single View"
            prompts = [format_single(camera_angle)]
            angle_str = camera_angle
            info = f"Mode: Single View | Angle: {camera_angle} | Elevation: {camera_elevation}"

        return (prompts, angle_str, camera_elevation, info)




class QwenOrbitTurntablePrompts:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "camera_elevation": (ELEVATIONS, {"default": "eye level"}),
                "include_suffix": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "generate_front_0deg": ("BOOLEAN", {"default": True, "tooltip": "Generate 8 views (including 0° front view via 'keep angle') for a completely unified 360° orbit."}),
                "custom_prefix": ("STRING", {"default": "", "multiline": False}),
                "custom_suffix": ("STRING", {"default": DEFAULT_SUFFIX, "multiline": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    OUTPUT_IS_LIST = (True,)
    RETURN_NAMES = ("prompts",)
    FUNCTION = "build_turntable_prompts"
    CATEGORY = "QwenImage21/prompt"
    DESCRIPTION = "Outputs a list of 7 or 8 prompts for full 360-degree turntable orbit around the original image."

    def build_turntable_prompts(self, camera_elevation, include_suffix=True, generate_front_0deg=True, custom_prefix="", custom_suffix=DEFAULT_SUFFIX):
        if isinstance(generate_front_0deg, (list, tuple)) and len(generate_front_0deg) > 0:
            generate_front_0deg = generate_front_0deg[0]
        generate_front_0deg = bool(generate_front_0deg)

        if generate_front_0deg:
            moves = ["keep angle"] + TURNTABLE_MOVES
        else:
            moves = TURNTABLE_MOVES

        prompts = []
        for m in moves:
            instruction = build_orbit_instruction(m, camera_elevation)
            if custom_prefix and custom_prefix.strip():
                full_inst = f"{custom_prefix.strip()} {instruction}"
            else:
                full_inst = instruction
            if include_suffix and custom_suffix:
                prompts.append(full_inst + custom_suffix)
            else:
                prompts.append(full_inst)
        return (prompts,)


class QwenOrbitCanvasPrep:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "target_size": ("INT", {"default": 768, "min": 256, "max": 2048, "step": 64}),
            },
            "optional": {
                "mask": ("MASK",),
            }
        }

    RETURN_TYPES = ("IMAGE", "MASK", "STRING")
    RETURN_NAMES = ("image", "mask", "alpha_coverage")
    FUNCTION = "fit_canvas"
    CATEGORY = "QwenImage21/image"
    DESCRIPTION = "Fits image into a square transparent canvas without distortion, matching the official 768x768 RGBA prep function."

    def fit_canvas(self, image, target_size=768, mask=None):
        # image is [B, H, W, C]
        b, h, w, c = image.shape
        scale = target_size / max(w, h)
        new_w = max(1, round(w * scale))
        new_h = max(1, round(h * scale))

        # Permute to [B, C, H, W] for interpolate
        x = image.permute(0, 3, 1, 2)
        if scale != 1.0:
            x = F.interpolate(x, size=(new_h, new_w), mode="bilinear", align_corners=False)

        # Create square canvas
        canvas = torch.zeros((b, c, target_size, target_size), dtype=x.dtype, device=x.device)
        pad_x = (target_size - new_w) // 2
        pad_y = (target_size - new_h) // 2
        canvas[:, :, pad_y : pad_y + new_h, pad_x : pad_x + new_w] = x
        out_image = canvas.permute(0, 2, 3, 1)

        # Handle mask
        if mask is not None:
            m = mask.unsqueeze(1) if mask.ndim == 3 else mask
            if scale != 1.0:
                m = F.interpolate(m, size=(new_h, new_w), mode="bilinear", align_corners=False)
            canvas_m = torch.zeros((b, 1, target_size, target_size), dtype=m.dtype, device=m.device)
            canvas_m[:, :, pad_y : pad_y + new_h, pad_x : pad_x + new_w] = m
            out_mask = canvas_m.squeeze(1)
            coverage = float((out_mask > 0.03).sum() / (out_mask.shape[-1] * out_mask.shape[-2]))
        else:
            if c >= 4:
                alpha = out_image[..., 3]
                out_mask = alpha
                coverage = float((alpha > 0.03).sum() / (alpha.shape[-1] * alpha.shape[-2]))
            else:
                out_mask = torch.ones((b, target_size, target_size), dtype=image.dtype, device=image.device)
                coverage = 1.0

        stats = f"Alpha coverage: {coverage:.1%}"
        return (out_image, out_mask, stats)


def get_turntable_session_dir():
    temp_dir = folder_paths.get_temp_directory()
    session_dir = os.path.join(temp_dir, "qwen_turntable_session")
    os.makedirs(session_dir, exist_ok=True)
    return session_dir


def save_turntable_session(frames, labels, angles):
    import json
    try:
        session_dir = get_turntable_session_dir()
        for idx, frame in enumerate(frames):
            arr = (255.0 * frame.cpu().numpy()).clip(0, 255).astype(np.uint8)
            img = Image.fromarray(arr)
            img.save(os.path.join(session_dir, f"slot_{idx:02d}.png"), compress_level=1)

        meta = {
            "num_frames": len(frames),
            "labels": labels,
            "angles": angles,
            "shape": list(frames[0].shape) if len(frames) > 0 else []
        }
        with open(os.path.join(session_dir, "session_meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
    except Exception as e:
        print(f"[QwenTurntable360Viewer] Warning: Failed to save turntable session buffer: {e}")


def load_turntable_session():
    import json
    session_dir = get_turntable_session_dir()
    meta_path = os.path.join(session_dir, "session_meta.json")
    if not os.path.exists(meta_path):
        return None, None, None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        num_frames = meta.get("num_frames", 0)
        labels = meta.get("labels", [])
        angles = meta.get("angles", [])
        if num_frames == 0:
            return None, None, None
        frames = []
        for idx in range(num_frames):
            slot_file = os.path.join(session_dir, f"slot_{idx:02d}.png")
            if not os.path.exists(slot_file):
                return None, None, None
            img = Image.open(slot_file)
            arr = np.array(img).astype(np.float32) / 255.0
            frames.append(torch.from_numpy(arr))
        return frames, labels, angles
    except Exception as e:
        print(f"[QwenTurntable360Viewer] Warning: Error reading session buffer: {e}")
        return None, None, None


class QwenTurntable360Viewer:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "orbit_images": ("IMAGE",),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO"
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    OUTPUT_NODE = True
    INPUT_IS_LIST = True
    FUNCTION = "display_turntable"
    CATEGORY = "QwenImage21/image"
    DESCRIPTION = "Interactive 360-degree turntable viewer with orbit ring scrubbing, camera indicator, and surgical frame replacement."

    def display_turntable(self, orbit_images, prompt=None, extra_pnginfo=None, **kwargs):
        import numpy as np
        from PIL import Image

        temp_dir = folder_paths.get_temp_directory()
        os.makedirs(temp_dir, exist_ok=True)
        prefix = "qwen_turntable_" + "".join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(5))

        # Flatten all orbit images from input list/batch
        all_orbit_tensors = []
        if isinstance(orbit_images, (list, tuple)):
            for item in orbit_images:
                if item is not None and isinstance(item, torch.Tensor):
                    for b in range(item.shape[0]):
                        all_orbit_tensors.append(item[b:b+1])
        elif isinstance(orbit_images, torch.Tensor):
            for b in range(orbit_images.shape[0]):
                all_orbit_tensors.append(orbit_images[b:b+1])

        # Unwrap hidden inputs when INPUT_IS_LIST = True
        if isinstance(prompt, (list, tuple)) and len(prompt) > 0:
            prompt = prompt[0]
        if isinstance(extra_pnginfo, (list, tuple)) and len(extra_pnginfo) > 0:
            extra_pnginfo = extra_pnginfo[0]

        # Inspect prompt context for mode and target camera angle
        mode_val = None
        target_angle = None
        if prompt is not None and isinstance(prompt, dict):
            for node_data in prompt.values():
                if isinstance(node_data, dict) and node_data.get("class_type") == "QwenOrbitPrompt":
                    inputs = node_data.get("inputs", {})
                    mode_val = inputs.get("mode")
                    target_angle = inputs.get("camera_angle")
                    if isinstance(mode_val, (list, tuple)) and len(mode_val) > 0:
                        mode_val = mode_val[0]
                    if isinstance(target_angle, (list, tuple)) and len(target_angle) > 0:
                        target_angle = target_angle[0]
                    if mode_val is None and inputs.get("turntable_7_views") is not None:
                        t7 = inputs.get("turntable_7_views")
                        if isinstance(t7, (list, tuple)) and len(t7) > 0:
                            t7 = t7[0]
                        mode_val = "Full 360° Turntable (8 Views)" if t7 else "Single View (Standalone)"
                    break

        is_patch_mode = (mode_val == "Patch Single Frame" and len(all_orbit_tensors) == 1)

        frames = []
        labels = []
        angles = []

        # ---------------------------------------------------------------------
        # Case A: Surgical Single Frame Patching
        # ---------------------------------------------------------------------
        if is_patch_mode:
            target_slot = None
            if target_angle:
                norm_angle = str(target_angle).strip().lower()
                target_slot = ANGLE_TO_SLOT_8.get(norm_angle)
                if target_slot is None:
                    if "180" in norm_angle:
                        target_slot = 4
                    elif "keep" in norm_angle or "front" in norm_angle or "0" in norm_angle:
                        target_slot = 0
                    elif "135" in norm_angle and "right" in norm_angle:
                        target_slot = 3
                    elif "90" in norm_angle and "right" in norm_angle:
                        target_slot = 2
                    elif "45" in norm_angle and "right" in norm_angle:
                        target_slot = 1
                    elif "135" in norm_angle and "left" in norm_angle:
                        target_slot = 5
                    elif "90" in norm_angle and "left" in norm_angle:
                        target_slot = 6
                    elif "45" in norm_angle and "left" in norm_angle:
                        target_slot = 7

            session_frames, session_labels, session_angles = load_turntable_session()
            if session_frames is not None and len(session_frames) >= 8 and target_slot is not None and target_slot < len(session_frames):
                new_frame = all_orbit_tensors[0][0]
                # Match channel depth with session
                if new_frame.shape[-1] != session_frames[0].shape[-1]:
                    if new_frame.shape[-1] == 3 and session_frames[0].shape[-1] == 4:
                        new_frame = torch.cat([new_frame, torch.ones((*new_frame.shape[:-1], 1), dtype=new_frame.dtype, device=new_frame.device)], dim=-1)
                    elif new_frame.shape[-1] == 4 and session_frames[0].shape[-1] == 3:
                        new_frame = new_frame[..., :3]

                # Match spatial resolution if needed
                if new_frame.shape[:2] != session_frames[0].shape[:2]:
                    new_frame = F.interpolate(
                        new_frame.permute(2, 0, 1).unsqueeze(0),
                        size=session_frames[0].shape[:2],
                        mode="bilinear",
                        align_corners=False
                    ).squeeze(0).permute(1, 2, 0)

                session_frames[target_slot] = new_frame
                orig_label = session_labels[target_slot].replace(" (Patched)", "")
                session_labels[target_slot] = f"{orig_label} (Patched)"

                save_turntable_session(session_frames, session_labels, session_angles)
                frames = session_frames
                labels = session_labels
                angles = session_angles
                print(f"[QwenTurntable360Viewer] [PATCHED] Surgically patched slot {target_slot} ('{target_angle}') in 8-view turntable session.")
            else:
                print(f"[QwenTurntable360Viewer] Notice: 'Patch Single Frame' requested for '{target_angle}', but no active 8-frame session buffer exists. Displaying as standalone single view.")
                frames = [all_orbit_tensors[0][0]]
                lbl = str(target_angle) if target_angle else "Novel View"
                labels = [f"{lbl} (No prior session)"]
                angles = [lbl.replace("right", "R").replace("left", "L").replace(" ", "")]

        # ---------------------------------------------------------------------
        # Case B: Exactly 8 frames generated by model (Full 360° Unified Orbit)
        # ---------------------------------------------------------------------
        elif len(all_orbit_tensors) == 8:
            canonical_labels_8 = [
                ("0° (Generated)", "0°"),
                ("45° right", "45° R"),
                ("90° right", "90° R"),
                ("135° right", "135° R"),
                ("180°", "180°"),
                ("135° left", "135° L"),
                ("90° left", "90° L"),
                ("45° left", "45° L"),
            ]
            for idx, orbit_t in enumerate(all_orbit_tensors):
                lbl, short_lbl = canonical_labels_8[idx]
                if len(frames) > 0 and orbit_t.shape[-1] != frames[0].shape[-1]:
                    if orbit_t.shape[-1] == 3 and frames[0].shape[-1] == 4:
                        orbit_t = torch.cat([orbit_t, torch.ones((*orbit_t.shape[:-1], 1), dtype=orbit_t.dtype, device=orbit_t.device)], dim=-1)
                    elif orbit_t.shape[-1] == 4 and frames[0].shape[-1] == 3:
                        orbit_t = orbit_t[..., :3]
                frames.append(orbit_t[0])
                labels.append(lbl)
                angles.append(short_lbl)

            save_turntable_session(frames, labels, angles)
            print(f"[QwenTurntable360Viewer] [SESSION] Saved 8-frame turntable session buffer.")

        # ---------------------------------------------------------------------
        # Case C: Single standalone view, or legacy 7 views
        # ---------------------------------------------------------------------
        else:
            canonical_labels_7 = [
                ("45° right", "45° R"),
                ("90° right", "90° R"),
                ("135° right", "135° R"),
                ("180°", "180°"),
                ("135° left", "135° L"),
                ("90° left", "90° L"),
                ("45° left", "45° L"),
            ]

            for idx, orbit_t in enumerate(all_orbit_tensors):
                if len(all_orbit_tensors) == 7:
                    lbl, short_lbl = canonical_labels_7[idx]
                elif len(all_orbit_tensors) == 1:
                    lbl = target_angle if target_angle else "Rotated View"
                    short_lbl = target_angle.replace("right", "R").replace("left", "L").replace(" ", "") if target_angle else "Target"
                else:
                    lbl = f"View {idx+1}"
                    short_lbl = f"V{idx+1}"

                if len(frames) > 0 and orbit_t.shape[-1] != frames[0].shape[-1]:
                    if orbit_t.shape[-1] == 3 and frames[0].shape[-1] == 4:
                        orbit_t = torch.cat([orbit_t, torch.ones((*orbit_t.shape[:-1], 1), dtype=orbit_t.dtype, device=orbit_t.device)], dim=-1)
                    elif orbit_t.shape[-1] == 4 and frames[0].shape[-1] == 3:
                        orbit_t = orbit_t[..., :3]

                frames.append(orbit_t[0])
                labels.append(lbl)
                angles.append(short_lbl)

            if len(frames) >= 7:
                save_turntable_session(frames, labels, angles)
                print(f"[QwenTurntable360Viewer] [SESSION] Saved {len(frames)}-frame turntable session buffer.")

        results = []
        for i, frame in enumerate(frames):
            arr = (255.0 * frame.cpu().numpy()).clip(0, 255).astype(np.uint8)
            img = Image.fromarray(arr)
            filename = f"{prefix}_{i:02d}.png"
            img.save(os.path.join(temp_dir, filename), compress_level=1)
            results.append({
                "filename": filename,
                "subfolder": "",
                "type": "temp",
                "label": labels[i],
                "angle": angles[i],
                "index": i
            })

        out_tensor = torch.stack(frames, dim=0) if len(frames) > 0 else torch.zeros((1, 64, 64, 3))
        return {
            "ui": {
                "images": results,
            },
            "result": (out_tensor,)
        }



def get_ffmpeg_path():
    p = shutil.which("ffmpeg")
    if p:
        return p
    for candidate in [
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        os.path.expanduser(r"~\ffmpeg\bin\ffmpeg.exe"),
    ]:
        if os.path.exists(candidate):
            return candidate
    return "ffmpeg"


class QwenTurntableExport:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "filename_prefix": ("STRING", {"default": "Qwen_Turntable"}),
                "fps": ("FLOAT", {"default": 2.5, "min": 0.5, "max": 60.0, "step": 0.5, "tooltip": "Playback framerate in FPS (2.5 fps = 400ms per frame)."}),
                "export_mp4": ("BOOLEAN", {"default": True, "tooltip": "Export looping 360 turntable as MP4 video (H.264)."}),
                "export_webp": ("BOOLEAN", {"default": True, "tooltip": "Export looping 360 turntable as animated WEBP (with transparent alpha)."}),
                "export_frames": ("BOOLEAN", {"default": True, "tooltip": "Export individual angle frames as separate PNG files (with transparent alpha)."}),
                "mp4_background": (["dark", "white", "black", "gray"], {"default": "dark", "tooltip": "Background color for MP4 (since MP4 container does not support alpha channel)."}),
                "loop_count": ("INT", {"default": 2, "min": 1, "max": 10, "tooltip": "Number of complete 360 loops in the exported MP4 video."}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO"
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    OUTPUT_NODE = True
    INPUT_IS_LIST = True
    FUNCTION = "export_media"
    CATEGORY = "QwenImage21/export"
    DESCRIPTION = "Exports turntable 360 renders to MP4 video (H.264), animated WEBP, and individual separate PNG frames."

    def export_media(self, images, filename_prefix="Qwen_Turntable", fps=2.5, export_mp4=True, export_webp=True, export_frames=True, mp4_background="dark", loop_count=2, prompt=None, extra_pnginfo=None):
        # When INPUT_IS_LIST = True, ComfyUI passes all inputs as lists
        if isinstance(filename_prefix, (list, tuple)) and len(filename_prefix) > 0:
            filename_prefix = filename_prefix[0]
        if isinstance(fps, (list, tuple)) and len(fps) > 0:
            fps = fps[0]
        if isinstance(export_mp4, (list, tuple)) and len(export_mp4) > 0:
            export_mp4 = export_mp4[0]
        if isinstance(export_webp, (list, tuple)) and len(export_webp) > 0:
            export_webp = export_webp[0]
        if isinstance(export_frames, (list, tuple)) and len(export_frames) > 0:
            export_frames = export_frames[0]
        if isinstance(mp4_background, (list, tuple)) and len(mp4_background) > 0:
            mp4_background = mp4_background[0]
        if isinstance(loop_count, (list, tuple)) and len(loop_count) > 0:
            loop_count = loop_count[0]

        # Safe string & numeric coercion
        filename_prefix = str(filename_prefix or "Qwen_Turntable")
        fps = float(fps or 2.5)
        export_mp4 = bool(export_mp4)
        export_webp = bool(export_webp)
        export_frames = bool(export_frames)
        mp4_background = str(mp4_background or "dark")
        loop_count = int(loop_count or 2)

        all_tensors = []
        if isinstance(images, (list, tuple)):
            for item in images:
                if item is not None and isinstance(item, torch.Tensor):
                    for b in range(item.shape[0]):
                        all_tensors.append(item[b:b+1])
        elif isinstance(images, torch.Tensor):
            for b in range(images.shape[0]):
                all_tensors.append(images[b:b+1])

        if len(all_tensors) == 0:
            return {"ui": {"images": []}, "result": (torch.zeros((1, 64, 64, 3)),)}

        out_tensor = torch.cat(all_tensors, dim=0)
        H, W = out_tensor.shape[1], out_tensor.shape[2]

        output_dir = folder_paths.get_output_directory()
        full_output_folder, filename, counter, subfolder, filename_prefix = folder_paths.get_save_image_path(
            filename_prefix, output_dir, W, H
        )

        # Dynamic tags: 8 frames (reference + 7 novel) vs 7 frames (novel only)
        if len(all_tensors) >= 8:
            canonical_tags = [
                "00_front_0deg",
                "01_right_45deg",
                "02_right_90deg",
                "03_right_135deg",
                "04_back_180deg",
                "05_left_135deg",
                "06_left_90deg",
                "07_left_45deg",
            ]
        else:
            canonical_tags = [
                "01_right_45deg",
                "02_right_90deg",
                "03_right_135deg",
                "04_back_180deg",
                "05_left_135deg",
                "06_left_90deg",
                "07_left_45deg",
            ]

        pil_frames = []
        np_frames = []
        for t in all_tensors:
            arr = (255.0 * t[0].cpu().numpy()).clip(0, 255).astype(np.uint8)
            np_frames.append(arr)
            pil_frames.append(Image.fromarray(arr))

        ui_results = []

        # 1. Export Separate PNG Frames
        if export_frames:
            for i, p_img in enumerate(pil_frames):
                tag = canonical_tags[i] if i < len(canonical_tags) else f"frame_{i:02d}"
                f_name = f"{filename}_{counter:05}_{tag}.png"
                f_path = os.path.join(full_output_folder, f_name)
                p_img.save(f_path, compress_level=2)
                ui_results.append({
                    "filename": f_name,
                    "subfolder": subfolder,
                    "type": "output"
                })

        # 2. Export Animated WEBP
        if export_webp and len(pil_frames) > 0:
            webp_name = f"{filename}_{counter:05}_turntable.webp"
            webp_path = os.path.join(full_output_folder, webp_name)
            duration_ms = max(20, int(1000.0 / max(0.1, fps)))
            pil_frames[0].save(
                webp_path,
                format="WEBP",
                save_all=True,
                append_images=pil_frames[1:],
                duration=duration_ms,
                loop=0,
                lossless=True
            )
            # If individual frames are not being exported, preview the animated WEBP in the UI
            if not export_frames:
                ui_results.append({
                    "filename": webp_name,
                    "subfolder": subfolder,
                    "type": "output",
                    "format": "image/webp"
                })

        # 3. Export MP4 Video via FFmpeg
        if export_mp4 and len(np_frames) > 0:
            mp4_name = f"{filename}_{counter:05}_turntable.mp4"
            mp4_path = os.path.join(full_output_folder, mp4_name)

            bg_colors = {
                "dark": (20, 23, 29),
                "white": (255, 255, 255),
                "black": (0, 0, 0),
                "gray": (128, 128, 128),
            }
            bg_rgb = bg_colors.get(mp4_background, (20, 23, 29))

            composited_rgb = []
            for arr in np_frames:
                if arr.shape[-1] == 4:
                    rgb = arr[:, :, :3].astype(np.float32)
                    alpha = arr[:, :, 3:4].astype(np.float32) / 255.0
                    bg = np.array(bg_rgb, dtype=np.float32)
                    comp = (rgb * alpha + bg * (1.0 - alpha)).clip(0, 255).astype(np.uint8)
                    composited_rgb.append(comp)
                else:
                    composited_rgb.append(arr[:, :, :3])

            loops = max(1, min(10, loop_count))
            video_frames = composited_rgb * loops
            raw_bytes = b"".join(f.tobytes() for f in video_frames)

            ffmpeg_bin = get_ffmpeg_path()
            cmd = [
                ffmpeg_bin,
                "-y",
                "-f", "rawvideo",
                "-vcodec", "rawvideo",
                "-s", f"{W}x{H}",
                "-pix_fmt", "rgb24",
                "-r", str(fps),
                "-i", "-",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-crf", "18",
                "-movflags", "+faststart",
                mp4_path
            ]
            try:
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                proc.communicate(input=raw_bytes)
                # Note: We do NOT append MP4 into ui_results["images"] because ComfyUI's
                # frontend renders preview items in <img> tags, which fails on MP4 files
                # and displays a broken image icon. The MP4 is written directly to disk.
            except Exception as e:
                print(f"[QwenTurntableExport] FFmpeg export error: {e}")

        return {
            "ui": {
                "images": ui_results,
            },
            "result": (out_tensor,)
        }


NODE_CLASS_MAPPINGS = {
    "QwenOrbitPrompt": QwenOrbitPrompt,
    "QwenOrbitTurntablePrompts": QwenOrbitTurntablePrompts,
    "QwenOrbitCanvasPrep": QwenOrbitCanvasPrep,
    "QwenTurntable360Viewer": QwenTurntable360Viewer,
    "QwenTurntableExport": QwenTurntableExport,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "QwenOrbitPrompt": "Qwen Viewpoint Orbit Prompt",
    "QwenOrbitTurntablePrompts": "Qwen Turntable 7-View Prompts",
    "QwenOrbitCanvasPrep": "Qwen Viewpoint Canvas Prep (768x768)",
    "QwenTurntable360Viewer": "Qwen Interactive 360° Turntable Viewer",
    "QwenTurntableExport": "Qwen Turntable Media Export (MP4/WEBP/Frames)",
}

