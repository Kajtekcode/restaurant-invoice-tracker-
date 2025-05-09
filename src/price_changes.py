import logging
from src.sheets import get_worksheet
from src.config import get_spreadsheet

logger = logging.getLogger(__name__)

def detect_price_changes(spreadsheet, ingredients, category):
    """Detect price changes (>5%) for ingredients in a category."""
    try:
        worksheet = get_worksheet(spreadsheet, category)
        sheet_data = worksheet.get_all_records()
        formatted_sheet_data = []
        for record in sheet_data:
            try:
                net_price = float(str(record["Cena netto (za JM)"]).replace(",", "."))
                formatted_record = {
                    "Składnik": record["Składnik"],
                    "Cena netto (za JM)": round(net_price, 2)
                }
                formatted_sheet_data.append(formatted_record)
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping invalid record in {category}: {e}")
                continue

        price_changes = []
        for ingredient in ingredients:
            new_price = ingredient["net_price_per_unit"]
            ingredient_name = ingredient["name"]
            for record in formatted_sheet_data:
                if record["Składnik"] == ingredient_name:
                    old_price = record["Cena netto (za JM)"]
                    if old_price > 0:
                        change_percent = ((new_price - old_price) / old_price) * 100
                        if abs(change_percent) > 5:
                            price_changes.append({
                                "name": ingredient_name,
                                "old_price": round(old_price, 2),
                                "new_price": round(new_price, 2),
                                "change_percent": round(change_percent, 2)
                            })
                    break

        if price_changes:
            logger.info(f"Price changes in {category}: {price_changes}")
        else:
            logger.info(f"No significant price changes in {category}")
        return price_changes
    except Exception as e:
        logger.error(f"Failed to detect price changes in {category}: {e}")
        return []