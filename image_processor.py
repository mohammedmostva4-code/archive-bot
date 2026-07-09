import os
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

def process_template(images_paths, title, details, output_path):
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(base_dir, 'template.png')
        
        if not os.path.exists(template_path):
            return False
            
        template = Image.open(template_path).convert('RGB')
        width, height = template.size # المفترض 940x788

        draw = ImageDraw.Draw(template)

        # 1. مسح منطقة النصوص الأصلية بدقة (تغطية المستطيل السفلي بالكامل)
        # لون الخلفية الكحلي الداكن للقالب
        bg_color = (46, 51, 77) 
        # مسح المنطقة من بكسل 535 إلى 690 عمودياً، ومن 40 إلى 900 أفقياً
        draw.rectangle([30, 535, 910, 690], fill=bg_color)

        # 2. إحداثيات المربعات الأربعة (ضبط دقيق جداً لمنع التداخل مع الخطوط البيضاء)
        # الإطارات البيضاء في القالب تشكل شبكة، سنضع الصور داخل الفراغات تماماً
        # الإحداثيات (يسار، أعلى، يمين، أسفل)
        boxes = [
            (475, 14, 925, 264), # أعلى يمين
            (14, 14, 464, 264),  # أعلى يسار
            (475, 275, 925, 525),# أسفل يمين
            (14, 275, 464, 525)  # أسفل يسار
        ]

        # 3. معالجة الصور ودمجها (Center Crop & Fill)
        for i, img_path in enumerate(images_paths):
            if i >= 4: break
            if not os.path.exists(img_path): continue
                
            img = Image.open(img_path).convert('RGB')
            target_w = boxes[i][2] - boxes[i][0]
            target_h = boxes[i][3] - boxes[i][1]
            
            # Smart Crop
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

        # 4. كتابة النصوص الجديدة بتنسيق احترافي
        font_bold_path = os.path.join(base_dir, 'fonts', 'Bold.ttf')
        font_reg_path = os.path.join(base_dir, 'fonts', 'Regular.ttf')

        if os.path.exists(font_bold_path):
            title_font = ImageFont.truetype(font_bold_path, 40)
        else:
            title_font = ImageFont.load_default()

        if os.path.exists(font_reg_path):
            details_font = ImageFont.truetype(font_reg_path, 22)
        else:
            details_font = ImageFont.load_default()

        # معالجة النصوص العربية
        display_title = get_display(arabic_reshaper.reshape(title))
        display_details = get_display(arabic_reshaper.reshape(details))

        # رسم العنوان (توسيط أفقي)
        t_bbox = draw.textbbox((0, 0), display_title, font=title_font)
        t_w = t_bbox[2] - t_bbox[0]
        draw.text(((width - t_w) // 2, 565), display_title, font=title_font, fill="white")

        # رسم التفاصيل (توسيط أفقي)
        d_bbox = draw.textbbox((0, 0), display_details, font=details_font)
        d_w = d_bbox[2] - d_bbox[0]
        draw.text(((width - d_w) // 2, 635), display_details, font=details_font, fill="white")

        # حفظ النتيجة
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        template.save(output_path, "PNG", quality=100)
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False
