import sys
from pathlib import Path
import json

def main(filepath_str):
    try:
        p = Path(filepath_str)
        if not p.exists():
            print(f"檔案不存在: {p}", file=sys.stderr)
            sys.exit(1)
            
        if p.suffix.lower() in ('.xlsx', '.xls'):
            import pandas as pd
            df = pd.read_excel(p)
            print(df.to_csv(index=False), end='')
        else:
            print(p.read_text(encoding='utf-8'), end='')
    except Exception as e:
        print(f"Worker 解析失敗: {e}", file=sys.stderr)
        sys.exit(1)

def generate_ppt(output_path_str, template_path_str=None):
    try:
        from pptx import Presentation
        from pptx.util import Pt
        
        import os
        if sys.stdin is None:
            # PyInstaller windowed mode fallback
            content = b""
            try:
                while True:
                    chunk = os.read(0, 8192)
                    if not chunk: break
                    content += chunk
            except Exception:
                pass
            content = content.decode('utf-8')
        else:
            content = sys.stdin.read()
        
        if template_path_str:
            prs = Presentation(template_path_str)
        else:
            prs = Presentation()
        
        # Simple Markdown to PPT parser
        # Expects: # Slide Title \n ## Content \n - point 1...
        slides_data = content.split('# Slide')
        
        for slide_text in slides_data:
            slide_text = slide_text.strip()
            if not slide_text:
                continue
                
            lines = slide_text.split('\n')
            title = lines[0].strip().lstrip(':').strip()
            
            # Find bullet points
            bullets = []
            notes = []
            in_notes = False
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                if line.lower().startswith('## notes') or line.lower().startswith('## 備註') or line.lower().startswith('## 講者備註'):
                    in_notes = True
                    continue
                if line.startswith('##'):
                    in_notes = False
                    continue
                    
                if in_notes:
                    notes.append(line)
                elif line.startswith('- ') or line.startswith('* '):
                    bullets.append(line[2:].strip())
                elif line:
                    bullets.append(line)
                    
            slide_layout = prs.slide_layouts[1] # Title and Content
            slide = prs.slides.add_slide(slide_layout)
            
            title_shape = slide.shapes.title
            body_shape = slide.placeholders[1]
            
            if title_shape:
                title_shape.text = title
                
            if body_shape and bullets:
                tf = body_shape.text_frame
                tf.text = bullets[0]
                for bullet in bullets[1:]:
                    p = tf.add_paragraph()
                    p.text = bullet
                    p.level = 0
                    
            if notes and slide.has_notes_slide:
                notes_slide = slide.notes_slide
                notes_tf = notes_slide.notes_text_frame
                notes_tf.text = '\n'.join(notes)
                
        if sys.stdout is None:
            import os
            os.write(1, b"OK")
        else:
            print("OK", end='')
    except Exception as e:
        msg = f"Worker 轉存 PPT 失敗: {e}\n"
        if sys.stderr is None:
            import os
            os.write(2, msg.encode('utf-8', 'replace'))
        else:
            print(msg, file=sys.stderr)
        sys.exit(1)
