import os
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

def process_template(images_paths, title, details, output_path):
    # تحميل القالب
    template_path = '/home/ubuntu/archive-bot/template.png'
    template = Image.open(template_path).convert('RGB')
    width, height = template.size # (940, 788)

    # إحداثيات المربعات الأربعة (تقديرية بناءً على الصورة)
    # المربع 1: أعلى يسار، المربع 2: أعلى يمين
    # المربع 3: أسفل يسار، المربع 4: أسفل يمين
    # الحدود البيضاء تقسم الصورة تقريباً في المنتصف
    
    # تحسين الإحداثيات بناءً على أبعاد 940x788
    # المربعات تنتهي تقريباً عند y=570 قبل منطقة النص
    margin = 12
    mid_x = width // 2
    mid_y = 285 # تقريباً منتصف منطقة الصور
    
    box_width = (width // 2) - (margin * 2)
    box_height = 270 # ارتفاع كل مربع صورة
    
    # الترتيب: [أعلى يمين، أعلى يسار، أسفل يمين، أسفل يسار] ليناسب القراءة العربية
    boxes = [
        (mid_x + margin // 2, margin, width - margin, margin + box_height), # أعلى يمين
        (margin, margin, mid_x - margin // 2, margin + box_height),         # أعلى يسار
        (mid_x + margin // 2, margin + box_height + margin, width - margin, margin + 2 * box_height + margin), # أسفل يمين
        (margin, margin + box_height + margin, mid_x - margin // 2, margin + 2 * box_height + margin)          # أسفل يسار
    ]

    for i, img_path in enumerate(images_paths):
        if i >= 4: break
        img = Image.open(img_path).convert('RGB')
        
        # تغيير حجم الصورة لتناسب المربع مع الحفاظ على التناسب أو القص
        target_w = boxes[i][2] - boxes[i][0]
        target_h = boxes[i][3] - boxes[i][1]
        
        # Crop and resize to fill the box
        img_ratio = img.width / img.height
        target_ratio = target_w / target_h
        
        if img_ratio > target_ratio:
            # الصورة أعرض من اللازم
            new_w = int(target_h * img_ratio)
            img = img.resize((new_w, target_h), Image.Resampling.LANCZOS)
            left = (new_w - target_w) // 2
            img = img.crop((left, 0, left + target_w, target_h))
        else:
            # الصورة أطول من اللازم
            new_h = int(target_w / img_ratio)
            img = img.resize((target_w, new_h), Image.Resampling.LANCZOS)
            top = (new_h - target_h) // 2
            img = img.crop((0, top, target_w, top + target_h))
            
        template.paste(img, (boxes[i][0], boxes[i][1]))

    # الكتابة على الصورة
    draw = ImageDraw.Draw(template)
    
    # استخدام خطوط النظام
    font_bold_path = "/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf"
    font_reg_path = "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"
    
    title_font = ImageFont.truetype(font_bold_path, 45)
    details_font = ImageFont.truetype(font_reg_path, 25)

    # معالجة النصوص العربية (Reshaping & Bidi)
    reshaped_title = arabic_reshaper.reshape(title)
    display_title = get_display(reshaped_title)
    
    reshaped_details = arabic_reshaper.reshape(details)
    display_details = get_display(reshaped_details)

    # حساب موقع النص (توسيط)
    # العنوان في y=600 تقريباً
    title_bbox = draw.textbbox((0, 0), display_title, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]
    draw.text(((width - title_w) // 2, 580), display_title, font=title_font, fill="white")

    # التفاصيل في y=660 تقريباً
    details_bbox = draw.textbbox((0, 0), display_details, font=details_font)
    details_w = details_bbox[2] - details_bbox[0]
    draw.text(((width - details_w) // 2, 645), display_details, font=details_font, fill="white")

    template.save(output_path)
    return output_path

if __name__ == "__main__":
    # اختبار سريع إذا لزم الأمر
    pass
