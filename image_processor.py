import os
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

def process_template(images_paths, title, details, output_path):
    try:
        # تحميل القالب
        template_path = '/home/ubuntu/archive-bot/template.png'
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template not found at {template_path}")
            
        template = Image.open(template_path).convert('RGB')
        width, height = template.size # (940, 788)

        # إحداثيات المربعات الأربعة (تحسين بناءً على أبعاد 940x788)
        # الهوامش والمسافات الفاصلة بين المربعات
        margin_top = 10
        margin_side = 10
        gap = 10
        
        box_width = (width - (2 * margin_side) - gap) // 2
        box_height = 275 # ارتفاع المربعات العلوية والسفلية
        
        # الترتيب: [أعلى يمين، أعلى يسار، أسفل يمين، أسفل يسار]
        boxes = [
            (width // 2 + gap // 2, margin_top, width - margin_side, margin_top + box_height), # أعلى يمين
            (margin_side, margin_top, width // 2 - gap // 2, margin_top + box_height),         # أعلى يسار
            (width // 2 + gap // 2, margin_top + box_height + gap, width - margin_side, margin_top + 2 * box_height + gap), # أسفل يمين
            (margin_side, margin_top + box_height + gap, width // 2 - gap // 2, margin_top + 2 * box_height + gap)          # أسفل يسار
        ]

        for i, img_path in enumerate(images_paths):
            if i >= 4: break
            img = Image.open(img_path).convert('RGB')
            
            target_w = boxes[i][2] - boxes[i][0]
            target_h = boxes[i][3] - boxes[i][1]
            
            # Crop and resize to fill the box
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

        # الكتابة على الصورة
        draw = ImageDraw.Draw(template)
        
        # خطوط النظام
        font_bold_path = "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf"
        font_reg_path = "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"
        
        if not os.path.exists(font_bold_path):
            font_bold_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if not os.path.exists(font_reg_path):
            font_reg_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

        title_font = ImageFont.truetype(font_bold_path, 42)
        details_font = ImageFont.truetype(font_reg_path, 22)

        # معالجة النصوص العربية
        reshaped_title = arabic_reshaper.reshape(title)
        display_title = get_display(reshaped_title)
        
        reshaped_details = arabic_reshaper.reshape(details)
        display_details = get_display(reshaped_details)

        # حساب موقع النص وتوسيطه
        title_bbox = draw.textbbox((0, 0), display_title, font=title_font)
        title_w = title_bbox[2] - title_bbox[0]
        draw.text(((width - title_w) // 2, 575), display_title, font=title_font, fill="white")

        details_bbox = draw.textbbox((0, 0), display_details, font=details_font)
        details_w = details_bbox[2] - details_bbox[0]
        draw.text(((width - details_w) // 2, 640), display_details, font=details_font, fill="white")

        template.save(output_path, "PNG")
        return True
    except Exception as e:
        print(f"Error in image processing: {e}")
        return False
