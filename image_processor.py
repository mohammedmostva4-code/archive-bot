import os
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
import datetime

def get_dynamic_font(text, font_path, max_width, initial_size):
    size = initial_size
    font = ImageFont.truetype(font_path, size)
    while size > 12:
        reshaped = get_display(arabic_reshaper.reshape(text))
        bbox = ImageDraw.Draw(Image.new('RGB', (1, 1))).textbbox((0, 0), reshaped, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            break
        size -= 1
        font = ImageFont.truetype(font_path, size)
    return font

def process_template(images_paths, title, details, output_path):
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(base_dir, 'template.png')
        
        if not os.path.exists(template_path):
            return False
            
        template = Image.open(template_path).convert('RGB')
        width, height = template.size 

        draw = ImageDraw.Draw(template)

        # 1. مسح المنطقة السفلية بلون الخلفية الأصلي
        bg_color = (46, 51, 77) 
        draw.rectangle([10, 530, width-10, 700], fill=bg_color)

        # 2. إحداثيات المربعات (مطابقة دقيقة للمثال لملء الفراغات)
        # الإطارات البيضاء في القالب عرضها حوالي 5-10 بكسل
        mid_x = width // 2
        mid_y = 268
        
        boxes = [
            (mid_x + 3, 13, width - 13, mid_y - 3), # أعلى يمين
            (13, 13, mid_x - 3, mid_y - 3),         # أعلى يسار
            (mid_x + 3, mid_y + 3, width - 13, 523),# أسفل يمين
            (13, mid_y + 3, mid_x - 3, 523)         # أسفل يسار
        ]

        # 3. دمج الصور
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

        # 4. تنسيق النصوص (مطابقة للمثال الاحترافي)
        font_bold_path = os.path.join(base_dir, 'fonts', 'Bold.ttf')
        font_reg_path = os.path.join(base_dir, 'fonts', 'Regular.ttf')

        max_w = width - 80
        
        # العنوان (كبير وبارز)
        title_font = get_dynamic_font(title, font_bold_path, max_w, 36)
        reshaped_title = get_display(arabic_reshaper.reshape(title))
        t_bbox = draw.textbbox((0, 0), reshaped_title, font=title_font)
        draw.text(((width - (t_bbox[2]-t_bbox[0])) // 2, 545), reshaped_title, font=title_font, fill="white")

        # التفاصيل (أصغر قليلاً وأسفل العنوان)
        details_font = get_dynamic_font(details, font_reg_path, max_w, 24)
        reshaped_details = get_display(arabic_reshaper.reshape(details))
        d_bbox = draw.textbbox((0, 0), reshaped_details, font=details_font)
        draw.text(((width - (d_bbox[2]-d_bbox[0])) // 2, 600), reshaped_details, font=details_font, fill="white")

        # التاريخ (كما في المثال، يظهر بشكل تلقائي)
        today = datetime.datetime.now()
        date_str = f"الموافق {today.strftime('%d')} {today.strftime('%B')} {today.year}م"
        # يمكن إضافة التاريخ الهجري يدوياً أو برمجياً إذا توفرت المكتبة، هنا سنضع نصاً مشاباً للمثال
        date_font = ImageFont.truetype(font_reg_path, 16)
        reshaped_date = get_display(arabic_reshaper.reshape(date_str))
        date_bbox = draw.textbbox((0, 0), reshaped_date, font=date_font)
        draw.text(((width - (date_bbox[2]-date_bbox[0])) // 2, 655), reshaped_date, font=date_font, fill="#cccccc")

        template.save(output_path, "PNG", quality=100)
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False
