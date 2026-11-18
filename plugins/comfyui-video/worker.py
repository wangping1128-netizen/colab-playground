#!/usr/bin/env python3
"""ComfyUI Video Studio worker for Colab Playground (runs on the Colab VM).

Supports one-click setup for:
  * Alibaba Tongyi Wan 2.2 (5B TI2V, 14B I2V FP8 + 4-step LoRA, 14B T2V FP8 + 4-step LoRA)
  * Tencent HunyuanVideo 1.5 (720P T2V, 720P I2V distilled FP8)
  * Lightricks LTX-2.3 22B synchronized audio + video (Distilled FP8, Dev FP8 + two-stage LoRA)
  * Arbitrary extra Hugging Face files via ``owner/repo:path/in/repo->models_subdir``

Protocol (see docs/PLUGINS.md):
  * inputs arrive as ``PLUGIN_INPUT_<ID>``; optional HF token as ``PLUGIN_HF_TOKEN``;
  * progress is written atomically to ``$PLUGIN_STATUS_FILE``;
  * non-GPU activity and active ComfyUI queue items touch ``$PLUGIN_HEARTBEAT``.
"""

import json
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

E = os.environ.get
RUN_DIR = E("PLUGIN_RUN_DIR", "/root/.colab-playground/runs/manual")
STATUS_FILE = E("PLUGIN_STATUS_FILE", os.path.join(RUN_DIR, "status.json"))
HEARTBEAT = E("PLUGIN_HEARTBEAT", "")

COMFY_DIR = "/content/ComfyUI"
STAGING_DIR = "/content/hf-staging"
INSTALL_STAMP = os.path.join(COMFY_DIR, ".cpg_comfy_video_v1")
SERVER_LOG = os.path.join(RUN_DIR, "server.log")
INSTALL_LOG = os.path.join(RUN_DIR, "install.log")
DOWNLOAD_LOG = os.path.join(RUN_DIR, "download.log")
NVIDIA_LIBS = ("/usr/lib64-nvidia", "/usr/local/nvidia/lib64")

PRESET = (E("PLUGIN_INPUT_PRESET", "wan2.2-ti2v-5b") or "wan2.2-ti2v-5b").strip()
EXTRA_DOWNLOADS = (E("PLUGIN_INPUT_EXTRA_DOWNLOADS", "") or "").strip()
INSTALL_NODES = (E("PLUGIN_INPUT_INSTALL_NODES", "1") or "1").strip() in ("1", "true", "yes")
VRAM_MODE = (E("PLUGIN_INPUT_VRAM_MODE", "auto") or "auto").strip()
PORT = int(float(E("PLUGIN_INPUT_PORT", "8188") or 8188))
EXTRA_ARGS = (E("PLUGIN_INPUT_EXTRA_ARGS", "") or "").strip()
HF_TOKEN = E("PLUGIN_HF_TOKEN", "")
SECRETS = [s for s in (HF_TOKEN,) if s]

MODEL_SUBDIRS = (
    "diffusion_models",
    "unet",
    "checkpoints",
    "text_encoders",
    "clip",
    "clip_vision",
    "vae",
    "loras",
    "latent_upscale_models",
    "upscale_models",
    "audio_encoders",
    "controlnet",
)

