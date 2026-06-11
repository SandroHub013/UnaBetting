import os
import subprocess
import shutil
import json
from pathlib import Path

# Configurazione
HF_DIR = Path("hf_test")
ASSETS_DIR = HF_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

VOICE = "it-IT-DiegoNeural" # Voce mascolina, profonda e dinamica

# Copione Diviso per Scene
SCENES = [
    {
        "id": "scene_1_hook",
        "text": "Il 99% delle persone che scommette sul tennis perde soldi. Credono sia sfortuna. Ma la verità è che stanno giocando contro un supercomputer. Per batterli, ti serve un'arma più grossa.",
        "image": r"G:\tennis betting\video_mission\snapshots\scene_1_hook.png"
    },
    {
        "id": "scene_2_solution",
        "text": "Nessuna emozione, solo pura matematica. Abbiamo dato in pasto a un'Intelligenza Artificiale un decennio di partite ATP. La nostra rete neurale legge la biomeccanica dei giocatori: l'altezza, la fatica, la mano dominante.",
        "image": r"G:\tennis betting\video_mission\snapshots\scene_2_solution.png"
    },
    {
        "id": "scene_3_quantum",
        "text": "Siamo arrivati al 67 percento di accuratezza. Ma stiamo per rompere il sistema. Stiamo implementando reti Transformer per capire l'effetto sasso carta forbice tra stili di gioco opposti.",
        "image": r"G:\tennis betting\video_mission\snapshots\scene_3_quantum.png"
    },
    {
        "id": "scene_4_mission",
        "text": "Stiamo costruendo il fondo speculativo sportivo più avanzato al mondo. Tre Intelligenze Artificiali lavorano 24 ore su 24 per estrarre Alpha da mercati inefficienti. La probabilità è l'unica religione.",
        "image": r"G:\tennis betting\video_mission\snapshots\scene_4_mission.png"
    }
]

def generate_voiceover(text, output_file):
    print(f"Generazione audio per: {text[:30]}...")
    cmd = f'edge-tts --voice "{VOICE}" --text "{text}" --write-media "{output_file}"'
    subprocess.run(cmd, shell=True, check=True)

def get_audio_duration(file_path):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", str(file_path)
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return float(result.stdout.strip())

def build_video():
    clips_html = []
    current_time = 0.0
    
    for i, scene in enumerate(SCENES):
        audio_filename = f"{scene['id']}.mp3"
        audio_path = ASSETS_DIR / audio_filename
        
        # 1. Genera Audio TTS
        if not audio_path.exists():
            generate_voiceover(scene["text"], audio_path)
            
        # 2. Ottieni durata audio
        duration = get_audio_duration(audio_path)
        
        # 3. Copia Immagine
        img_src = scene["image"]
        if os.path.exists(img_src):
            img_filename = f"{scene['id']}_{Path(img_src).name}"
            img_dest = ASSETS_DIR / img_filename
            if not img_dest.exists():
                shutil.copy2(img_src, img_dest)
        else:
            print(f"[!] Errore: Immagine mancante {img_src}")
            return
            
        # 4. Aggiungi i tag HTML
        clips_html.append(f'''
      <!-- Scene {i+1}: {scene["id"]} -->
      <img src="assets/{img_filename}" class="clip" data-start="{current_time:.3f}" data-duration="{duration:.3f}" data-track-index="0" />
      <audio src="assets/{audio_filename}" data-start="{current_time:.3f}" data-duration="{duration:.3f}" data-track-index="1"></audio>
        ''')
        
        current_time += duration

    total_duration = current_time

    # Genera l'HTML di Hyperframes
    html_content = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{
        margin: 0;
        width: 1920px;
        height: 1080px;
        overflow: hidden;
        background: #000;
      }}
      .clip {{
        position: absolute;
        top: 0; left: 0;
        width: 100%; height: 100%;
        object-fit: cover;
      }}
    </style>
  </head>
  <body>
    <div
      id="root"
      data-composition-id="main"
      data-start="0"
      data-duration="{total_duration:.3f}"
      data-width="1920"
      data-height="1080"
    >
      {''.join(clips_html)}
    </div>

    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      
      // Aggiungiamo un leggero effetto di zoom (Ken Burns) su ogni immagine tramite GSAP
      gsap.utils.toArray('.clip').forEach(clip => {{
         const start = parseFloat(clip.getAttribute('data-start'));
         const duration = parseFloat(clip.getAttribute('data-duration'));
         tl.fromTo(clip, 
            {{ scale: 1.0, transformOrigin: "center center" }},
            {{ scale: 1.1, duration: duration, ease: "none" }},
            start
         );
      }});

      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""

    index_html_path = HF_DIR / "index.html"
    index_html_path.write_text(html_content, encoding="utf-8")
    print(f"File index.html generato in {index_html_path}")

    # Render video usando hyperframes
    print("Rendering finale con hyperframes...")
    render_cmd = ["npx", "hyperframes", "render", "-o", "Manifesto_Tennis_AI.mp4"]
    subprocess.run(render_cmd, cwd=str(HF_DIR), shell=True, check=True)
    print(f"Rendering Completato! Il video è pronto in {HF_DIR / 'Manifesto_Tennis_AI.mp4'}")

if __name__ == "__main__":
    print("Avvio Motore di Rendering Autonomo con Hyperframes...")
    try:
        build_video()
    except Exception as e:
        print(f"Errore critico durante la generazione: {e}")
