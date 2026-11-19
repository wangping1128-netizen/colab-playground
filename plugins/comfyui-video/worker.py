#!/usr/bin/env python3
import base64 as b64,importlib as il,json,os,re,shlex,shutil as sh,signal as sg,socket,subprocess as sp,sys,threading as th,time,urllib.request as ur,zlib
OE,P,PY,sx,sl,tm,G,SO=os.environ,os.path,sys.executable,shlex.split,time.sleep,time.time,1e9,sp.STDOUT
E,B,F,dn,gs,rm,fm=OE.get,P.basename,P.isfile,P.dirname,P.getsize,lambda p:sh.rmtree(p,1),re.fullmatch
inp=lambda k,d="":(E("PLUGIN_INPUT_"+k)or d).strip()
RUN,C,LH,RQ=E("PLUGIN_RUN_DIR","/tmp/cpg"),"/content/ComfyUI","127.0.0.1","requirements.txt"
MP,M,CN,SF,HB,TOK=f"{C}/main.py",f"{C}/models",f"{C}/custom_nodes",E("PLUGIN_STATUS_FILE",f"{RUN}/status.json"),E("PLUGIN_HEARTBEAT",""),E("PLUGIN_HF_TOKEN","")
STG,STM,SL,IL="/content/.hf",f"{C}/.cpg_v1",f"{RUN}/server.log",f"{RUN}/install.log"
PR,EX,EN,VM,XA=inp("PRESET","wan2.2-ti2v-5b"),inp("EXTRA_DOWNLOADS"),inp("EXTRA_NODES"),inp("VRAM_MODE","auto"),inp("EXTRA_ARGS")
IND,PORT,A=inp("INSTALL_NODES","1")in("1","true","yes"),int(float(inp("PORT","8188"))),r"[A-Za-z0-9_]"
RG,SPL=A+r"[\w.-]*",lambda s:[x.strip()for x in re.split(r"[;\n]+",s or"")if x.strip()]
D="diffusion_models unet checkpoints text_encoders clip clip_vision vae loras latent_upscale_models upscale_models audio_encoders controlnet".split()
# PRESETS (zlib+b85)
_PB="c-rllU2oeq6o&tbpsNiqW$P<(b1`6Uv86zY6<PNI1O`Fdl+9J5RFRe)4Eygpq?ACWDOq097U**4$n<&1_dL`&Cx5#c<18b4v<Z=9LFHcEx$of7JF<7K!z<?l-OKUYjI606bLV%qqPaV|yK`UXS#pnlDc9p>HM$Pnk-K6^vK1`nILlWw72_s6-h?<wgNopy+;Y0YjLRur=DaF%=?RihNx8^NVTs|60^gg=N1dW+UXmjvEVtz%$5SC`fh!0AYVhkV!;8efFeG&Z(CL+tU<Iap37aa#_|uN^uu5?lEO1MjS4k0JvioEx9Q@cF`LTD|BUKUFK2N1=$MCSvHuzedU^+Z3*{)a}HYviu7H;BQ%;)n_8<O&vkz1P363+H?L`s@`DMqwZ14&dvGV%NuNd7w{soV!%jDlc+)D9FSHy{2)@T~JKa>LdeS+eCvF>aRH0D-{hA@Yg|$<markSqxoNnU2OL^^9)6`jFLtX!~eL3!|?s(nT91X-A9{2UfZTiF|F(i15quvp@4A(kYirZ@GsNEAdelA>l+iS~gOLvTAxoNe&{x*Bim77pQF(<~zq@*yibCO4=k^S{u;eokiOnDyuoN*x|W9kQ6hm144wbweQn>J3a+N!h0K%}=*i&I_ggBT6kNG^hz;^L0Or%hQoxJ=H}?vjR%eQ*7+aq^9`oYjl&}{)pbQJx$TCP11gA)Lea)9v8DEQUwwfda*6TmR;2qRV7p1%pKu@7w9$=#S3*a{~+9fM@~GeucPxb<+Oy*IX7AiSP5GRAgCx(@IPTG72~5zT1#Lhf#VsJw4*E?-$8$3B48Ig#9^Ds81MHfXiPDUvM}LTd$H=r;=-)?b}@Bho5R3I+b#9sh1zmend(Oi1lwsl>qj%Ex4l2lSmo;mXu>>af?|lS&u=}r#p%ckhaA37J<WHYSG?{d+luP;?BRoMBL!9qVB%=`V8>qdP0y+Kc=9L7eGQ6n0G)RS#uLa&`{mG$v1&4(hhq6vDVATHV%bfV_jx$(SNyg~-fa2(mT>6o&}A?w6w(Ui>-uq1==^4C>H@l1jr4a=TH{l2HLAK#gymRC>og3jfk!r++Q9K34Bo^ThT+RaH_(RpQ*%;1Pjzt*ITsm8Q@l>^i;d3yslKe~iH2*c)E~GTH{)`5_iV#}bz#t3o}Y&URaTbC8b8i0=e%;J=Nh(5S%E92f{X=QxBkS?HZC`Qgu`iM=(biV52r6QJ}ZrSDh`d|wJEaoOc2`si{pIv=3({s_E|a9Q66Rmi-MWw4PAaLa+s3U^!3U-z7ErCv!26ni2Y!u2C<>Z^+PYP&O%{p^Y*dEA3n31R?}*L$!8c_#~Wg4?>P^Xq~|)gk+!4O75UPv$lpMkc+ROx%&g3Jf<j)hLj6KG=!eI&%;*373wQ9Wu>"
PRESETS={k:(v[0],[tuple(x)for x in v[1]])for k,v in json.loads(zlib.decompress(b64.b85decode(_PB))).items()}
ND=(("Comfy-Org/ComfyUI-Manager",1),("city96/ComfyUI-GGUF",0),("Kosinkadink/ComfyUI-VideoHelperSuite",0))
_stg,_srv=["detect"],[None]
md,bg,du=lambda p:os.makedirs(p,exist_ok=1),lambda fn:th.Thread(target=fn,daemon=1).start(),lambda:sh.disk_usage("/").free
red=lambda t:str(t).replace(TOK,"***")if len(TOK)>=4 else str(t)
tail=lambda p=SL:red(" | ".join(x.strip()for x in open(p,errors="replace").readlines()[-8:]if x.strip()))if F(p)else""
def dsz(p):
 t=0
 for r,_,fs in os.walk(p):
  for f in fs:
   try:t+=gs(f"{r}/{f}")
   except OSError:pass
 return t
