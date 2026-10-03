# ComfyUI-Qwen-Image-2.1-Orbit 🌀

[![ComfyUI Custom Node](https://img.shields.io/badge/ComfyUI-Custom%20Node-blue.svg)](https://github.com/comfyanonymous/ComfyUI)
[![Model](https://img.shields.io/badge/Model-Qwen--Image--2.1-purple.svg)](https://huggingface.co/Qwen/Qwen-Image-2.1)
[![VRAM](https://img.shields.io/badge/VRAM-8GB%20Safe-success.svg)](#hardware--vram-optimization)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**360° Turntable Orbit & Camera Control for Qwen-Image 2.1 in ComfyUI.**

- 🌀 **Full 360° Turntables**: Generate 8 seamless, consistent viewpoints from a single 2D image in one click.
- ⚡ **Fix Any Angle in Seconds**: Regenerate and replace just one flawed viewpoint without re-running the entire turntable.
- 🕹️ **Interactive 3D Viewer**: In-canvas orbit ring with live camera tracking (`📷`), drag scrubbing, and speed controls.
- 📦 **One-Click Multi-Export**: Automatically export looping MP4 video, transparent animated WebP, and individual PNG frames.
- 🛡️ **8GB VRAM Safe**: Sequential execution keeps peak VRAM strictly under 7.0 GB (tested on RTX 4070 Laptop).

---

## 🎬 Showcase

### 1. 2D Image ➔ Complete 360° Viewpoint Orbit
From a single reference image, generate 8 unified viewpoint perspectives with consistent lighting and transparent background:

#### Example A: Stylized Character (Egyptian Mummy)
![Side by Side 360 Demo - Mummy](assets/side_by_side_demo.gif)

#### Example B: Realistic Human & Drapery (Egyptian Queen)
![Side by Side 360 Demo - Egyptian Queen](assets/demo_egyptian_queen.gif)

#### Example C: 3D Asset / Plush Toy (Cute Monster)
![Side by Side 360 Demo - Plush Monster](assets/demo_plush_monster.gif)

### 2. In-Canvas Interactive 360° Viewer
Scrub angles directly on the ComfyUI canvas with an elliptical 3D orbit ring, live camera handle (`📷`), playback speed presets (0.5x, 1x, 2x), and instant single-click frame saving:

![Interactive Canvas Viewer](assets/interactive_viewer_demo.gif)

---

## ✨ Key Features

- 🌀 **Full Turntable 360**: Generates 8 sequential angles with matching lighting and seamless looping.
- ⚡ **Fix Any Angle (`Patch Single Frame`)**: Regenerates only the chosen viewpoint (~4s on Viggle Turbo) and updates that slot in the saved turntable.
- 🎯 **Single View**: Generates a single standalone angle.
- 🖥️ **Interactive Viewer (`QwenTurntable360Viewer`)**: 3D orbit ring, live camera handle, drag scrubbing, speed presets, and single-click frame saving.
- 📦 **Auto Multi-Export (`QwenTurntableExport`)**: Exports looping MP4 video, transparent animated WebP, and numbered PNG frames.
- 🛡️ **8GB VRAM Safe**: Sequential execution stays under 7.0 GB VRAM with zero OOM crashes.

---

## 📦 Included Workflows

Both verified workflows are located in the [`workflows/`](workflows/) folder:

| Workflow | Engine | Steps / View | 360 Orbit Time | Patch Time | Recommended For |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`Qwen_Image_2.1_Viggle_Turbo_Viewpoint_Orbit.json`** | **Viggle Turbo LoRA** | **6 steps** | **~3.5 min** | **~4 sec** | ⚡ **Fastest (Recommended)** |
| **`Qwen_Image_2.1_Viewpoint_Orbit.json`** | Standard Euler | 28–40 steps | ~12–15 min | ~90 sec | 🎨 High-precision evaluations |

---

## 🚀 Installation

```bash
cd custom_nodes
git clone https://github.com/ehab-ayman-gharib/ComfyUI-Qwen-Image-2.1-Orbit.git
pip install -r ComfyUI-Qwen-Image-2.1-Orbit/requirements.txt
```
*(Requires standard `torch`, `numpy`, and `Pillow`. Ensure `ffmpeg` is installed for MP4 export).*

---

## 📥 Required Models & Paths

| Model | File | Path in ComfyUI | Source |
| :--- | :--- | :--- | :--- |
| **Viewpoint Orbit LoRA** | `orbit_alpha_lora.safetensors` | `models/loras/` | [ML-Intern-lab HF](https://huggingface.co/ML-Intern-lab/Qwen-Image-2.1-viewpoint-orbit-LoRA/blob/main/checkpoints/steps2000res768/orbit_alpha_lora/orbit_alpha_lora.safetensors) |
| **Viggle Turbo LoRA** *(for fast workflow)* | `Qwen-Image-2.1-viggle-turbo-v0.2.1-6step-lora-r128.safetensors` | `models/loras/` | [Viggle AI HF](https://huggingface.co/Viggle/Qwen-Image-2.1-viggle-turbo) |
| **Text Encoder (W4A8)** | `qwen3vl_8b_w4a8.safetensors` | `models/text_encoders/` | [Comfy-Org HF](https://huggingface.co/Comfy-Org/Qwen-Image-2.1) |
| **Diffusion Model (DiT)** | `qwen_image_2.1_Q5_K_M.gguf` (or FP8 / BF16) | `models/unet/` | [Unsloth GGUF](https://huggingface.co/unsloth/Qwen-Image-2.1-GGUF) / [Qwen HF](https://huggingface.co/Qwen/Qwen-Image-2.1) |
| **VAE** | `qwen_image_2.1_vae_bf16.safetensors` | `models/vae/` | [Comfy-Org HF](https://huggingface.co/Comfy-Org/Qwen-Image-2.1) |
| **Background Removal** | `RMBG-2.0` | via `comfyui-rmbg` | [comfyui-rmbg](https://github.com/1038lab/ComfyUI-RMBG) |

> ⚠️ **8GB GPU Note**: Always use `qwen3vl_8b_w4a8.safetensors` (W4A8, ~5.88 GB). Avoid FP8 scaled (~10.58 GB) to prevent OOM.

---

## 🛠️ How to Use

1. Load [`workflows/Qwen_Image_2.1_Viggle_Turbo_Viewpoint_Orbit.json`](workflows/Qwen_Image_2.1_Viggle_Turbo_Viewpoint_Orbit.json) in ComfyUI.
2. Select an image in **Load Image** (RMBG-2.0 removes the background automatically).
3. In **Qwen Viewpoint Orbit Prompt**, select `mode`: **`Full Turntable 360`**.
4. Click **Queue Prompt**. View the result in the interactive 360° viewer or find exported MP4/WebP/PNGs in `output/`.

### How to Fix a Single Angle:
1. In **Qwen Viewpoint Orbit Prompt**, switch `mode` to **`Patch Single Frame`**.
2. Select the `camera_angle` you want to fix (e.g., `180`).
3. Click **Queue Prompt**. It renders only that angle (~4s) and updates that slot in the saved turntable.

---

## 📐 Supported Camera Angles

- **Angles**: `keep angle`, `45 right`, `90 right`, `135 right`, `180`, `135 left`, `90 left`, `45 left`
- **Elevations**: `eye level` (default), `low angle` (~ -20°), `elevated` (~ +40°)

---

## 🤝 Credits & Acknowledgments

- **[ML-Intern-lab](https://huggingface.co/ML-Intern-lab/Qwen-Image-2.1-viewpoint-orbit-LoRA)**: Viewpoint Orbit LoRA and original Gradio demo.
- **[Alibaba Qwen Team](https://github.com/QwenLM/Qwen-Image)**: Qwen-Image 2.1 foundational model and WanVAE.
- **[Viggle AI](https://huggingface.co/viggle-ai)**: 6-step Turbo distillation LoRA.
- **[ComfyUI](https://github.com/comfyanonymous/ComfyUI)**: Modular generative AI platform.
- **[BiRefNet / RMBG-2.0](https://github.com/ZhengPeng7/BiRefNet)**: Background segmentation.

---

## 📄 License

[Apache 2.0 License](LICENSE)
