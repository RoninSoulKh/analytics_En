import pandas as pd
import numpy as np
import calendar
import re
import os
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Border, Side, Alignment

def run_calls_analysis(input_path, output_dir):
    # --- СТИЛІ ---
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                         top=Side(style='thin'), bottom=Side(style='thin'))
    yellow_fill = PatternFill(start_color='FFFF00', end_color='FFFF00', fill_type='solid')
    bold_font = Font(bold=True)
    wrap_align = Alignment(wrap_text=True, horizontal='center', vertical='center')

    # 1. Читаємо дані через pandas для математики та сортування
    df_raw = pd.read_excel(input_path, sheet_name=0, header=None)
    data_df = df_raw.iloc[3:].copy() # Пропускаємо шапку (3 рядки)
    data_df = data_df.where(pd.notnull(data_df), None)

    # Сортування: ПІБ (колонка 1), Дата (колонка 5)
    data_df[5] = pd.to_datetime(data_df[5], errors='coerce', dayfirst=True)
    data_df = data_df.sort_values(by=[1, 5])

    # Завантажуємо ОРИГІНАЛЬНИЙ файл через openpyxl, щоб зберегти формати шапки
    wb = load_workbook(input_path)
    ws1 = wb.worksheets[0]
    ws1.title = "Поіменний (Оброблений)"

    # Видаляємо старі дані
    ws1.delete_rows(4, ws1.max_row)
    ws1.freeze_panes = 'A4'

    rows_data = data_df.values.tolist()

    if rows_data:
        current_name = rows_data[0][1]
        
        current_date_raw = rows_data[0][5]
        current_date_str = current_date_raw.strftime('%d.%m.%Y') if pd.notnull(current_date_raw) else 'Невідома дата'
        count = 0

        for row in rows_data:
            name = row[1]
            date_raw = row[5]
            date_str = date_raw.strftime('%d.%m.%Y') if pd.notnull(date_raw) else 'Невідома дата'

            if name != current_name or date_str != current_date_str:
                summary_row = [None] * len(row)
                summary_row[5] = f"Всього дзвінків за {current_date_str}: {count}"
                ws1.append(summary_row)

                for cell in ws1[ws1.max_row]:
                    cell.fill = yellow_fill
                    cell.font = bold_font
                    cell.border = thin_border
                
                if name != current_name:
                    ws1.append([None]); ws1.append([None]); ws1.append([None])
                else:
                    ws1.append([None]); ws1.append([None])

                current_name = name
                current_date_str = date_str
                count = 0

            formatted_row = list(row)
            # ФІКС: Замінюємо NaT на None, щоб openpyxl не вмирав
            formatted_row[5] = formatted_row[5].strftime('%d.%m.%Y') if pd.notnull(formatted_row[5]) else None
            ws1.append(formatted_row)

            for cell in ws1[ws1.max_row]:
                if cell.value is not None:
                    cell.border = thin_border
            count += 1

        # Останній підсумок
        summary_row = [None] * len(rows_data[0])
        summary_row[5] = f"Всього дзвінків за {current_date_str}: {count}"
        ws1.append(summary_row)
        for cell in ws1[ws1.max_row]:
            cell.fill = yellow_fill; cell.font = bold_font; cell.border = thin_border

    # --- ЛИСТ 2: Зведена статистика ---
    if "Зведена статистика" in wb.sheetnames:
        del wb["Зведена статистика"]
    ws2 = wb.create_sheet(title="Зведена статистика")
    ws2.freeze_panes = 'A2'

    valid_dates = data_df[5].dropna()
    if not valid_dates.empty:
        target_year = int(valid_dates.dt.year.mode()[0])
        target_month = int(valid_dates.dt.month.mode()[0])
        _, num_days = calendar.monthrange(target_year, target_month)
        month_dates = [pd.Timestamp(year=target_year, month=target_month, day=d) for d in range(1, num_days + 1)]
    else:
        month_dates = []

    workers = sorted([w for w in data_df[1].unique() if w is not None])
    default_rrsc = data_df[0].dropna().iloc[0] if not data_df[0].dropna().empty else "Дані відсутні"

    headers = ["РРСЦ", "Дата"] + workers
    ws2.append(headers)

    for cell in ws2[1]:
        cell.font = bold_font; cell.border = thin_border; cell.alignment = wrap_align

    for md in month_dates:
        row_out = [default_rrsc, md.strftime('%d.%m.%Y')]
        for w in workers:
            c = len(data_df[(data_df[1] == w) & (data_df[5] == md)])
            row_out.append(c)
        ws2.append(row_out)
        for cell in ws2[ws2.max_row]: cell.border = thin_border

    total_row = ["", "Всього за місяць:"]
    for w in workers:
        total_row.append(len(data_df[data_df[1] == w]))
    ws2.append(total_row)
    for cell in ws2[ws2.max_row]:
        cell.font = bold_font; cell.border = thin_border; cell.fill = yellow_fill

    ws2.column_dimensions['A'].width = 20
    ws2.column_dimensions['B'].width = 12
    for col in range(3, len(headers) + 1):
        ws2.column_dimensions[ws2.cell(row=1, column=col).column_letter].width = 15

    # Збереження
    input_filename = os.path.basename(input_path)
    output_filename = input_filename.replace('.xlsx', '_Оброблений.xlsx')
    output_path = os.path.join(output_dir, output_filename)
    wb.save(output_path)
    
    return output_filename
