import pandas as pd
import numpy as np
import calendar
import os
import shutil
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Border, Side, Alignment

def run_calls_analysis(input_path: str, output_dir: str) -> str:
    # --- СТИЛІ (Краса в стилі warnings.py) ---
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="50A74B", end_color="50A74B", fill_type="solid")
    
    controller_font = Font(bold=True, size=12)
    controller_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
    
    yellow_fill = PatternFill(start_color='FFFF00', end_color='FFFF00', fill_type='solid')
    bold_font = Font(bold=True)
    
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                         top=Side(style='thin'), bottom=Side(style='thin'))
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # 1. Читаємо дані
    df_raw = pd.read_excel(input_path, sheet_name=0, header=None)
    
    # Зберігаємо шапку (перші 3 рядки), щоб намалювати її красиво
    header_rows = df_raw.iloc[:3].values.tolist()
    
    data_df = df_raw.iloc[3:].copy()
    
    # --- ФІКС: Видаляємо "фантомні" порожні рядки ---
    data_df = data_df.dropna(subset=[1]) 
    data_df = data_df.where(pd.notnull(data_df), None)

    # Сортування: ПІБ (колонка 1), Дата (колонка 5)
    data_df[5] = pd.to_datetime(data_df[5], errors='coerce', dayfirst=True)
    data_df = data_df.sort_values(by=[1, 5])

    # --- ЗБЕРЕЖЕННЯ ---
    input_filename = os.path.basename(input_path)
    output_filename = input_filename.replace('.xlsx', '_Оброблений.xlsx')
    output_path = os.path.join(output_dir, output_filename)
    
    shutil.copyfile(input_path, output_path)
    wb = load_workbook(output_path)
    
    # Видаляємо всі старі листи, щоб не тратити час на delete_rows і створити ідеальні нові
    for sheet_name in wb.sheetnames:
        del wb[sheet_name]

    # --- ЛИСТ 1: Поіменний (Оброблений) ---
    ws1 = wb.create_sheet("Поіменний (Оброблений)")
    
    # Малюємо шапку в зеленому стилі
    for r_idx, row in enumerate(header_rows, 1):
        cleaned_row = ["" if pd.isna(x) else x for x in row]
        ws1.append(cleaned_row)
        for col_idx, val in enumerate(cleaned_row, 1):
            cell = ws1.cell(row=r_idx, column=col_idx)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = thin_border
            
    ws1.freeze_panes = 'A4'

    rows_data = data_df.values.tolist()

    if rows_data:
        current_name = rows_data[0][1]
        current_date = rows_data[0][5]
        count = 0

        # Вписуємо відсортовані дані
        for row in rows_data:
            name = row[1]
            date = row[5]

            # Зміна працівника або дати - додаємо підсумок (жовтий рядок)
            if name != current_name or date != current_date:
                summary_row = [None] * len(row)
                date_str = current_date.strftime('%d.%m.%Y') if pd.notnull(current_date) else 'Невідома дата'
                summary_row[5] = f"Всього дзвінків за {date_str}: {count}"
                ws1.append(summary_row)

                for cell in ws1[ws1.max_row]:
                    cell.fill = yellow_fill
                    cell.font = bold_font
                    cell.border = thin_border
                    cell.alignment = center_align
                
                if name != current_name:
                    ws1.append([None]); ws1.append([None]); ws1.append([None])
                else:
                    ws1.append([None]); ws1.append([None])

                current_name = name
                current_date = date
                count = 0

            formatted_row = list(row)
            if pd.notnull(formatted_row[5]):
                formatted_row[5] = formatted_row[5].strftime('%d.%m.%Y')
            else:
                formatted_row[5] = "-" 
                
            ws1.append(formatted_row)

            # Наводимо красу для даних
            for cell in ws1[ws1.max_row]:
                if cell.value is not None:
                    cell.border = thin_border
                    cell.alignment = left_align if cell.column == 2 else center_align
            count += 1

        # Останній підсумок
        summary_row = [None] * len(rows_data[0])
        date_str = current_date.strftime('%d.%m.%Y') if pd.notnull(current_date) else 'Невідома дата'
        summary_row[5] = f"Всього дзвінків за {date_str}: {count}"
        ws1.append(summary_row)
        for cell in ws1[ws1.max_row]:
            cell.fill = yellow_fill
            cell.font = bold_font
            cell.border = thin_border
            cell.alignment = center_align

    # Ширина колонок Лист 1
    cols_width1 = {'A': 15, 'B': 40, 'C': 15, 'D': 15, 'E': 15, 'F': 25, 'G': 15}
    for col, width in cols_width1.items():
        ws1.column_dimensions[col].width = width

    # --- ЛИСТ 2: Зведена статистика (СУПЕР-ШВИДКІСТЬ) ---
    ws2 = wb.create_sheet(title="Зведена статистика")
    ws2.freeze_panes = 'A2'

    valid_dates = data_df[5].dropna()
    if not valid_dates.empty:
        target_year = int(valid_dates.dt.year.mode()[0])
        target_month = int(valid_dates.dt.month.mode()[0])
        _, num_days = calendar.monthrange(target_year, target_month)
        month_dates = [pd.Timestamp(year=target_year, month=target_month, day=d) for d in range(1, num_days + 1)]
        
        # --- ФІКС 3: crosstab рахує всю матрицю за 0.01 сек замість мільйона циклів ---
        pivot_counts = pd.crosstab(data_df[5], data_df[1])
    else:
        month_dates = []
        pivot_counts = pd.DataFrame()

    workers = sorted([w for w in data_df[1].unique() if w is not None])
    default_rrsc = data_df[0].dropna().iloc[0] if not data_df[0].dropna().empty else "Дані відсутні"

    headers = ["РРСЦ", "Дата"] + workers
    ws2.append(headers)

    for col_num, header in enumerate(headers, 1):
        cell = ws2.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border
        cell.alignment = center_align

    # Заповнюємо дані зі швидкістю світла
    for md in month_dates:
        row_out = [default_rrsc, md.strftime('%d.%m.%Y')]
        for w in workers:
            # Якщо дата і працівник є в pivot таблиці - беремо значення, інакше 0
            count_val = pivot_counts.loc[md, w] if (md in pivot_counts.index and w in pivot_counts.columns) else 0
            row_out.append(int(count_val))
            
        ws2.append(row_out)
        for cell in ws2[ws2.max_row]: 
            cell.border = thin_border
            cell.alignment = center_align

    # Підсумковий рядок (Сірий колір як футер)
    total_row = ["", "ВСЬОГО ЗА МІСЯЦЬ:"]
    for w in workers:
        total_count = pivot_counts[w].sum() if w in pivot_counts.columns else 0
        total_row.append(int(total_count))
        
    ws2.append(total_row)
    for c_idx, cell in enumerate(ws2[ws2.max_row], 1):
        cell.font = bold_font
        cell.border = thin_border
        if c_idx > 1:
            cell.fill = controller_fill
            cell.alignment = center_align
        else:
            cell.fill = header_fill

    ws2.column_dimensions['A'].width = 20
    ws2.column_dimensions['B'].width = 15
    for col in range(3, len(headers) + 1):
        ws2.column_dimensions[ws2.cell(row=1, column=col).column_letter].width = 15

    wb.save(output_path)
    return output_filename