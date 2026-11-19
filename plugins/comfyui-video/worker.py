#!/usr/bin/env python3
import importlib as il,json,os,re,shlex,shutil as sh,signal,socket,subprocess as sp,sys,threading as th,time,urllib.request as ur
OE,P,PY,sx,sl,tm=os.environ,os.path,sys.executable,shlex.split,time.sleep,time.time
E,B,F,J,dn,gs,rm=OE.get,P.basename,P.isfile,P.join,P.dirname,P.getsize,lambda p:sh.rmtree(p,True)
inp=lambda k,d="":(E("PLUGIN_INPUT_"+k)or d).strip()
RUN,C,LH,RQ=E("PLUGIN_RUN_DIR","/tmp/cpg"),"/content/ComfyUI","127.0.0.1","requirements.txt"
M,SF,HB,TOK=f"{C}/models",E("PLUGIN_STATUS_FILE",f"{RUN}/status.json"),E("PLUGIN_HEARTBEAT",""),E("PLUGIN_HF_TOKEN","")
STG,STM,SL,IL="/content/.hf",f"{C}/.cpg_v1",f"{RUN}/server.log",f"{RUN}/install.log"
PR,EX,VM,XA=inp("PRESET","wan2.2-ti2v-5b"),inp("EXTRA_DOWNLOADS"),inp("VRAM_MODE","auto"),inp("EXTRA_ARGS")
IND,PORT=inp("INSTALL_NODES","1")in("1","true","yes"),int(float(inp("PORT","8188")))
D=tuple("diffusion_models unet checkpoints text_encoders clip clip_vision vae loras latent_upscale_models upscale_models audio_encoders controlnet".split())
CO,LR="Comfy-Org/","Lightricks/"
RP=(CO+"Wan-2.2",CO+"Hunyuan-Video-1.5",LR+"LTX-2.3",LR+"LTX-2.3-fp8",CO+"ltx-2",CO+"MiniMax-H3",LR+"LTX-2.5",CO+"gemma-4",LR+"LTX-2.5-22b-IC-LoRA-Pixel-Spatial-Upscaler")
_p=lambda s:[(RP[int(r)],(n[1:]if n[0]=="/"else f"{''if n[0]=='~'else'split_files/'}{D[int(d)]}/{n.lstrip('~')}")+".safetensors",D[int(d)],float(g))for r,d,n,g in(t.split(":")for t in s.split())]
F8,I8,CI,H3,L5P,BF,UX="_fp8_scaled","int8_convrot","comfy-int8-convrot","minimax_h3_","ltx-2.5-","-bf16","upscaler-x2"
WT,H7,L2="0:3:umt5_xxl_fp8_e4m3fn_scaled:6.7","1:0:hunyuanvideo1.5_720p_","/ltx-2.3-22b-"
W2,HV,TV,IV,HL="Wan 2.2 ","Hunyuan Video 1.5 ","Text to Video","Image to Video",("high","low")
TI,G4,GE=f"Text/{IV}",f"6:3:~gemma4-12b-with-proj-{L5P}","7:3:~gemma4_e2b_it_"
HC,LC=f"1:3:qwen_2.5_vl_7b{F8}:8.8 1:3:byt5_small_glyphxl_fp16:0.5 1:6:hunyuanvideo15_vae_fp16:0.5",f"4:3:gemma_3_12B_it{F8}:13.2 2:8:/ltx-2.3-spatial-{UX}-1.1:1"
MH=f"5:3:~qwen3vl_32b_{H3}nvfp4_awq:15.7 5:6:~{H3}video_vae_{I8}:2.8 5:6:~{H3}audio_vae_fp32:0.6"
L5=f"6:0:~{L5P}22b-distilled-transformer-{CI}:21.5 6:6:~{L5P}video-vae{BF}:2.5 6:6:~{L5P}audio-vae{BF}:0.5 6:8:~{L5P}latent-spatial-{UX}{BF}-1.0:1"
h3=lambda k,t:f"5:0:~{H3}{k}a_pruned_{I8}:21 5:7:~{H3}{k}_turbo_{t}_comfyui_bf16:2 {MH}"
w14=lambda k,v:" ".join([*(f"0:0:wan2.2_{k}_{h}_noise_14B{F8}:14.3"for h in HL),*(f"0:7:wan2.2_{k}_lightx2v_4steps_lora_{v}_{h}_noise:0.6"for h in HL),WT,"0:6:wan_2.1_vae:0.3"])
PRESETS={k:(t,_p(s))for k,(t,s)in{
"minimax-h3-ti2v":(f"MiniMax H3: {TI}",h3("fl2v","8step_v1.0")),
"minimax-h3-r2v":("MiniMax H3: Reference to Video",h3("ref2v","4step_v0.1")),
"ltx2.5-22b-int8":(f"LTX-2.5 {TI}",f"{L5} {G4}{CI}:15.4 {GE}{I8}:4.8"),
"ltx2.5-22b-dfr":(f"LTX-2.5 DFR: {IV}",f"{L5} {G4}bf16:25 {GE}bf16:9.5 6:8:~{L5P}latent-temporal-{UX}{BF}-1.0:0.5 8:7:/{L5P}22b-ic-lora-pixel-spatial-{UX}-1.0:1"),
"wan2.2-ti2v-5b":(f"{W2}5B Video Generation",f"0:0:wan2.2_ti2v_5B_fp16:10 {WT} 0:6:wan2.2_vae:1.4"),
"wan2.2-i2v-14b-fp8":(f"{W2}14B {IV}",w14("i2v","v1")),
"wan2.2-t2v-14b-fp8":(f"{W2}14B {TV}",w14("t2v","v1.1")),
"hunyuan1.5-720p-t2v":(f"{HV}{TV}",f"{H7}t2v_fp16:16.7 {HC}"),
"hunyuan1.5-720p-i2v":(f"{HV}{IV}",f"{H7}i2v_cfg_distilled{F8}:8.5 1:5:sigclip_vision_patch14_384:0.8 {HC}"),
"ltx2.3-22b-distilled-fp8":(f"LTX-2.3 {TI} (Distilled)",f"3:2:{L2}distilled-fp8:29.5 {LC}"),
"ltx2.3-22b-dev-fp8":(f"LTX-2.3 {TI}",f"3:2:{L2}dev-fp8:29.5 2:7:{L2}distilled-lora-384-1.1:7.6 {LC}"),
"none":("Browse Templates -> Video",""),
}.items()}
ND=((CO+"ComfyUI-Manager",1),("city96/ComfyUI-GGUF",0),("Kosinkadink/ComfyUI-VideoHelperSuite",0))
_stg,_srv=["detect"],[None]
md=lambda p:os.makedirs(p,exist_ok=True)
bg=lambda fn:th.Thread(target=fn,daemon=True).start()
du=lambda:sh.disk_usage("/").free
red=lambda t:str(t).replace(TOK,"***")if len(TOK)>=4 else str(t)
tail=lambda p=SL:red(" | ".join(x.strip()for x in open(p,errors="replace").readlines()[-8:]if x.strip()))if F(p)else""
def dsz(p):
 t=0
 for r,_,fs in os.walk(p):
  for f in fs:
   try:t+=gs(J(r,f))
   except OSError:pass
 return t
