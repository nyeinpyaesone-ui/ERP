"""
Localization utilities for Myanmar ERP context.
Handles MMK currency formatting, local tax rules, and date formats.
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime

class MyanmarLocalization:
    """Handles Myanmar-specific localization logic."""
    
    CURRENCY_CODE = "MMK"
    
    # Myanmar Tax Rates (Example: Commercial Tax 5%)
    COMMERCIAL_TAX_RATE = Decimal("0.05")

    @staticmethod
    def format_currency(amount: float, symbol: bool = True) -> str:
        """Format amount as Myanmar Kyat (MMK)."""
        symbol_str = " Ks" if symbol else ""
        return f"{amount:,.2f}{symbol_str}"

    @staticmethod
    def calculate_commercial_tax(amount: Decimal) -> Decimal:
        """Calculate standard 5% commercial tax."""
        return (amount * MyanmarLocalization.COMMERCIAL_TAX_RATE).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @staticmethod
    def format_my_date(date_obj: datetime) -> str:
        """Format date to Myanmar format (e.g., ၂၀၂၄-၀၁-၁၅)."""
        # Mapping digits to Myanmar script
        my_digits = "၀၁၂၃၄၅၆၇၈၉"
        date_str = date_obj.strftime("%Y-%m-%d")
        return "".join(my_digits[int(d)] if d.isdigit() else d for d in date_str)