# Verified official Comfy-Org / Lightricks file layouts matching ComfyUI's built-in Template Library.
# Each tuple is (hf_repo, path_in_repo, target_models_subdir, approx_gb).
PRESETS = {
    "wan2.2-ti2v-5b": {
        "template": "Wan 2.2 5B Video Generation",
        "files": [
            ("Comfy-Org/Wan-2.2", "split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors", "diffusion_models", 10.0),
            ("Comfy-Org/Wan-2.2", "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", "text_encoders", 6.7),
            ("Comfy-Org/Wan-2.2", "split_files/vae/wan2.2_vae.safetensors", "vae", 1.4),
        ],
    },
    "wan2.2-i2v-14b-fp8": {
        "template": "Wan 2.2 14B Image to Video",
        "files": [
            ("Comfy-Org/Wan-2.2", "split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors", "diffusion_models", 14.3),
            ("Comfy-Org/Wan-2.2", "split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors", "diffusion_models", 14.3),
            ("Comfy-Org/Wan-2.2", "split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors", "loras", 0.6),
            ("Comfy-Org/Wan-2.2", "split_files/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors", "loras", 0.6),
            ("Comfy-Org/Wan-2.2", "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", "text_encoders", 6.7),
            ("Comfy-Org/Wan-2.2", "split_files/vae/wan_2.1_vae.safetensors", "vae", 0.3),
        ],
    },
    "wan2.2-t2v-14b-fp8": {
        "template": "Wan 2.2 14B Text to Video",
        "files": [
            ("Comfy-Org/Wan-2.2", "split_files/diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors", "diffusion_models", 14.3),
            ("Comfy-Org/Wan-2.2", "split_files/diffusion_models/wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors", "diffusion_models", 14.3),
            ("Comfy-Org/Wan-2.2", "split_files/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors", "loras", 0.6),
            ("Comfy-Org/Wan-2.2", "split_files/loras/wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors", "loras", 0.6),
            ("Comfy-Org/Wan-2.2", "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors", "text_encoders", 6.7),
            ("Comfy-Org/Wan-2.2", "split_files/vae/wan_2.1_vae.safetensors", "vae", 0.3),
        ],
    },
    "hunyuan1.5-720p-t2v": {
        "template": "Hunyuan Video 1.5 Text to Video",
        "files": [
            ("Comfy-Org/Hunyuan-Video-1.5", "split_files/diffusion_models/hunyuanvideo1.5_720p_t2v_fp16.safetensors", "diffusion_models", 16.7),
            ("Comfy-Org/Hunyuan-Video-1.5", "split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors", "text_encoders", 8.8),
            ("Comfy-Org/Hunyuan-Video-1.5", "split_files/text_encoders/byt5_small_glyphxl_fp16.safetensors", "text_encoders", 0.5),
            ("Comfy-Org/Hunyuan-Video-1.5", "split_files/vae/hunyuanvideo15_vae_fp16.safetensors", "vae", 0.5),
        ],
    },
    "hunyuan1.5-720p-i2v": {
        "template": "Hunyuan Video 1.5 Image to Video",
        "files": [
            ("Comfy-Org/Hunyuan-Video-1.5", "split_files/diffusion_models/hunyuanvideo1.5_720p_i2v_cfg_distilled_fp8_scaled.safetensors", "diffusion_models", 8.5),
            ("Comfy-Org/Hunyuan-Video-1.5", "split_files/clip_vision/sigclip_vision_patch14_384.safetensors", "clip_vision", 0.8),
            ("Comfy-Org/Hunyuan-Video-1.5", "split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors", "text_encoders", 8.8),
            ("Comfy-Org/Hunyuan-Video-1.5", "split_files/text_encoders/byt5_small_glyphxl_fp16.safetensors", "text_encoders", 0.5),
            ("Comfy-Org/Hunyuan-Video-1.5", "split_files/vae/hunyuanvideo15_vae_fp16.safetensors", "vae", 0.5),
        ],
    },
    "ltx2.3-22b-distilled-fp8": {
        "template": "LTX-2.3 Text/Image to Video (Distilled)",
        "files": [
            ("Lightricks/LTX-2.3-fp8", "ltx-2.3-22b-distilled-fp8.safetensors", "checkpoints", 29.5),
            ("Comfy-Org/ltx-2", "split_files/text_encoders/gemma_3_12B_it_fp8_scaled.safetensors", "text_encoders", 13.2),
            ("Lightricks/LTX-2.3", "ltx-2.3-spatial-upscaler-x2-1.1.safetensors", "latent_upscale_models", 1.0),
        ],
    },
    "ltx2.3-22b-dev-fp8": {
        "template": "LTX-2.3 Text/Image to Video",
        "files": [
            ("Lightricks/LTX-2.3-fp8", "ltx-2.3-22b-dev-fp8.safetensors", "checkpoints", 29.5),
            ("Lightricks/LTX-2.3", "ltx-2.3-22b-distilled-lora-384-1.1.safetensors", "loras", 7.6),
            ("Comfy-Org/ltx-2", "split_files/text_encoders/gemma_3_12B_it_fp8_scaled.safetensors", "text_encoders", 13.2),
            ("Lightricks/LTX-2.3", "ltx-2.3-spatial-upscaler-x2-1.1.safetensors", "latent_upscale_models", 1.0),
        ],
    },
    "none": {
        "template": "Browse Templates -> Video",
        "files": [],
    },
}

