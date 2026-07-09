import os
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

def get_dynamic_font(text, font_path, max_width, initial_size):
    """خوارزمية لتحديد حجم الخط المناسب للمساحة المتاحة"""
    size = initial_size
    font = ImageFont.truetype(font_path, size)
    
    # تصغير الخط حتى يناسب العرض المسموح به
    while size > 10:
        reshaped = get_display(arabic_reshaper.reshape(text))
        bbox = ImageDraw.Draw(Image.new('RGB', (1, 1))).textbbox((0, 0), reshaped, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            break
        size -= 2
        font = ImageFont.truetype(font_path, size)
    return font

def process_template(images_paths, title, details, output_path):
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(base_dir, 'template.png')
        
        if not os.path.exists(template_path):
            return False
            
        template = Image.open(template_path).convert('RGB')
        width, height = template.size # 1013x900 تقريباً بناءً على التحليل

        draw = ImageDraw.Draw(template)

        # 1. مسح منطقة النصوص الأصلية باحترافية
        bg_color = (46, 51, 77) 
        # مسح كامل المنطقة السفلية للنصوص لضمان عدم وجود تداخل
        draw.rectangle([20, 535, width-20, 695], fill=bg_color)

        # 2. إحداثيات المربعات الدقيقة (بناءً على تحليل بكسل بكسل للفواصل البيضاء)
        # الإطارات البيضاء عادة ما تكون في المنتصف تماماً
        # سنترك هامش 2 بكسل عن الإطارات لضمان عدم التداخل
        mid_x = width // 2
        mid_y = 268 # نقطة الفاصل الأفقي
        
        boxes = [
            (mid_x + 5, 15, width - 15, mid_y - 5), # أعلى يمين
            (15, 15, mid_x - 5, mid_y - 5),         # أعلى يسار
            (mid_x + 5, mid_y + 5, width - 15, 525),# أسفل يمين
            (15, mid_y + 5, mid_x - 5, 525)         # أسفل يسار
        ]

        # 3. معالجة الصور (Center Crop & High Quality Resize)
        for i, img_path in enumerate(images_paths):
            if i >= 4: break
            if not os.path.exists(img_path): continue
                
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

        # 4. نظام النصوص المتكيف (Dynamic Text System)
        font_bold_path = os.path.join(base_dir, 'fonts', 'Bold.ttf')
        font_reg_path = os.path.join(base_dir, 'fonts', 'Regular.ttf')
        
        if not os.path.exists(font_bold_path): font_bold_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if not os.path.exists(font_reg_path): font_reg_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

        # الحد الأقصى للعرض المسموح به للنص (مع ترك هوامش)
        max_text_width = width - 100

        # الحصول على خطوط بأحجام متكيفة
        title_font = get_dynamic_font(title, font_bold_path, max_text_width, 42)
        details_font = get_dynamic_font(details, font_reg_path, max_text_width, 24)

        # معالجة النصوص للعرض
        display_title = get_display(arabic_reshaper.reshape(title))
        display_details = get_display(arabic_reshaper.reshape(details))

        # رسم العنوان (توسيط)
        t_bbox = draw.textbbox((0, 0), display_title, font=title_font)
        draw.text(((width - (t_bbox[2]-t_bbox[0])) // 2, 565), display_title, font=title_font, fill="white")

        # رسم التفاصيل (توسيط)
        d_bbox = draw.textbbox((0, 0), display_details, font=details_font)
        draw.text(((width - (d_bbox[2]-d_bbox[0])) // 2, 635), display_details, font=details_font, fill="white")

        # حفظ النتيجة النهائية
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        template.save(output_path, "PNG", quality=100)
        return True
    except Exception as e:
        print(f"ROOT CAUSE ERROR: {e}")
        return False