def st(m="",p=None,g=None,s="running",o=None):
 if g:_stg[0]=g
 d=dict(state=s,stage=_stg[0],message=red(m))
 if p is not None:d["progress"]=max(0.0,min(1.0,float(p)))
 if o:d["outputs"]=o
 print(s,_stg[0],d["message"],flush=True)
 md(dn(SF)or".");open(SF+".tmp","w").write(json.dumps(d));os.replace(SF+".tmp",SF)
def fail(m):st(m,s="failed");sys.exit(1)
def hb():
 if HB:
  try:md(dn(HB));open(HB,"a").close();os.utime(HB,None)
  except OSError:pass
def clean_env():
 e={k:v for k,v in OE.items()if not k.startswith("PLUGIN_")}
 e["PATH"]="/usr/local/cuda/bin:/usr/local/bin:"+e.get("PATH","/usr/bin:/bin")
 ld=[p for p in("/usr/lib64-nvidia","/usr/local/nvidia/lib64",e.get("LD_LIBRARY_PATH",""))if p and(":"in p or P.isdir(p))]
 if ld:e["LD_LIBRARY_PATH"]=":".join(ld)
 return dict(e,PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True",PYTHONUNBUFFERED="1",GIT_TERMINAL_PROMPT="0")
choose_vram_flag=lambda m,v:""if m=="normalvram"else(f"--{m}"if m in("highvram","lowvram")else("--highvram"if v>=70000 else""if v>=20000 else"--lowvram"if v>0 else"--cpu"))
def build_download_plan(pr,ex):
 if pr not in PRESETS:raise ValueError(f"unknown preset {pr!r}")
 tpl,items=PRESETS[pr][0],list(PRESETS[pr][1])
 ok=lambda p:p and"/"!=p[0]and all(x not in("",".","..")for x in p.split("/"))
 for e in(x.strip()for x in re.split(r"[;\n]+",ex or"")if x.strip()):
  m=re.fullmatch(r"([A-Za-z0-9_][\w.-]*/[A-Za-z0-9_][\w.-]*):([^\\]+)->([^\\]+)",e)
  if not m:raise ValueError(f"invalid extra {e!r}")
  r,p,s=m[1],m[2].strip(),m[3].strip().strip("/")
  s=s[7:]if s.startswith("models/")else s
  if not(ok(p)and ok(s)):raise ValueError(f"invalid extra {e!r}")
  items.append((r,p,s,0.0))
 seen,plan=set(),[]
 for r,p,s,g in items:
  k=f"{s}/{B(p)}"
  if k not in seen:seen.add(k);plan.append((r,p,s,g))
 return plan,tpl
def install():
 md("/content");env=clean_env()
 try:
  with open(IL,"a")as log:
   rx=lambda*c,ck=1:sp.run(c,stdout=log,stderr=sp.STDOUT,env=env,check=bool(ck))
   pip=lambda*a,ck=1:rx(PY,"-m","pip","install","-q",*a,ck=ck)
   gc=lambda u,d,ck=1:rx("git","clone","--depth=1",f"https://github.com/{u}.git",d,ck=ck)
   st("setup hf_hub",0.1,"install");pip("-U","huggingface_hub[hf_xet]")
   if not(F(f"{C}/main.py")and F(STM)):
    if not F(f"{C}/main.py"):st("cloning ComfyUI",0.25);rm(C);gc(CO+"ComfyUI",C)
    st("installing deps",0.55);pip("-r",f"{C}/{RQ}");pip("gguf","imageio-ffmpeg","opencv-python-headless")
   for s in(*D,"../output","../input"):md(P.normpath(f"{M}/{s}"))
   if IND:
    for i,(u,rq)in enumerate(ND,1):
     n=u.split("/")[1];d=f"{C}/custom_nodes/{n}"
     if P.isdir(d)and os.listdir(d):continue
     rm(d);st(f"node {n} ({i}/3)",0.75+0.07*i)
     if gc(u,d,0).returncode:rm(d)
     elif rq and F(f"{d}/{RQ}"):pip("-r",f"{d}/{RQ}",ck=0)
   open(STM,"w").write("ok\n");st("ComfyUI ready",1.0)
 except sp.CalledProcessError as e:fail(f"install ({e.returncode}): {tail(IL)or e}")
def download(plan):
 st("checking models",0.02,"download")
 if not plan:st("no model",1.0);return[]
 pend,rdy=[],[]
 for r,p,s,g in plan:
  fn,dst=B(p),f"{M}/{s}/{B(p)}"
  (rdy.append(f"{s}/{fn}")if F(dst)and gs(dst)>1048576 else pend.append((r,p,s,int(g*1e9))))
 if not pend:st(f"{len(rdy)} ready",1.0);return rdy
 tot,free=sum(x[3]for x in pend),du()
 if tot and free<tot+int(4e9):fail(f"disk low: {free/1e9:.1f}G<{tot/1e9:.1f}G+4G")
 OE["HF_HUB_DISABLE_PROGRESS_BARS"]="1";il.invalidate_caches()
 from huggingface_hub import hf_hub_download as hfd
 b0=0
 for i,(r,p,s,esz)in enumerate(pend,1):
  fn,dst=B(p),f"{M}/{s}/{B(p)}";md(dn(dst));rm(STG);ev=th.Event()
  def rep(k=i,nm=fn,b=b0):
   while not ev.wait(8):
    g=b+dsz(STG);st(f"[{k}/{len(pend)}] {nm} ({g/1e9:.1f}"+(f"/{tot/1e9:.1f}G)"if tot else"G)"),(g/tot)if tot else None);hb()
  st(f"[{i}/{len(pend)}] {fn}",(b0/tot)if tot else 0.05);bg(rep)
  try:src=hfd(r,p,cache_dir=STG,token=TOK or None)
  except Exception as e:fail(f"download {fn} ({r}): {e}")
  finally:ev.set()
  b=P.realpath(src);sz=gs(b);sh.move(b,dst);rm(STG);b0+=esz or sz;rdy.append(f"{s}/{fn}")
 rm(P.expanduser("~/.cache/huggingface/xet"));st(f"downloaded {len(rdy)}",1.0);return rdy
def ksrv():
 if _srv[0]and _srv[0].poll()is None:
  try:os.killpg(_srv[0].pid,signal.SIGTERM)
  except OSError:pass
def main():
 md(RUN);signal.signal(signal.SIGTERM,lambda*_:(ksrv(),st("stopped",s="failed"),os._exit(143)));done=th.Event()
 bg(lambda:(hb(),[hb()for _ in iter(lambda:done.wait(25),True)]))
 if PORT==8080:fail("port 8080 reserved")
 try:plan,tpl=build_download_plan(PR,EX)
 except ValueError as e:fail(str(e))
 st("checking GPU",g="detect");gpu,mib=None,0
 try:
  o=sp.check_output(["nvidia-smi","--query-gpu=name,memory.total","--format=csv,noheader,nounits"],text=True,stderr=sp.DEVNULL).strip()
  if o:n,m=o.splitlines()[0].split(",",1);gpu,mib=n.strip(),int(float(m))
 except Exception:pass
 fgb,gn=lambda:round(du()/1e9,1),gpu or"CPU"
 if not gpu and PR!="none":fail("no GPU; select L4 or A100")
 st(f"{gn} ({mib} MiB), {fgb():.1f}G free",1.0)
 install();rdy=download(plan);sp.run(["pkill","-f",f"{C}/main.py"]);sl(2)
 try:socket.create_connection((LH,PORT),1).close();fail(f"port {PORT} busy")
 except OSError:pass
 vf=choose_vram_flag(VM,mib);st(f"starting ComfyUI on {PORT} ({vf or'default'})",0.3,"server")
 proc=_srv[0]=sp.Popen([PY,*sx(f"-u {C}/main.py --listen {LH} --port {PORT} --enable-cors-header --preview-method auto {vf}"),*sx(XA)],cwd=C,env=clean_env(),stdout=open(SL,"w"),stderr=sp.STDOUT,stdin=sp.DEVNULL,start_new_session=True)
 hj=lambda u:json.loads(ur.urlopen(f"http://{LH}:{PORT}{u}",timeout=5).read().decode())
 stats,t0=None,tm()
 while tm()-t0<420 and proc.poll()is None:
  try:
   x=hj("/system_stats")
   if type(x)is dict and"system"in x:stats=x;break
  except Exception:pass
  hb();sl(3)
 if not stats:ksrv();fail(f"ComfyUI failed: {tail()}")
 devs=stats.get("devices")or[]
 if gpu and(devs[0].get("type")if devs else"")!="cuda":fail(f"no CUDA: {tail()}")
 ver=stats.get("system",{}).get("comfyui_version","latest");done.set()
 st(f"ComfyUI {ver} ready ({gn}, {len(rdy)} models) - '{tpl}'",1.0,s="ready",o=dict(comfyui_version=ver,gpu=gn,vram_total_mib=mib,vram_mode=vf.lstrip("-")or"default",preset=PR,recommended_template=tpl,models_ready=len(rdy),disk_free_gb=fgb(),output_dir=f"{C}/output"))
 while True:
  sl(20)
  if proc.poll()is not None:fail(f"ComfyUI exited: {tail()}")
  try:
   q=hj("/queue")
   if type(q)is dict and(q.get("queue_running")or q.get("queue_pending")):hb()
  except Exception:pass
if __name__=="__main__":
 if sys.argv[1:]==["--self-test"]:
  assert all(build_download_plan(n,"")[1]for n in PRESETS)and clean_env()["GIT_TERMINAL_PROMPT"]=="0"and choose_vram_flag("auto",22500)==""and choose_vram_flag("normalvram",22500)==""
  print("self-test ok");sys.exit(0)
 try:main()
 except SystemExit:raise
 except Exception as e:fail(f"worker error: {type(e).__name__}: {e}")