def st(m="",p=None,g=None,s="running",o=None):
 if g:_stg[0]=g
 d=dict(state=s,stage=_stg[0],message=red(m))
 if p is not None:d["progress"]=max(0.,min(1.,float(p)))
 if o:d["outputs"]=o
 print(s,_stg[0],d["message"],flush=True);md(dn(SF)or".");open(SF+".tmp","w").write(json.dumps(d));os.replace(SF+".tmp",SF)
fail=lambda m:(st(m,s="failed"),sys.exit(1))
def hb():
 if HB:
  try:md(dn(HB));open(HB,"a").close();os.utime(HB)
  except OSError:pass
def clean_env():
 L="/usr/local/";e={k:v for k,v in OE.items()if not k.startswith("PLUGIN_")};g=e.get
 e["PATH"]=f"{L}cuda/bin:{L}bin:"+g("PATH","/usr/bin:/bin")
 ld=[p for p in("/usr/lib64-nvidia",L+"nvidia/lib64",g("LD_LIBRARY_PATH",""))if p and(":"in p or P.isdir(p))]
 if ld:e["LD_LIBRARY_PATH"]=":".join(ld)
 return dict(e,PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True",PYTHONUNBUFFERED="1",GIT_TERMINAL_PROMPT="0")
choose_vram_flag=lambda m,v:""if m=="normalvram"else f"--{m}"if m in("highvram","lowvram")else"--highvram"if v>=70000 else""if v>=20000 else"--lowvram"if v>0 else"--cpu"
def build_download_plan(pr,ex):
 if pr not in PRESETS:raise ValueError(f"unknown preset {pr!r}")
 tpl,it=PRESETS[pr][0],list(PRESETS[pr][1])
 ok=lambda p:p and p[0]!="/"and not{"",".",".."}&set(p.split("/"))
 for e in SPL(ex):
  m=fm(f"({RG}/{RG}):([^\\\\]+)->([^\\\\]+)",e)
  if not m:raise ValueError(f"invalid extra {e!r}")
  r,p,s=m[1],m[2].strip(),re.sub(r"^models/","",m[3].strip().strip("/"))
  if not(ok(p)and ok(s)):raise ValueError(f"invalid extra {e!r}")
  it.append((r,p,s,0.))
 sn,pl=set(),[]
 for x in it:
  k=f"{x[2]}/{B(x[1])}"
  if k not in sn:sn.add(k);pl.append(x)
 return pl,tpl
def parse_extra_nodes(en):
 o,sn=[],set()
 for e in SPL(en):
  p,at,r=re.sub(r"^https?://github\.com/","",e).partition("@");p=re.sub(r"\.git$","",p.rstrip("/"));g="/"in p
  if(at and not r)or".."in p+r or not fm(f"{RG}/{RG}"if g else RG,p)or(r and(not fm(A+r"[\w./+-]*",r)or(not g and"/"in r))):raise ValueError(f"invalid node {e!r}")
  x=("git",p,r)if g else("cnr",f"{p}@{r}"if r else p,"")
  if x not in sn:sn.add(x);o.append(x)
 return o
def install(env,en=()):
 md("/content");cm=f"{CN}/ComfyUI-Manager/cm-cli.py"
 try:
  with open(IL,"a")as lg:
   rx=lambda*c,ck=1,cw=None,ev=None:sp.run(c,cwd=cw,stdout=lg,stderr=SO,env=ev or env,check=bool(ck))
   pip=lambda*a,ck=1:rx(PY,"-m","pip","install","-q",*a,ck=ck)
   gc=lambda u,d,ck=1,rf="":rx("git","clone",*([]if rf else["--depth=1"]),f"https://github.com/{u}.git",d,ck=ck)
   st("setup hf_hub",.1,"install");pip("-U","huggingface_hub[hf_xet]")
   if not(F(MP)and F(STM)):
    if not F(MP):st("cloning ComfyUI",.25);rm(C);gc("Comfy-Org/ComfyUI",C)
    st("installing deps",.55);pip("-r",f"{C}/{RQ}");pip("gguf","imageio-ffmpeg","opencv-python-headless")
   for s in(*D,"../output","../input"):md(P.normpath(f"{M}/{s}"))
   base=ND if IND else((ND[0],)if any(k=="cnr"for k,_,_ in en)else())
   ns=[("git",u,"",rq,0)for u,rq in base]+[(k,u,r,1,1)for k,u,r in en];N=len(ns)
   for i,(k,u,r,rq,ip)in enumerate(ns,1):
    st(f"node {B(u)} ({i}/{N})",.7+.28*i/N);hb()
    if k=="git":
     d=f"{CN}/{B(u)}"
     if P.isdir(d)and os.listdir(d):continue
     rm(d)
     if gc(u,d,0,r).returncode:rm(d);continue
     if r:rx("git","-C",d,"checkout",r,ck=0)
     if rq and F(f"{d}/{RQ}"):pip("-r",f"{d}/{RQ}",ck=0)
     if ip and F(f"{d}/install.py"):rx(PY,"install.py",ck=0,cw=d)
    elif F(cm):rx(PY,cm,"install",u,"--mode","remote",ck=0,cw=C,ev={**env,"COMFYUI_PATH":C})
   open(STM,"w").write("ok\n");st("ComfyUI ready",1.)
 except sp.CalledProcessError as e:fail(f"install ({e.returncode}): {tail(IL)or e}")
def download(pl):
 st("checking models",.02,"download")
 if not pl:st("no model",1.);return[]
 pd,rd=[],[]
 for r,p,s,g in pl:
  fn=B(p);dst=f"{M}/{s}/{fn}"
  (rd.append(f"{s}/{fn}")if F(dst)and gs(dst)>1048576 else pd.append((r,p,s,fn,dst,int(g*G))))
 if not pd:st(f"{len(rd)} ready",1.);return rd
 tot,fr,N=sum(x[5]for x in pd),du(),len(pd)
 if tot and fr<tot+4*G:fail(f"disk low: {fr/G:.1f}G<{tot/G:.1f}G+4G")
 OE["HF_HUB_DISABLE_PROGRESS_BARS"]="1";il.invalidate_caches()
 from huggingface_hub import hf_hub_download as hfd
 b0=0
 for i,(r,p,s,fn,dst,ez)in enumerate(pd,1):
  md(dn(dst));rm(STG);ev=th.Event()
  def rep(k=i,nm=fn,b=b0):
   while not ev.wait(8):g=b+dsz(STG);st(f"[{k}/{N}] {nm} ({g/G:.1f}"+(f"/{tot/G:.1f}G)"if tot else"G)"),g/tot if tot else None);hb()
  st(f"[{i}/{N}] {fn}",b0/tot if tot else .05);bg(rep)
  try:src=hfd(r,p,cache_dir=STG,token=TOK or None)
  except Exception as e:fail(f"download {fn} ({r}): {e}")
  finally:ev.set()
  b=P.realpath(src);b0+=ez or gs(b);sh.move(b,dst);rm(STG);rd.append(f"{s}/{fn}")
 rm(P.expanduser("~/.cache/huggingface/xet"));st(f"downloaded {len(rd)}",1.);return rd
def ksrv():
 s=_srv[0]
 if s and s.poll()is None:
  try:os.killpg(s.pid,sg.SIGTERM)
  except OSError:pass
def main():
 md(RUN);sg.signal(sg.SIGTERM,lambda*_:(ksrv(),st("stopped",s="failed"),os._exit(143)));dn0=th.Event()
 bg(lambda:(hb(),[hb()for _ in iter(lambda:dn0.wait(25),True)]))
 if PORT==8080:fail("port 8080 reserved")
 try:pl,tpl=build_download_plan(PR,EX);en=parse_extra_nodes(EN)
 except ValueError as e:fail(str(e))
 st("checking GPU",g="detect");gpu,mib=None,0
 try:
  o=sp.check_output(sx("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits"),text=True,stderr=sp.DEVNULL).strip()
  if o:n,m=o.splitlines()[0].split(",",1);gpu,mib=n.strip(),int(float(m))
 except Exception:pass
 fgb,gn=lambda:round(du()/G,1),gpu or"CPU"
 if not gpu and PR!="none":fail("no GPU; select L4 or A100")
 st(f"{gn} ({mib} MiB), {fgb():.1f}G free",1.)
 env=clean_env();install(env,en);rd=download(pl);sp.run(["pkill","-f",MP]);sl(2)
 try:socket.create_connection((LH,PORT),1).close();fail(f"port {PORT} busy")
 except OSError:pass
 vf=choose_vram_flag(VM,mib);st(f"starting ComfyUI on {PORT} ({vf or'default'})",.3,"server")
 pr=_srv[0]=sp.Popen([PY,*sx(f"-u {MP} --listen {LH} --port {PORT} --enable-cors-header --preview-method auto {vf}"),*sx(XA)],cwd=C,env=env,stdout=open(SL,"w"),stderr=SO,stdin=sp.DEVNULL,start_new_session=True)
 hj=lambda u:json.loads(ur.urlopen(f"http://{LH}:{PORT}{u}",timeout=5).read())
 ss,t0=None,tm()
 while tm()-t0<420 and pr.poll()is None:
  try:
   x=hj("/system_stats")
   if type(x)is dict and"system"in x:ss=x;break
  except Exception:pass
  hb();sl(3)
 if not ss:ksrv();fail(f"ComfyUI failed: {tail()}")
 dv=ss.get("devices")or[]
 if gpu and(dv[0].get("type")if dv else"")!="cuda":fail(f"no CUDA: {tail()}")
 ver=ss.get("system",{}).get("comfyui_version","latest");dn0.set()
 st(f"ComfyUI {ver} ready ({gn}, {len(rd)} models) - '{tpl}'",1.,s="ready",o=dict(comfyui_version=ver,gpu=gn,vram_total_mib=mib,vram_mode=vf.lstrip("-")or"default",preset=PR,recommended_template=tpl,models_ready=len(rd),disk_free_gb=fgb(),output_dir=f"{C}/output"))
 while True:
  sl(20)
  if pr.poll()is not None:fail(f"ComfyUI exited: {tail()}")
  try:
   q=hj("/queue")
   if type(q)is dict and(q.get("queue_running")or q.get("queue_pending")):hb()
  except Exception:pass
if __name__=="__main__":
 if sys.argv[1:]==["--self-test"]:
  assert all(build_download_plan(n,"")[1]for n in PRESETS)and clean_env()["GIT_TERMINAL_PROMPT"]=="0"and choose_vram_flag("auto",22500)==choose_vram_flag("normalvram",22500)==""and parse_extra_nodes("https://github.com/a/b.git@abc;c-d@1.0;a/b@abc")==[("git","a/b","abc"),("cnr","c-d@1.0","")]
  for bad in("../a/b","a/b@-x","a/b@","a/b/c","a/b;rm -rf /"):
   try:parse_extra_nodes(bad);raise AssertionError(bad)
   except ValueError:pass
  print("self-test ok");sys.exit(0)
 try:main()
 except SystemExit:raise
 except Exception as e:fail(f"worker error: {type(e).__name__}: {e}")
