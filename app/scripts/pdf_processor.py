import fitz
import re

class PDFProcessor:
    def __init__(self, file_path):
        self.file_path = file_path
        self.address_pattern = re.compile(
            r"(вул\.|просп\.|пров\.|бульв\.|м-н|пл\.|шосе)\s*([^,]+?)\s*,\s*буд\.?\s*([0-9a-zA-Zа-яА-ЯіІїЇєЄґҐ/-]+)", 
            re.IGNORECASE
        )

    def parse_and_split(self):
        cards = []
        doc = fitz.open(self.file_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            full_width = page.rect.width
            full_height = page.rect.height
            
            start_markers = page.search_for("ПРИВАТНЕ АКЦІОНЕРНЕ")
            y_starts = sorted([m.y0 for m in start_markers])
            
            if not y_starts or len(y_starts) > 3:
                h3 = full_height / 3.0
                y_starts = [0, h3, h3 * 2]
                
            rects = []
            for i in range(len(y_starts)):
                y_top = max(0, y_starts[i] - 5)
                
                if i < len(y_starts) - 1:
                    y_bottom = y_starts[i+1]
                else:
                    y_bottom = full_height
                    
                rects.append(fitz.Rect(0, y_top, full_width, y_bottom))

            for i, r in enumerate(rects):
                text = page.get_text("text", clip=r, sort=True)
                clean_text = ' '.join(text.replace('\n', ' ').split())
                
                if len(clean_text) < 50:
                    continue
                
                spozhivach_idx = clean_text.lower().find("споживачу:")
                if spozhivach_idx != -1:
                    target_text = clean_text[spozhivach_idx:]
                else:
                    target_text = clean_text

                match = self.address_pattern.search(target_text)
                
                if match:
                    street_type = match.group(1).strip()
                    street_name = match.group(2).strip()
                    house = match.group(3).strip()
                    full_street = f"{street_type} {street_name}".replace("  ", " ")
                else:
                    full_street = "Не розпізнано вулицю"
                    house = f"Стор. {page_num+1}, Блок {i+1}"

                cards.append({
                    "page_num": page_num,
                    "rect_index": i, 
                    "y_top": r.y0,   
                    "y_bottom": r.y1,
                    "street": full_street,
                    "house": house,
                })
                
        doc.close()
        return cards

    def group_by_street_and_house(self, cards):
        grouped = {}
        for card in cards:
            s = card['street']
            h = card['house']
            if s not in grouped:
                grouped[s] = []
            if h not in grouped[s]:
                grouped[s].append(h)
                
        for s in grouped:
            def sort_key(house_str):
                numbers = re.findall(r'\d+', house_str)
                return int(numbers[0]) if numbers else float('inf')
                
            try:
                grouped[s] = sorted(grouped[s], key=sort_key)
            except:
                grouped[s] = sorted(grouped[s])
            
        return [{"street": k, "houses": v} for k, v in grouped.items()]

    def sort_cards_by_address(self, cards):
        def sort_key(x):
            numbers = re.findall(r'\d+', x['house'])
            house_num = int(numbers[0]) if numbers else float('inf')
            return (x['street'], house_num)
            
        return sorted(cards, key=sort_key)

    def filter_cards_by_houses(self, cards, distribution_list):
        filtered = []
        for card in cards:
            for dist in distribution_list:
                if card['street'] == dist['street'] and str(card['house']) == str(dist['house']):
                    filtered.append(card)
        return filtered

    def merge_cards_to_pdf(self, sorted_cards, output_path):
        src_doc = fitz.open(self.file_path)
        out_doc = fitz.open()
        
        if not sorted_cards:
            src_doc.close()
            out_doc.close()
            return
            
        original_rect = src_doc[0].rect
        full_width = original_rect.width
        h3 = original_rect.height / 3.0 
        
        chunks = [sorted_cards[i:i + 3] for i in range(0, len(sorted_cards), 3)]
        
        for chunk in chunks:
            new_page = out_doc.new_page(width=original_rect.width, height=original_rect.height)
            
            for i, card in enumerate(chunk):
                src_page_num = card["page_num"]
                y_top = card["y_top"]
                y_bottom = card["y_bottom"]
                
                # Магія очищення (Redaction)
                temp_doc = fitz.open()
                temp_doc.insert_pdf(src_doc, from_page=src_page_num, to_page=src_page_num)
                temp_page = temp_doc[0]
                
                # Позначаємо до видалення все, що вище нашої картки
                if y_top > 0:
                    rect_top = fitz.Rect(0, 0, full_width, y_top)
                    temp_page.add_redact_annot(rect_top, cross_out=False)
                
                # Позначаємо до видалення все, що нижче нашої картки
                if y_bottom < original_rect.height:
                    rect_bot = fitz.Rect(0, y_bottom, full_width, original_rect.height)
                    temp_page.add_redact_annot(rect_bot, cross_out=False)
                    
                # Фізично випалюємо зайвий текст
                temp_page.apply_redactions()
                
                src_rect = fitz.Rect(0, y_top, full_width, y_bottom)
                card_h = y_bottom - y_top
                dst_rect = fitz.Rect(0, i * h3, full_width, i * h3 + card_h)
                
                # Вставляємо вже чистий шматок на фінальну сторінку
                new_page.show_pdf_page(dst_rect, temp_doc, 0, clip=src_rect)
                temp_doc.close()
                
        out_doc.save(output_path)
        src_doc.close()
        out_doc.close()