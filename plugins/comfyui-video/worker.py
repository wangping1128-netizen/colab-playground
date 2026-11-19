#!/usr/bin/env python3
import importlib, json, os, re, shlex, shutil, signal, socket, subprocess as sp, sys, threading, time, urllib.request as ur

E, P = os.environ.get, os.path
B, F, J, rm = P.basename, P.isfile, P.join, lambda p: shutil.rmtree(p, True)
inp = lambda k, d="": (E("PLUGIN_INPUT_" + k) or d).strip()
RUN = E("PLUGIN_RUN_DIR", "/tmp/cpg")
SF, HB, TOK = E("PLUGIN_STATUS_FILE", f"{RUN}/status.json"), E("PLUGIN_HEARTBEAT", ""), E("PLUGIN_HF_TOKEN", "")
C, STG, STAMP, SLOG, ILOG = "/content/ComfyUI", "/content/.hf", "/content/ComfyUI/.cpg_v1", f"{RUN}/server.log", f"{RUN}/install.log"
PRESET, EXTRA, VMODE, XARGS = inp("PRESET", "wan2.2-ti2v-5b"), inp("EXTRA_DOWNLOADS"), inp("VRAM_MODE", "auto"), inp("EXTRA_ARGS")
INODES, PORT = inp("INSTALL_NODES", "1") in ("1", "true", "yes"), int(float(inp("PORT", "8188")))

MODEL_SUBDIRS = tuple("diffusion_models unet checkpoints text_encoders clip clip_vision vae loras latent_upscale_models upscale_models audio_encoders controlnet".split())
REPOS = ("Comfy-Org/Wan-2.2", "Comfy-Org/Hunyuan-Video-1.5", "Lightricks/LTX-2.3", "Lightricks/LTX-2.3-fp8", "Comfy-Org/ltx-2")
_p = lambda s: [(REPOS[int(r)], (n[1:] if n[0] == "/" else f"split_files/{MODEL_SUBDIRS[int(d)]}/{n}") + ".safetensors", MODEL_SUBDIRS[int(d)], float(g)) for r, d, n, g in (t.split(":") for t in s.split())]
F8, WT, H7, L2 = "_fp8_scaled", "0:3:umt5_xxl_fp8_e4m3fn_scaled:6.7", "1:0:hunyuanvideo1.5_720p_", "/ltx-2.3-22b-"
W2, HV, LT, TV, IV, HL = "Wan 2.2 ", "Hunyuan Video 1.5 ", "LTX-2.3 Text/Image to Video", "Text to Video", "Image to Video", ("high", "low")
HC, LC = f"1:3:qwen_2.5_vl_7b{F8}:8.8 1:3:byt5_small_glyphxl_fp16:0.5 1:6:hunyuanvideo15_vae_fp16:0.5", f"4:3:gemma_3_12B_it{F8}:13.2 2:8:/ltx-2.3-spatial-upscaler-x2-1.1:1"
w14 = lambda k, v: " ".join([*(f"0:0:wan2.2_{k}_{h}_noise_14B{F8}:14.3" for h in HL), *(f"0:7:wan2.2_{k}_lightx2v_4steps_lora_{v}_{h}_noise:0.6" for h in HL), WT, "0:6:wan_2.1_vae:0.3"])
PRESETS = {k: (t, _p(s)) for k, (t, s) in {
 "wan2.2-ti2v-5b": (f"{W2}5B Video Generation", f"0:0:wan2.2_ti2v_5B_fp16:10 {WT} 0:6:wan2.2_vae:1.4"),
 "wan2.2-i2v-14b-fp8": (f"{W2}14B {IV}", w14("i2v", "v1")),
 "wan2.2-t2v-14b-fp8": (f"{W2}14B {TV}", w14("t2v", "v1.1")),
 "hunyuan1.5-720p-t2v": (f"{HV}{TV}", f"{H7}t2v_fp16:16.7 {HC}"),
 "hunyuan1.5-720p-i2v": (f"{HV}{IV}", f"{H7}i2v_cfg_distilled{F8}:8.5 1:5:sigclip_vision_patch14_384:0.8 {HC}"),
 "ltx2.3-22b-distilled-fp8": (f"{LT} (Distilled)", f"3:2:{L2}distilled-fp8:29.5 {LC}"),
 "ltx2.3-22b-dev-fp8": (LT, f"3:2:{L2}dev-fp8:29.5 2:7:{L2}distilled-lora-384-1.1:7.6 {LC}"),
 "none": ("Browse Templates -> Video", ""),
}.items()}
NODES = (("Comfy-Org/ComfyUI-Manager", 1), ("city96/ComfyUI-GGUF", 0), ("Kosinkadink/ComfyUI-VideoHelperSuite", 0))
_stg, _srv = ["detect"], [None]
md = lambda p: os.makedirs(p, exist_ok=True)
bg = lambda fn: threading.Thread(target=fn, daemon=True).start()
red = lambda t: str(t).replace(TOK, "***") if len(TOK) >= 4 else str(t)
tail = lambda p=SLOG: red(" | ".join(x.strip() for x in open(p, errors="replace").readlines()[-8:] if x.strip())) if F(p) else ""