CUSTOM_NODES = (
    ("ComfyUI-Manager", "https://github.com/Comfy-Org/ComfyUI-Manager.git", True),
    ("ComfyUI-GGUF", "https://github.com/city96/ComfyUI-GGUF.git", False),
    ("ComfyUI-VideoHelperSuite", "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git", False),
)

_current_stage = ["detect"]
_server = [None]


# ------------------------------------------------------------- status & safety


def redact(text):
    for s in SECRETS:
        if len(s) >= 4:
            text = text.replace(s, "***")
    return text


def status(state, stage=None, message="", progress=None, outputs=None):
    if stage:
        _current_stage[0] = stage
    doc = {"state": state, "stage": _current_stage[0], "message": redact(message)}
    if progress is not None:
        doc["progress"] = max(0.0, min(1.0, float(progress)))
    if outputs is not None:
        doc["outputs"] = outputs
    print("[%s] %s/%s: %s" % (time.strftime("%H:%M:%S"), state, doc["stage"], doc["message"]), flush=True)
    os.makedirs(os.path.dirname(STATUS_FILE) or ".", exist_ok=True)
    tmp = STATUS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)
    os.replace(tmp, STATUS_FILE)


def fail(message):
    status("failed", message=message)
    sys.exit(1)


def touch_heartbeat():
    if not HEARTBEAT:
        return
    try:
        os.makedirs(os.path.dirname(HEARTBEAT), exist_ok=True)
        with open(HEARTBEAT, "a", encoding="utf-8"):
            os.utime(HEARTBEAT, None)
    except OSError:
        pass


def heartbeat_while(done_event):
    def loop():
        touch_heartbeat()
        while not done_event.wait(25):
            touch_heartbeat()

    threading.Thread(target=loop, daemon=True).start()


