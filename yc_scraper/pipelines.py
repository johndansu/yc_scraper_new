# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html

import pandas as pd
from itemadapter import ItemAdapter
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter


class ExcelExportPipeline:
    """Pipeline to export items to Excel format"""

    def __init__(self):
        self.items = []

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        # Convert item to dict and ensure all fields are present
        item_dict = {
            'company_name': adapter.get('company_name', ''),
            'company_website': adapter.get('company_website', ''),
            'founders_name': adapter.get('founders_name', ''),
            'founders_linkedin': adapter.get('founders_linkedin', ''),
            'founders_twitter': adapter.get('founders_twitter', '')
        }
        self.items.append(item_dict)
        return item

    def close_spider(self, spider):
        if not self.items:
            spider.logger.warning('No items to export')
            return
        
        # Create DataFrame with proper column names
        df = pd.DataFrame(self.items)
        
        # Rename columns to user-friendly names
        column_mapping = {
            'company_name': 'Company Name',
            'company_website': 'Company Website',
            'founders_name': "Founder's Name",
            'founders_linkedin': 'Founders LinkedIn',
            'founders_twitter': 'Founders Twitter'
        }
        
        df = df.rename(columns=column_mapping)
        
        # Ensure columns are in the correct order
        column_order = [
            'Company Name',
            'Company Website',
            "Founder's Name",
            'Founders LinkedIn',
            'Founders Twitter'
        ]
        
        # Reorder columns (only include columns that exist)
        df = df[[col for col in column_order if col in df.columns]]
        
        # Export to Excel
        output_file = 'yc_companies.xlsx'
        
        try:
            # Write to Excel
            df.to_excel(output_file, index=False, engine='openpyxl')
            
            # Format the Excel file for better readability
            self._format_excel_file(output_file)
            
            spider.logger.info(f'✅ Successfully exported {len(self.items)} companies to {output_file}')
        except Exception as e:
            spider.logger.error(f'Error exporting to Excel: {e}')
            raise
    
    def _format_excel_file(self, filename):
        """Format the Excel file with headers and column widths"""
        try:
            wb = load_workbook(filename)
            ws = wb.active
            
            # Format header row
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF", size=11)
            
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center', vertical='center')
            
            # Auto-adjust column widths
            for column in ws.columns:
                max_length = 0
                column_letter = get_column_letter(column[0].column)
                
                for cell in column:
                    try:
                        cell_value = str(cell.value) if cell.value else ''
                        if len(cell_value) > max_length:
                            max_length = len(cell_value)
                    except:
                        pass
                
                # Set column width (with some padding, max 50)
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            # Set row height for header
            ws.row_dimensions[1].height = 20
            
            # Freeze header row
            ws.freeze_panes = 'A2'
            
            wb.save(filename)
        except Exception as e:
            # If formatting fails, the file still exists with data
            pass

