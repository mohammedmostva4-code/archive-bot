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
            
        # فتح القالب
        template = Image.open(template_path).convert('RGB')
        width, height = template.size # 940x788 تقريباً

        draw = ImageDraw.Draw(template)

        # 1. مسح النصوص الأصلية من القالب (تغطيتها بلون الخلفية)
        # لون الخلفية في القالب هو كحلي داكن (2e334d تقريباً)
        bg_color = (46, 51, 77) 
        
        # مسح منطقة العنوان والتفاصيل (تعديل الإحداثيات لتغطية النص القديم بالكامل)
        draw.rectangle([50, 540, 890, 680], fill=bg_color)

        # 2. إحداثيات المربعات الأربعة (تغطية كاملة للمساحة الزرقاء)
        # تقسيم المساحة العلوية إلى 4 مربعات متساوية مع فواصل بسيطة
        margin = 15
        gap = 10
        box_w = (width - 2*margin - gap) // 2
        box_h = 255 # ارتفاع المربع الواحد
        
        # الترتيب: أعلى يمين، أعلى يسار، أسفل يمين، أسفل يسار
        boxes = [
            (width//2 + gap//2, margin, width - margin, margin + box_h),
            (margin, margin, width//2 - gap//2, margin + box_h),
            (width//2 + gap//2, margin + box_h + gap, width - margin, margin + 2*box_h + gap),
            (margin, margin + box_h + gap, width//2 - gap//2, margin + 2*box_h + gap)
        ]

        # 3. دمج الصور مع Smart Crop (ملء المربع بالكامل)
        for i, img_path in enumerate(images_paths):
            if i >= 4: break
            if not os.path.exists(img_path): continue
                
            img = Image.open(img_path).convert('RGB')
            target_w = boxes[i][2] - boxes[i][0]
            target_h = boxes[i][3] - boxes[i][1]
            
            # حساب النسب لعمل Crop ذكي (Center Crop)
            img_ratio = img.width / img.height
            target_ratio = target_w / target_h
            
            if img_ratio > target_ratio:
                # الصورة أعرض من المربع -> قص الجوانب
                new_w = int(target_h * img_ratio)
                img = img.resize((new_w, target_h), Image.Resampling.LANCZOS)
                left = (new_w - target_w) // 2
                img = img.crop((left, 0, left + target_w, target_h))
            else:
                # الصورة أطول من المربع -> قص الأعلى والأسفل
                new_h = int(target_w / img_ratio)
                img = img.resize((target_w, new_h), Image.Resampling.LANCZOS)
                top = (new_h - target_h) // 2
                img = img.crop((0, top, target_w, top + target_h))
                
            template.paste(img, (boxes[i][0], boxes[i][1]))

        # 4. كتابة النصوص الجديدة بجودة عالية
        font_bold_path = os.path.join(base_dir, 'fonts', 'Bold.ttf')
        font_reg_path = os.path.join(base_dir, 'fonts', 'Regular.ttf')

        # أحجام الخطوط بناءً على النموذج الاحترافي
        title_size = 38
        details_size = 20

        if os.path.exists(font_bold_path):
            title_font = ImageFont.truetype(font_bold_path, title_size)
        else:
            title_font = ImageFont.load_default()

        if os.path.exists(font_reg_path):
            details_font = ImageFont.truetype(font_reg_path, details_size)
        else:
            details_font = ImageFont.load_default()

        # معالجة النصوص العربية (Reshaping & Bidi)
        display_title = get_display(arabic_reshaper.reshape(title))
        display_details = get_display(arabic_reshaper.reshape(details))

        # رسم العنوان (توسيط)
        t_bbox = draw.textbbox((0, 0), display_title, font=title_font)
        draw.text(((width - (t_bbox[2]-t_bbox[0])) // 2, 560), display_title, font=title_font, fill="white")

        # رسم التفاصيل (توسيط)
        d_bbox = draw.textbbox((0, 0), display_details, font=details_font)
        draw.text(((width - (d_bbox[2]-d_bbox[0])) // 2, 625), display_details, font=details_font, fill="white")

        # حفظ النتيجة بجودة عالية
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        template.save(output_path, "PNG", quality=100)
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False