def clean_env(include_hf_token=False):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PLUGIN_")}
    path_parts = ["/usr/local/cuda/bin", "/usr/local/bin", env.get("PATH", "/usr/bin:/bin")]
    env["PATH"] = ":".join(p for p in path_parts if p)
    ld_parts = [p for p in NVIDIA_LIBS if os.path.isdir(p)]
    if env.get("LD_LIBRARY_PATH"):
        ld_parts.append(env["LD_LIBRARY_PATH"])
    if ld_parts:
        env["LD_LIBRARY_PATH"] = ":".join(ld_parts)
    env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    env["PYTHONUNBUFFERED"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    if include_hf_token and HF_TOKEN:
        env["HF_TOKEN"] = HF_TOKEN
    return env


# ------------------------------------------------------------- helpers


def gpu_info():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if not out:
            return None, 0
        first = out.splitlines()[0]
        name, mem = [x.strip() for x in first.split(",", 1)]
        return name, int(float(mem))
    except Exception:  # noqa: BLE001
        return None, 0


def choose_vram_flag(mode, vram_mib):
    if mode == "highvram":
        return "--highvram"
    if mode == "normalvram":
        return "--normalvram"
    if mode == "lowvram":
        return "--lowvram"
    if vram_mib >= 70000:
        return "--highvram"
    if vram_mib >= 20000:
        return "--normalvram"
    if vram_mib > 0:
        return "--lowvram"
    return "--cpu"


def is_safe_relpath(p):
    if not p or p.startswith("/") or "\\" in p:
        return False
    parts = p.split("/")
    return all(part and part not in (".", "..") for part in parts)


def is_repo_id(repo):
    parts = repo.split("/")
    if len(parts) != 2:
        return False
    return all(
        part and not part.startswith((".", "-")) and re.match(r"^[A-Za-z0-9._-]+$", part)
        for part in parts
    )


def parse_extra_downloads(spec_text):
    """Parses 'owner/repo:path/in/repo->subdir; ...' into [(repo, path, subdir, 0.0)]."""
    items = []
    if not spec_text.strip():
        return items
    for raw in re.split(r"[;\n]+", spec_text):
        entry = raw.strip()
        if not entry:
            continue
        if ":" not in entry or "->" not in entry:
            raise ValueError("invalid extra download %r (expected owner/repo:path/in/repo->models_subdir)" % entry)
        repo, rest = entry.split(":", 1)
        repo_path, subdir = rest.rsplit("->", 1)
        repo, repo_path, subdir = repo.strip(), repo_path.strip(), subdir.strip().strip("/")
        if subdir.startswith("models/"):
            subdir = subdir[len("models/"):]
        if not is_repo_id(repo):
            raise ValueError("invalid Hugging Face repo id %r" % repo)
        if not is_safe_relpath(repo_path):
            raise ValueError("invalid file path in repo %r" % repo_path)
        if not is_safe_relpath(subdir):
            raise ValueError("invalid ComfyUI models subdirectory %r" % subdir)
        items.append((repo, repo_path, subdir, 0.0))
    return items


def build_download_plan(preset_name, extra_text):
    if preset_name not in PRESETS:
        raise ValueError("unknown preset %r" % preset_name)
    base = list(PRESETS[preset_name]["files"])
    extra = parse_extra_downloads(extra_text)
    seen = set()
    plan = []
    for repo, repo_path, subdir, est_gb in base + extra:
        dest_rel = os.path.join(subdir, os.path.basename(repo_path))
        if dest_rel in seen:
            continue
        seen.add(dest_rel)
        plan.append((repo, repo_path, subdir, est_gb))
    return plan, PRESETS[preset_name]["template"]


def dir_size(path):
    total = 0
    if not os.path.exists(path):
        return 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def http_json(url, timeout=5):
    req = urllib.request.Request(url, headers={"User-Agent": "colab-playground-comfyui/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ------------------------------------------------------------- installation


def run_logged(cmd, log_handle, env=None, cwd=None, check=True):
    log_handle.write("$ " + redact(shlex.join(cmd)) + "\n")
    log_handle.flush()
    return subprocess.run(
        cmd,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        env=env or clean_env(),
        cwd=cwd,
        check=check,
    )


def ensure_model_dirs():
    for sub in MODEL_SUBDIRS:
        os.makedirs(os.path.join(COMFY_DIR, "models", sub), exist_ok=True)
    os.makedirs(os.path.join(COMFY_DIR, "output"), exist_ok=True)
    os.makedirs(os.path.join(COMFY_DIR, "input"), exist_ok=True)


def install_comfyui():
    os.makedirs("/content", exist_ok=True)
    try:
        with open(INSTALL_LOG, "a", encoding="utf-8") as log:
            status("running", "install", "preparing huggingface_hub[hf_xet]", progress=0.1)
            run_logged(
                [sys.executable, "-m", "pip", "install", "-q", "-U", "huggingface_hub[hf_xet]"],
                log,
            )

            if os.path.isfile(os.path.join(COMFY_DIR, "main.py")) and os.path.isfile(INSTALL_STAMP):
                ensure_model_dirs()
                if INSTALL_NODES:
                    install_custom_nodes(log)
                status("running", "install", "reusing existing ComfyUI installation", progress=1.0)
                return

            if not os.path.isfile(os.path.join(COMFY_DIR, "main.py")):
                status("running", "install", "cloning ComfyUI", progress=0.25)
                shutil.rmtree(COMFY_DIR, ignore_errors=True)
                run_logged(
                    [
                        "git",
                        "clone",
                        "--depth",
                        "1",
                        "https://github.com/Comfy-Org/ComfyUI.git",
                        COMFY_DIR,
                    ],
                    log,
                )

            ensure_model_dirs()

            status("running", "install", "installing ComfyUI dependencies", progress=0.55)
            run_logged(
                [sys.executable, "-m", "pip", "install", "-q", "-r", os.path.join(COMFY_DIR, "requirements.txt")],
                log,
            )
            run_logged(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "-q",
                    "gguf",
                    "imageio-ffmpeg",
                    "opencv-python-headless",
                ],
                log,
            )

            if INSTALL_NODES:
                install_custom_nodes(log)

            with open(INSTALL_STAMP, "w", encoding="utf-8") as fh:
                fh.write("ok\n")
            status("running", "install", "ComfyUI environment ready", progress=1.0)
    except subprocess.CalledProcessError as exc:
        cmd_name = os.path.basename(exc.cmd[0]) if getattr(exc, "cmd", None) else "command"
        detail = log_tail(INSTALL_LOG, n=12) or str(exc)
        fail("ComfyUI installation failed (%s, exit %s): %s" % (cmd_name, exc.returncode, detail))


def install_custom_nodes(log):
    nodes_root = os.path.join(COMFY_DIR, "custom_nodes")
    os.makedirs(nodes_root, exist_ok=True)
    for idx, (name, url, install_reqs) in enumerate(CUSTOM_NODES, start=1):
        dest = os.path.join(nodes_root, name)
        if os.path.isdir(dest) and os.listdir(dest):
            continue
        shutil.rmtree(dest, ignore_errors=True)
        status(
            "running",
            "install",
            "installing %s (%d/%d)" % (name, idx, len(CUSTOM_NODES)),
            progress=0.75 + 0.07 * idx,
        )
        res = run_logged(
            ["git", "clone", "--depth", "1", url, dest],
            log,
            check=False,
        )
        if res.returncode != 0:
            shutil.rmtree(dest, ignore_errors=True)
            log.flush()
            print("warning: failed to clone %s: %s" % (name, log_tail(INSTALL_LOG, n=3)), flush=True)
            continue
        req_file = os.path.join(dest, "requirements.txt")
        if install_reqs and os.path.isfile(req_file):
            run_logged([sys.executable, "-m", "pip", "install", "-q", "-r", req_file], log, check=False)


# ------------------------------------------------------------- model downloads


def probe_remote_sizes(pending):
    """Queries exact byte sizes from Hugging Face Hub; falls back to preset GB estimates."""
    helper = (
        "import json, os, sys\n"
        "from huggingface_hub import HfApi\n"
        "api = HfApi(token=os.environ.get('HF_TOKEN') or None)\n"
        "req = json.loads(sys.argv[1])\n"
        "out = {}\n"
        "by_repo = {}\n"
        "for r, p in req:\n"
        "    by_repo.setdefault(r, []).append(p)\n"
        "for r, paths in by_repo.items():\n"
        "    infos = api.get_paths_info(r, paths=paths, repo_type='model')\n"
        "    for info in infos:\n"
        "        sz = getattr(info, 'size', None) or 0\n"
        "        if getattr(info, 'lfs', None) and getattr(info.lfs, 'size', None):\n"
        "            sz = info.lfs.size\n"
        "        out[r + ':' + info.path] = int(sz)\n"
        "print(json.dumps(out))\n"
    )
    payload = json.dumps([[r, p] for r, p, _, _ in pending])
    res = subprocess.run(
        [sys.executable, "-c", helper, payload],
        capture_output=True,
        text=True,
        env=clean_env(include_hf_token=True),
    )
    if res.returncode == 0:
        try:
            return json.loads(res.stdout.strip().splitlines()[-1])
        except Exception:  # noqa: BLE001
            return {}
    err = redact((res.stderr or "").strip())
    if "401" in err or "403" in err or "GatedRepoError" in err or "RepositoryNotFoundError" in err:
        fail(
            "Hugging Face access denied or repository not found (for gated models such as LTX-2.5, "
            "accept the license on huggingface.co and save your HF token on the Plugins page)"
        )
    return {}


def download_models(plan):
    if not plan:
        status("running", "download", "no preloaded model requested (preset = none)", progress=1.0)
        return []

    pending = []
    ready_files = []
    for repo, repo_path, subdir, est_gb in plan:
        fname = os.path.basename(repo_path)
        dest = os.path.join(COMFY_DIR, "models", subdir, fname)
        if os.path.isfile(dest) and os.path.getsize(dest) > 1024 * 1024:
            ready_files.append(os.path.join(subdir, fname))
        else:
            pending.append((repo, repo_path, subdir, est_gb))

    if not pending:
        status(
            "running",
            "download",
            "all %d model file(s) already present on disk" % len(ready_files),
            progress=1.0,
        )
        return ready_files

    status("running", "download", "checking model sizes on Hugging Face", progress=0.02)
    exact_sizes = probe_remote_sizes(pending)
    sizes = []
    for repo, repo_path, subdir, est_gb in pending:
        sz = exact_sizes.get("%s:%s" % (repo, repo_path)) or int(est_gb * 1e9)
        sizes.append(sz)
    total_bytes = sum(sizes)

    free_bytes = shutil.disk_usage("/content").free
    if total_bytes > 0 and free_bytes < total_bytes + int(4 * 1e9):
        fail(
            "not enough VM disk space: %.1f GB free, need %.1f GB (+4 GB headroom). "
            "Pick a lighter preset or start a fresh session."
            % (free_bytes / 1e9, total_bytes / 1e9)
        )

    dl_script = (
        "import os, sys\n"
        "from huggingface_hub import hf_hub_download\n"
        "hf_hub_download(\n"
        "    repo_id=sys.argv[1],\n"
        "    filename=sys.argv[2],\n"
        "    local_dir=sys.argv[3],\n"
        "    token=os.environ.get('HF_TOKEN') or None,\n"
        ")\n"
    )

    completed_bytes = 0
    with open(DOWNLOAD_LOG, "a", encoding="utf-8") as log:
        for idx, ((repo, repo_path, subdir, _), expected_sz) in enumerate(zip(pending, sizes), start=1):
            fname = os.path.basename(repo_path)
            dest_dir = os.path.join(COMFY_DIR, "models", subdir)
            dest_path = os.path.join(dest_dir, fname)
            os.makedirs(dest_dir, exist_ok=True)
            shutil.rmtree(STAGING_DIR, ignore_errors=True)
            os.makedirs(STAGING_DIR, exist_ok=True)

            done_file = threading.Event()

            def report_progress(cur_idx=idx, cur_name=fname, base_done=completed_bytes):
                while not done_file.wait(8):
                    staged = dir_size(STAGING_DIR)
                    got = base_done + staged
                    pct = (got / total_bytes) if total_bytes > 0 else None
                    msg = "[%d/%d] %s (%.1f / %.1f GB)" % (
                        cur_idx,
                        len(pending),
                        cur_name,
                        got / 1e9,
                        total_bytes / 1e9,
                    ) if total_bytes > 0 else "[%d/%d] %s (%.1f GB)" % (
                        cur_idx,
                        len(pending),
                        cur_name,
                        got / 1e9,
                    )
                    status("running", "download", msg, progress=pct)
                    touch_heartbeat()

            status(
                "running",
                "download",
                "[%d/%d] downloading %s" % (idx, len(pending), fname),
                progress=(completed_bytes / total_bytes) if total_bytes > 0 else 0.05,
            )
            threading.Thread(target=report_progress, daemon=True).start()
            try:
                log.write("downloading %s:%s -> %s\n" % (repo, repo_path, dest_path))
                log.flush()
                subprocess.run(
                    [sys.executable, "-c", dl_script, repo, repo_path, STAGING_DIR],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    env=clean_env(include_hf_token=True),
                    check=True,
                )
            except subprocess.CalledProcessError as exc:
                log.flush()
                detail = log_tail(DOWNLOAD_LOG, n=12) or str(exc)
                fail("failed downloading %s from %s: %s" % (fname, repo, detail))
            finally:
                done_file.set()

            staged_file = os.path.join(STAGING_DIR, repo_path)
            if not os.path.isfile(staged_file):
                fail("downloaded file missing at %s" % staged_file)
            actual_sz = os.path.getsize(staged_file)
            shutil.move(staged_file, dest_path)
            shutil.rmtree(STAGING_DIR, ignore_errors=True)
            completed_bytes += expected_sz or actual_sz
            ready_files.append(os.path.join(subdir, fname))

    status("running", "download", "downloaded %d model file(s)" % len(ready_files), progress=1.0)
    return ready_files


# ------------------------------------------------------------- server


def port_busy(port):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def kill_existing_comfy():
    subprocess.run(["pkill", "-f", "/content/ComfyUI/main.py"], check=False)
    for _ in range(20):
        if subprocess.run(["pgrep", "-f", "/content/ComfyUI/main.py"], capture_output=True).returncode != 0:
            return
        time.sleep(1)


def log_tail(path=SERVER_LOG, n=8):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return redact(" | ".join(line.strip() for line in fh.readlines()[-n:] if line.strip()))
    except OSError:
        return ""


def start_server(vram_flag):
    cmd = [
        sys.executable,
        "-u",
        os.path.join(COMFY_DIR, "main.py"),
        "--listen",
        "127.0.0.1",
        "--port",
        str(PORT),
        "--enable-cors-header",
        "--preview-method",
        "auto",
        vram_flag,
    ]
    if EXTRA_ARGS:
        cmd += shlex.split(EXTRA_ARGS)
    with open(os.path.join(RUN_DIR, "server.cmd"), "w", encoding="utf-8") as fh:
        fh.write(redact(shlex.join(cmd)) + "\n")
    with open(SERVER_LOG, "w", encoding="utf-8") as srv_log:
        proc = subprocess.Popen(
            cmd,
            cwd=COMFY_DIR,
            env=clean_env(include_hf_token=False),
            stdout=srv_log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    _server[0] = proc
    return proc


def wait_ready(proc, timeout=420):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            return None
        try:
            stats = http_json("http://127.0.0.1:%d/system_stats" % PORT, timeout=5)
            if isinstance(stats, dict) and "system" in stats:
                return stats
        except Exception:  # noqa: BLE001
            pass
        touch_heartbeat()
        time.sleep(3)
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except OSError:
        pass
    return None


def on_sigterm(*_):
    proc = _server[0]
    if proc is not None and proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except OSError:
            pass
    try:
        status("failed", message="stopped")
    except OSError:
        pass
    os._exit(143)


def monitor():
    """Keep supervising ComfyUI; touch heartbeat when prompts are queued/running."""
    while True:
        time.sleep(20)
        proc = _server[0]
        if proc is not None and proc.poll() is not None:
            fail("ComfyUI exited unexpectedly: %s" % log_tail())
        try:
            q = http_json("http://127.0.0.1:%d/queue" % PORT, timeout=5)
            if isinstance(q, dict) and (q.get("queue_running") or q.get("queue_pending")):
                touch_heartbeat()
        except Exception:  # noqa: BLE001
            pass


# ------------------------------------------------------------- self-test & main


def self_test():
    for name in PRESETS:
        plan, tpl = build_download_plan(name, "")
        assert isinstance(tpl, str) and tpl
        for repo, repo_path, subdir, _ in plan:
            assert is_repo_id(repo), repo
            assert is_safe_relpath(repo_path), repo_path
            assert subdir in MODEL_SUBDIRS, subdir
    extra, _ = build_download_plan(
        "none",
        "Comfy-Org/Wan-2.2:split_files/vae/wan2.2_vae.safetensors->vae; "
        "QuantStack/Wan2.2-I2V-A14B-GGUF:HighNoise/model.gguf->models/unet",
    )
    assert len(extra) == 2
    assert extra[1][2] == "unet"
    assert choose_vram_flag("auto", 81920) == "--highvram"
    assert choose_vram_flag("auto", 40960) == "--normalvram"
    assert choose_vram_flag("auto", 15360) == "--lowvram"
    assert choose_vram_flag("auto", 0) == "--cpu"
    env = clean_env()
    assert env.get("GIT_TERMINAL_PROMPT") == "0"
    assert "PLUGIN_ID" not in env
    if shutil.which("git"):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src")
            dst = os.path.join(tmp, "dst")
            os.makedirs(src)
            subprocess.run(["git", "init", "-q", src], env=env, check=True)
            with open(os.path.join(src, "README.md"), "w", encoding="utf-8") as fh:
                fh.write("ok\n")
            subprocess.run(["git", "-C", src, "add", "README.md"], env=env, check=True)
            subprocess.run(
                ["git", "-C", src, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-q", "-m", "init"],
                env=env,
                check=True,
            )
            subprocess.run(["git", "clone", "--depth", "1", "-q", "file://" + src, dst], env=env, check=True)
            assert os.path.isfile(os.path.join(dst, "README.md"))
    print("self-test ok (%d presets verified)" % len(PRESETS))
    return 0


def main():
    os.makedirs(RUN_DIR, exist_ok=True)
    signal.signal(signal.SIGTERM, on_sigterm)
    setup_done = threading.Event()
    heartbeat_while(setup_done)

    if PORT == 8080:
        fail("VM port 8080 belongs to Colab; choose another port (e.g. 8188)")

    try:
        plan, template_hint = build_download_plan(PRESET, EXTRA_DOWNLOADS)
    except ValueError as exc:
        fail(str(exc))

    status("running", "detect", "checking GPU and disk space")
    gpu, vram_mib = gpu_info()
    free_gb = round(shutil.disk_usage("/content").free / 1e9, 1) if os.path.isdir("/content") else 0.0
    if not gpu and PRESET != "none":
        fail("no NVIDIA GPU detected on this runtime; select L4 or A100 when starting video models")
    status(
        "running",
        "detect",
        "%s (%d MiB VRAM), %.1f GB free disk" % (gpu or "CPU", vram_mib, free_gb),
        progress=1.0,
    )

    install_comfyui()
    ready_files = download_models(plan)

    kill_existing_comfy()
    if port_busy(PORT):
        fail("port %d is already in use on the VM; choose another port" % PORT)

    vram_flag = choose_vram_flag(VRAM_MODE, vram_mib)
    status("running", "server", "starting ComfyUI on port %d (%s)" % (PORT, vram_flag), progress=0.3)
    proc = start_server(vram_flag)
    stats = wait_ready(proc)
    if not stats:
        fail("ComfyUI did not become ready: %s" % log_tail())

    devices = stats.get("devices") or []
    dev_type = devices[0].get("type", "") if devices else ""
    if gpu and dev_type != "cuda":
        fail("ComfyUI started without CUDA (device=%r): %s" % (dev_type, log_tail()))

    comfy_ver = stats.get("system", {}).get("comfyui_version", "latest")
    free_after_gb = round(shutil.disk_usage("/content").free / 1e9, 1) if os.path.isdir("/content") else 0.0
    outputs = {
        "comfyui_version": comfy_ver,
        "gpu": gpu or "CPU",
        "vram_total_mib": vram_mib,
        "vram_mode": vram_flag.lstrip("-"),
        "preset": PRESET,
        "recommended_template": template_hint,
        "models_ready": len(ready_files),
        "disk_free_gb": free_after_gb,
        "output_dir": "/content/ComfyUI/output",
    }
    setup_done.set()
    status(
        "ready",
        "server",
        "ComfyUI %s ready (%s, %d model files) — open '%s' in Browse Templates"
        % (comfy_ver, gpu or "CPU", len(ready_files), template_hint),
        progress=1.0,
        outputs=outputs,
    )
    monitor()


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        sys.exit(self_test())
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        fail("worker error: %s: %s" % (type(exc).__name__, exc))
