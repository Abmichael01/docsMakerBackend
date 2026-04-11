import json
from asgiref.sync import sync_to_async

async def handle_analyze_document(args, fields):
    """
    Skill: Deep document analysis for math errors, locale consistency, and professional polish.
    """
    events = []
    issues = []
    recommendations = []
    
    # 1. Math Guard Logic
    # Group fields by potential logical blocks (e.g. subtotal, tax, total)
    field_map = {f['id']: f for f in fields}
    
    # Simple math check for common field names
    try:
        subtotal = float(field_map.get('subtotal.number', {}).get('currentValue', 0) or 0)
        tax = float(field_map.get('tax.number', {}).get('currentValue', 0) or 0)
        total = float(field_map.get('total.number', {}).get('currentValue', 0) or 0)
        
        if subtotal + tax != total and total != 0:
            issues.append(f"Math Error: Subtotal ({subtotal}) + Tax ({tax}) does not equal Total ({total}). Should be {subtotal+tax}.")
    except: pass

    # 2. Locale Logic
    country = str(field_map.get('country.select', {}).get('currentValue', '')).lower()
    if 'usa' in country or 'united states' in country:
        date_val = str(field_map.get('date.date', {}).get('currentValue', ''))
        if date_val and '/' in date_val:
            parts = date_val.split('/')
            if len(parts) == 3 and int(parts[0]) > 12: # Likely DD/MM/YYYY
                issues.append(f"Locale Mismatch: US document detected, but date '{date_val}' is in DD/MM format. Should be MM/DD.")

    # 3. Professional Polish (Executive Rewrite Triggers)
    for f in fields:
        val = str(f.get('currentValue', ''))
        if f.get('type') == 'textarea' and len(val.split()) < 5 and val.strip():
            recommendations.append(f"Field '{f.get('name')}' is very brief. I recommend a professional rewrite.")

    result_text = "Analysis complete. "
    if issues or recommendations:
        result_text += "Found these points: \n- " + "\n- ".join(issues + recommendations)
    else:
        result_text += "No issues found. Document is professional."

    return {
        "events": events,
        "text": result_text,
        "data": {
            "has_issues": len(issues) > 0,
            "issues": issues,
            "recommendations": recommendations
        }
    }

async def handle_get_locale_defaults(args):
    """
    Skill: Retrieve industry-standard defaults for various locales.
    """
    country = args.get("country", "Global").lower()
    
    locales = {
        "nigeria": {"vat": 0.075, "currency": "NGN", "date_format": "DD/MM/YYYY", "phone_code": "+234"},
        "uk": {"vat": 0.20, "currency": "GBP", "date_format": "DD/MM/YYYY", "phone_code": "+44"},
        "usa": {"vat": 0.0, "currency": "USD", "date_format": "MM/DD/YYYY", "phone_code": "+1"},
    }
    
    data = locales.get(country, locales.get("uk")) # Default to UK for global/unknown
    return {
        "events": [],
        "text": f"Retrieved defaults for {country.title()}: VAT {data['vat']*100}%, Currency {data['currency']}.",
        "data": data
    }
