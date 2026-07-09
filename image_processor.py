import os
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

def process_template(images_paths, title, details, output_path):
    try:
        # استخدام المسار النسبي الصحيح للمجلد الحالي
        base_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(base_dir, 'template.png')
        
        if not os.path.exists(template_path):
            print(f"DEBUG: Template not found at {template_path}")
            return False
            
        template = Image.open(template_path).convert('RGB')
        width, height = template.size

        # إحداثيات المربعات
        margin_top = 10
        margin_side = 10
        gap = 10
        box_width = (width - (2 * margin_side) - gap) // 2
        box_height = 275
        
        boxes = [
            (width // 2 + gap // 2, margin_top, width - margin_side, margin_top + box_height),
            (margin_side, margin_top, width // 2 - gap // 2, margin_top + box_height),
            (width // 2 + gap // 2, margin_top + box_height + gap, width - margin_side, margin_top + 2 * box_height + gap),
            (margin_side, margin_top + box_height + gap, width // 2 - gap // 2, margin_top + 2 * box_height + gap)
        ]

        for i, img_path in enumerate(images_paths):
            if i >= 4: break
            if not os.path.exists(img_path):
                print(f"DEBUG: Image {i} not found at {img_path}")
                continue
                
            img = Image.open(img_path).convert('RGB')
            target_w = boxes[i][2] - boxes[i][0]
            target_h = boxes[i][3] - boxes[i][1]
            
            img_ratio = img.width / img.height
            target_ratio = target_w / target_h
            
            if img_ratio > target_ratio:
                new_w = int(target_h * img_ratio)
                img = img.resize((new_w, target_h), Image.Resampling.LANCZOS)
                left = (new_w - target_w) // 2
                img = img.crop((left, 0, left + target_w, target_h))
            else:
                new_h = int(target_w / img_ratio)
                img = img.resize((target_w, new_h), Image.Resampling.LANCZOS)
                top = (new_h - target_h) // 2
                img = img.crop((0, top, target_w, top + target_h))
                
            template.paste(img, (boxes[i][0], boxes[i][1]))

        # الكتابة باستخدام الخطوط المحلية
        draw = ImageDraw.Draw(template)
        font_bold = os.path.join(base_dir, 'fonts', 'Bold.ttf')
        font_reg = os.path.join(base_dir, 'fonts', 'Regular.ttf')

        # تحميل الخطوط مع التحقق
        try:
            if os.path.exists(font_bold):
                title_font = ImageFont.truetype(font_bold, 42)
            else:
                title_font = ImageFont.load_default()
                
            if os.path.exists(font_reg):
                details_font = ImageFont.truetype(font_reg, 22)
            else:
                details_font = ImageFont.load_default()
        except Exception as fe:
            print(f"DEBUG: Font error: {fe}")
            title_font = ImageFont.load_default()
            details_font = ImageFont.load_default()

        # معالجة النصوص العربية
        display_title = get_display(arabic_reshaper.reshape(title))
        display_details = get_display(arabic_reshaper.reshape(details))

        # توسيط النصوص
        title_bbox = draw.textbbox((0, 0), display_title, font=title_font)
        draw.text(((width - (title_bbox[2] - title_bbox[0])) // 2, 575), display_title, font=title_font, fill="white")

        details_bbox = draw.textbbox((0, 0), display_details, font=details_font)
        draw.text(((width - (details_bbox[2] - details_bbox[0])) // 2, 640), display_details, font=details_font, fill="white")

        # التأكد من وجود مجلد المخرجات
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        template.save(output_path, "PNG")
        return True
    except Exception as e:
        print(f"CRITICAL ERROR in image processing: {e}")
        return False
