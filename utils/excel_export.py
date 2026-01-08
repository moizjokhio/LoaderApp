"""
Excel Export Utilities
"""
import pandas as pd
from io import BytesIO


def convert_df_to_excel(df: pd.DataFrame, sheet_name: str = "Data") -> bytes:
    """
    Convert DataFrame to Excel bytes for download.
    
    Args:
        df: pandas DataFrame
        sheet_name: Name for the Excel sheet
    
    Returns:
        bytes: Excel file as bytes
    """
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()