def dsz(p):
 t = 0
 for r, _, fs in os.walk(p):
  for f in fs:
   try: t += P.getsize(J(r, f))
   except OSError: pass
 return t

def st(m="", p=None, g=None, s="running", o=None):
 if g: _stg[0] = g
 d = dict(state=s, stage=_stg[0], message=red(m))
 if p is not None: d["progress"] = max(0.0, min(1.0, float(p)))
 if o: d["outputs"] = o
 print(s, _stg[0], d["message"], flush=True)
 md(P.dirname(SF) or "."); open(SF + ".tmp", "w").write(json.dumps(d)); os.replace(SF + ".tmp", SF)

def fail(m): st(m, s="failed"); sys.exit(1)

def hb():
 if HB:
  try: md(P.dirname(HB)); open(HB, "a").close(); os.utime(HB, None)
  except OSError: pass

def clean_env():
 e = {k: v for k, v in os.environ.items() if not k.startswith("PLUGIN_")}
 e["PATH"] = "/usr/local/cuda/bin:/usr/local/bin:" + e.get("PATH", "/usr/bin:/bin")
 ld = [p for p in ("/usr/lib64-nvidia", "/usr/local/nvidia/lib64", e.get("LD_LIBRARY_PATH", "")) if p and (":" in p or P.isdir(p))]
 if ld: e["LD_LIBRARY_PATH"] = ":".join(ld)
 return dict(e, PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True", PYTHONUNBUFFERED="1", GIT_TERMINAL_PROMPT="0")

choose_vram_flag = lambda m, v: "" if m == "normalvram" else (f"--{m}" if m in ("highvram", "lowvram") else ("--highvram" if v >= 70000 else "" if v >= 20000 else "--lowvram" if v > 0 else "--cpu"))

def build_download_plan(pr, ex):
 if pr not in PRESETS: raise ValueError(f"unknown preset {pr!r}")
 tpl, items = PRESETS[pr][0], list(PRESETS[pr][1])
 ok = lambda p: bool(p and p[0] != "/" and all(x and x not in (".", "..") for x in p.split("/")))
 for e in (x.strip() for x in re.split(r"[;\n]+", ex or "") if x.strip()):
  m = re.fullmatch(r"([A-Za-z0-9_][\w.-]*/[A-Za-z0-9_][\w.-]*):([^\\]+)->([^\\]+)", e)
  if not m: raise ValueError(f"invalid extra {e!r}")
  r, p, s = m[1], m[2].strip(), m[3].strip().strip("/")
  s = s[7:] if s.startswith("models/") else s
  if not (ok(p) and ok(s)): raise ValueError(f"invalid extra {e!r}")
  items.append((r, p, s, 0.0))
 seen, plan = set(), []
 for r, p, s, g in items:
  k = f"{s}/{B(p)}"
  if k not in seen: seen.add(k); plan.append((r, p, s, g))
 return plan, tpl

def install():
 md("/content"); env = clean_env()
 try:
  with open(ILOG, "a") as log:
   sh = lambda *c, ck=1: sp.run(c, stdout=log, stderr=sp.STDOUT, env=env, check=bool(ck))
   pip = lambda *a, ck=1: sh(sys.executable, "-m", "pip", "install", "-q", *a, ck=ck)
   gc = lambda u, d, ck=1: sh("git", "clone", "--depth=1", f"https://github.com/{u}.git", d, ck=ck)
   st("setup hf_hub", 0.1, "install"); pip("-U", "huggingface_hub[hf_xet]")
   if not (F(f"{C}/main.py") and F(STAMP)):
    if not F(f"{C}/main.py"): st("cloning ComfyUI", 0.25); rm(C); gc("Comfy-Org/ComfyUI", C)
    st("installing deps", 0.55); pip("-r", f"{C}/requirements.txt"); pip("gguf", "imageio-ffmpeg", "opencv-python-headless")
   for s in (*MODEL_SUBDIRS, "../output", "../input"): md(P.normpath(f"{C}/models/{s}"))
   if INODES:
    for i, (u, rq) in enumerate(NODES, 1):
     n = u.split("/")[1]; d = f"{C}/custom_nodes/{n}"
     if P.isdir(d) and os.listdir(d): continue
     rm(d); st(f"node {n} ({i}/3)", 0.75 + 0.07 * i)
     if gc(u, d, 0).returncode: rm(d)
     elif rq and F(f"{d}/requirements.txt"): pip("-r", f"{d}/requirements.txt", ck=0)
   open(STAMP, "w").write("ok\n"); st("ComfyUI ready", 1.0)
 except sp.CalledProcessError as e: fail(f"install ({e.returncode}): {tail(ILOG) or e}")

def download(plan):
 st("checking models", 0.02, "download")
 if not plan: st("no model", 1.0); return []
 pend, rdy = [], []
 for r, p, s, g in plan:
  fn, dst = B(p), f"{C}/models/{s}/{B(p)}"
  (rdy.append(f"{s}/{fn}") if F(dst) and P.getsize(dst) > 1048576 else pend.append((r, p, s, int(g * 1e9))))
 if not pend: st(f"{len(rdy)} ready", 1.0); return rdy
 tot, free = sum(x[3] for x in pend), shutil.disk_usage("/").free
 if tot and free < tot + int(4e9): fail(f"disk low: {free/1e9:.1f}G<{tot/1e9:.1f}G+4G")
 os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"; importlib.invalidate_caches()
 from huggingface_hub import hf_hub_download as hfd
 b0 = 0
 for i, (r, p, s, esz) in enumerate(pend, 1):
  fn, dst = B(p), f"{C}/models/{s}/{B(p)}"; md(P.dirname(dst)); rm(STG); ev = threading.Event()
  def rep(k=i, nm=fn, b=b0):
   while not ev.wait(8):
    g = b + dsz(STG); st(f"[{k}/{len(pend)}] {nm} ({g/1e9:.1f}" + (f"/{tot/1e9:.1f}G)" if tot else "G)"), (g / tot) if tot else None); hb()
  st(f"[{i}/{len(pend)}] {fn}", (b0 / tot) if tot else 0.05); bg(rep)
  try: src = hfd(r, p, cache_dir=STG, token=TOK or None)
  except Exception as e: fail(f"download {fn} ({r}): {e}")
  finally: ev.set()
  b = P.realpath(src); sz = P.getsize(b); shutil.move(b, dst); rm(STG); b0 += esz or sz; rdy.append(f"{s}/{fn}")
 rm(P.expanduser("~/.cache/huggingface/xet")); st(f"downloaded {len(rdy)}", 1.0); return rdy

def ksrv():
 if _srv[0] and _srv[0].poll() is None:
  try: os.killpg(_srv[0].pid, signal.SIGTERM)
  except OSError: pass

def main():
 md(RUN); signal.signal(signal.SIGTERM, lambda *_: (ksrv(), st("stopped", s="failed"), os._exit(143))); done = threading.Event()
 bg(lambda: (hb(), [hb() for _ in iter(lambda: done.wait(25), True)]))
 if PORT == 8080: fail("port 8080 reserved")
 try: plan, tpl = build_download_plan(PRESET, EXTRA)
 except ValueError as e: fail(str(e))
 st("checking GPU", g="detect"); gpu, mib = None, 0
 try:
  o = sp.check_output(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], text=True, stderr=sp.DEVNULL).strip()
  if o: n, m = o.splitlines()[0].split(",", 1); gpu, mib = n.strip(), int(float(m))
 except Exception: pass
 fgb = lambda: round(shutil.disk_usage("/").free / 1e9, 1)
 if not gpu and PRESET != "none": fail("no GPU; select L4 or A100")
 st(f"{gpu or 'CPU'} ({mib} MiB), {fgb():.1f}G free", 1.0)
 install(); rdy = download(plan); sp.run(["pkill", "-f", f"{C}/main.py"]); time.sleep(2)
 try: socket.create_connection(("127.0.0.1", PORT), 1).close(); fail(f"port {PORT} busy")
 except OSError: pass
 vf = choose_vram_flag(VMODE, mib); st(f"starting ComfyUI on {PORT} ({vf or 'default'})", 0.3, "server")
 proc = _srv[0] = sp.Popen([sys.executable, *shlex.split(f"-u {C}/main.py --listen 127.0.0.1 --port {PORT} --enable-cors-header --preview-method auto {vf}"), *shlex.split(XARGS)], cwd=C, env=clean_env(), stdout=open(SLOG, "w"), stderr=sp.STDOUT, stdin=sp.DEVNULL, start_new_session=True)
 hj = lambda u: json.loads(ur.urlopen(f"http://127.0.0.1:{PORT}{u}", timeout=5).read().decode())
 stats, t0 = None, time.time()
 while time.time() - t0 < 420 and proc.poll() is None:
  try:
   x = hj("/system_stats")
   if isinstance(x, dict) and "system" in x: stats = x; break
  except Exception: pass
  hb(); time.sleep(3)
 if not stats: ksrv(); fail(f"ComfyUI failed: {tail()}")
 devs = stats.get("devices") or []
 if gpu and (devs[0].get("type") if devs else "") != "cuda": fail(f"no CUDA: {tail()}")
 ver = stats.get("system", {}).get("comfyui_version", "latest"); done.set()
 st(f"ComfyUI {ver} ready ({gpu or 'CPU'}, {len(rdy)} models) - '{tpl}'", 1.0, s="ready", o=dict(comfyui_version=ver, gpu=gpu or "CPU", vram_total_mib=mib, vram_mode=vf.lstrip("-") or "default", preset=PRESET, recommended_template=tpl, models_ready=len(rdy), disk_free_gb=fgb(), output_dir=f"{C}/output"))
 while True:
  time.sleep(20)
  if proc.poll() is not None: fail(f"ComfyUI exited: {tail()}")
  try:
   q = hj("/queue")
   if isinstance(q, dict) and (q.get("queue_running") or q.get("queue_pending")): hb()
  except Exception: pass

if __name__ == "__main__":
 if sys.argv[1:] == ["--self-test"]:
  assert all(build_download_plan(n, "")[1] for n in PRESETS) and clean_env()["GIT_TERMINAL_PROMPT"] == "0" and choose_vram_flag("auto", 22500) == "" and choose_vram_flag("normalvram", 22500) == ""
  print("self-test ok"); sys.exit(0)
 try: main()
 except SystemExit: raise
 except Exception as e: fail(f"worker error: {type(e).__name__}: {e}")
